"""
This module provides a read-only web evidence validation layer for the Tackle Hunger pipeline.
It takes a sites batch as input and produces a JSON evidence report for each site.

Stability guarantees:
- Every outbound web request has a bounded timeout (default 8s).
- Each request is retried at most MAX_RETRIES (2) times.
- A failure/timeout on one site never blocks the rest of the batch.
- Affected fields are marked as `not_evaluable` or `uncertain` instead of crashing.
- Lightweight per-site logging is emitted (start / warning / completion).

Performance optimizations (no behavior change):
- A single pooled `requests.Session` is reused for the entire batch run.
- An in-memory cache keyed by canonical URL avoids re-fetching duplicate
  websites that appear across multiple sites in the same batch.
- Per-site fetching is short-circuited (one canonical fetch per site).
- Run-level timing + cache-hit + request counters are emitted at the end.
"""

import json
import argparse
import logging
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import requests
    from requests.adapters import HTTPAdapter
    from requests.exceptions import RequestException, Timeout
    HAS_REQUESTS = True
except ImportError:  # graceful degradation: still works without `requests`
    requests = None
    HTTPAdapter = None
    RequestException = Exception
    Timeout = Exception
    HAS_REQUESTS = False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REQUEST_TIMEOUT = 8        # seconds (within the 5-10s window)
MAX_RETRIES = 2            # do not retry more than 2 times
MAX_WORKERS = 8            # parallel sites at a time (safe for network I/O)
USER_AGENT = "TackleHungerEvidenceBot/1.0 (+read-only)"

# ---------------------------------------------------------------------------
# Web search (enrichment) configuration
# ---------------------------------------------------------------------------
# Controlled web search is used ONLY to surface enrichment *candidates* for
# website discovery and phone extraction. Search results are never trusted
# blindly: every candidate flows through the existing probe + scoring path,
# and decision thresholds remain unchanged. Disable by setting the env var
# `TH_DISABLE_WEB_SEARCH=1` or overriding `ENABLE_WEB_SEARCH = False`.
import os as _os

ENABLE_WEB_SEARCH: bool = _os.environ.get("TH_DISABLE_WEB_SEARCH", "").strip() not in ("1", "true", "True")

# Cap how many results we *consider* per query. Kept small so search latency
# never dominates the batch and host load stays gentle.
WEB_SEARCH_MAX_RESULTS: int = 8

# Bounded per-search request (separate from page fetch timeout).
WEB_SEARCH_TIMEOUT: int = 6

# Optional: real search API keys. When present, used in preference to the
# free-tier HTML scrapers below.
#   - SERPER_API_KEY: https://serper.dev (Google search proxy, JSON API)
#   - BING_SEARCH_API_KEY + BING_SEARCH_ENDPOINT: legacy Bing-compatible API
SERPER_API_KEY: Optional[str] = _os.environ.get("SERPER_API_KEY") or None
BING_SEARCH_API_KEY: Optional[str] = _os.environ.get("BING_SEARCH_API_KEY") or None
BING_SEARCH_ENDPOINT: str = _os.environ.get(
    "BING_SEARCH_ENDPOINT",
    "https://api.bing.microsoft.com/v7.0/search",
)

# Browser-like UA only for the search request - host pages keep the bot UA.
_SEARCH_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("web_evidence")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Canonicalization helpers (used for caching only; never leak to output)
# ---------------------------------------------------------------------------
_SCHEME_RE = re.compile(r"^https?://", re.IGNORECASE)


def _canonical_url(value: Any) -> Optional[str]:
    """
    Canonical form used as a cache key. Strips scheme, leading 'www.',
    trailing slashes, and lowercases. Returns None for empty/None input.
    """
    if value is None:
        return None
    s = str(value).strip().lower()
    if not s:
        return None
    s = _SCHEME_RE.sub("", s)
    if s.startswith("www."):
        s = s[4:]
    return s.rstrip("/") or None


# ---------------------------------------------------------------------------
# Batch context: shared session, URL cache, counters
# ---------------------------------------------------------------------------
@dataclass
class BatchContext:
    """
    Per-run shared state. Created once per batch and passed through
    site/field processing to enable connection reuse and caching.
    """
    session: Any = None                                  # requests.Session or None
    url_cache: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    discovery_cache: Dict[str, Optional[Dict[str, Any]]] = field(default_factory=dict)
    # Cache homepage text (truncated) per canonical URL so multiple field
    # extractors (phone, address, etc.) can mine it without re-fetching.
    page_text_cache: Dict[str, str] = field(default_factory=dict)
    # Cache web-search results per normalized query so the same org never
    # triggers more than one outbound search per batch.
    search_cache: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    lock: Any = field(default_factory=threading.Lock)
    requests_made: int = 0
    cache_hits: int = 0
    discovery_attempts: int = 0
    discovery_hits: int = 0
    search_attempts: int = 0
    search_hits: int = 0

    def incr_requests(self) -> None:
        with self.lock:
            self.requests_made += 1

    def incr_cache_hits(self) -> None:
        with self.lock:
            self.cache_hits += 1


def _build_session() -> Any:
    """
    Build a pooled HTTP session sized for the configured worker count.
    Returns None if `requests` is unavailable.
    """
    if not HAS_REQUESTS:
        return None
    sess = requests.Session()
    sess.headers.update({"User-Agent": USER_AGENT})
    # Pool large enough for our worker count + a little headroom
    adapter = HTTPAdapter(pool_connections=MAX_WORKERS * 2, pool_maxsize=MAX_WORKERS * 2)
    sess.mount("http://", adapter)
    sess.mount("https://", adapter)
    return sess


# ---------------------------------------------------------------------------
# Safe request helper
# ---------------------------------------------------------------------------
def safe_get(url, site_label="unknown", ctx: Optional[BatchContext] = None):
    """
    Perform a bounded, retry-limited HTTP GET.

    Returns a dict:
      { "ok": bool, "status_code": int|None, "error": str|None }

    Never raises. Reuses the shared session from `ctx` when provided.
    """
    if not HAS_REQUESTS:
        return {"ok": False, "status_code": None, "error": "requests_not_installed"}

    if not url:
        return {"ok": False, "status_code": None, "error": "empty_url"}

    # Ensure scheme for the request, but do not modify caller's data
    target = url if url.lower().startswith(("http://", "https://")) else f"http://{url}"
    getter = ctx.session.get if (ctx is not None and ctx.session is not None) else requests.get
    if ctx is not None:
        ctx.incr_requests()

    last_error = None
    attempts = MAX_RETRIES + 1  # initial attempt + up to MAX_RETRIES retries
    for attempt in range(1, attempts + 1):
        try:
            resp = getter(target, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            return {"ok": resp.ok, "status_code": resp.status_code, "error": None}
        except Timeout:
            last_error = "timeout"
            logger.warning(f"[{site_label}] request timeout (attempt {attempt}/{attempts}) for {target}")
        except RequestException as e:
            last_error = f"request_error:{type(e).__name__}"
            logger.warning(f"[{site_label}] request failed (attempt {attempt}/{attempts}) for {target}: {e}")
        except Exception as e:  # belt-and-suspenders: never bubble up
            last_error = f"unexpected:{type(e).__name__}"
            logger.warning(f"[{site_label}] unexpected error (attempt {attempt}/{attempts}) for {target}: {e}")

    return {"ok": False, "status_code": None, "error": last_error or "unknown_failure"}


def safe_get_text(url, site_label="unknown", ctx: Optional[BatchContext] = None, max_bytes: int = 200_000):
    """
    Variant of safe_get that also returns response text (truncated).
    Returns: { "ok": bool, "text": str, "status_code": int|None, "error": str|None }
    """
    if not HAS_REQUESTS:
        return {"ok": False, "text": "", "status_code": None, "error": "requests_not_installed"}
    if not url:
        return {"ok": False, "text": "", "status_code": None, "error": "empty_url"}

    target = url if url.lower().startswith(("http://", "https://")) else f"http://{url}"
    getter = ctx.session.get if (ctx is not None and ctx.session is not None) else requests.get
    if ctx is not None:
        ctx.incr_requests()

    last_error = None
    attempts = MAX_RETRIES + 1
    for attempt in range(1, attempts + 1):
        try:
            resp = getter(target, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            text = resp.text or ""
            if len(text) > max_bytes:
                text = text[:max_bytes]
            return {"ok": resp.ok, "text": text, "status_code": resp.status_code, "error": None}
        except Timeout:
            last_error = "timeout"
            logger.warning(f"[{site_label}] discovery timeout (attempt {attempt}/{attempts}) for {target}")
        except RequestException as e:
            last_error = f"request_error:{type(e).__name__}"
            logger.warning(f"[{site_label}] discovery failed (attempt {attempt}/{attempts}) for {target}: {e}")
        except Exception as e:
            last_error = f"unexpected:{type(e).__name__}"
            logger.warning(f"[{site_label}] discovery unexpected error (attempt {attempt}/{attempts}) for {target}: {e}")

    return {"ok": False, "text": "", "status_code": None, "error": last_error or "unknown_failure"}


# ---------------------------------------------------------------------------
# Subpage crawl: contact / about pages
# ---------------------------------------------------------------------------
#
# Many charity / food-pantry sites place their phone number, email, or
# physical address ONLY on a dedicated "Contact" or "About" page, not on
# the homepage.  This module discovers such subpage links from the
# homepage HTML and fetches them so the existing phone/email extractors
# can mine a richer text corpus without any new dependencies.
#
# Design constraints:
#   - At most MAX_SUBPAGES (2) extra fetches per site to stay well within
#     rate-limit budgets.
#   - Only same-origin links are followed (no external navigation).
#   - Results are cached in `ctx.page_text_cache` with a "|subpages"
#     suffix so they're available to all downstream extractors.
# ---------------------------------------------------------------------------

# Patterns that strongly signal a contact / about / location page.
_CONTACT_PATH_RE = re.compile(
    r"/(contact|about|about[_-]?us|reach[_-]?us|get[_-]?in[_-]?touch"
    r"|our[_-]?location|location|directions|find[_-]?us|visit"
    r"|hours|info|connect|staff)"
    r"(/|$|\?|#|\.html?)",
    re.IGNORECASE,
)

# Anchor text patterns (for when the path is generic like /?page_id=42).
_CONTACT_ANCHOR_RE = re.compile(
    r"\b(contact\s*us|contact|about\s*us|about|get\s*in\s*touch"
    r"|reach\s*us|our\s*location|location|find\s*us|directions"
    r"|visit\s*us|hours|connect|staff)\b",
    re.IGNORECASE,
)

_ANCHOR_HREF_RE = re.compile(
    r"""<a\s[^>]*?href\s*=\s*["']([^"'#]{1,300})["'][^>]*>(.*?)</a>""",
    re.IGNORECASE | re.DOTALL,
)

MAX_SUBPAGES = 2  # hard cap on extra fetches per site


def _discover_contact_pages(
    homepage_html: str,
    base_url: str,
) -> List[str]:
    """
    Scan the homepage HTML for anchor links that point to contact / about
    pages on the same domain.  Returns a de-duplicated list of absolute
    URLs (at most MAX_SUBPAGES).
    """
    if not homepage_html or not base_url:
        return []

    try:
        parsed_base = _urlparse.urlparse(
            base_url if base_url.startswith(("http://", "https://")) else f"https://{base_url}"
        )
        base_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"
        base_netloc = parsed_base.netloc.lower().lstrip("www.")
    except Exception:
        return []

    seen: set = set()
    results: List[str] = []

    for m in _ANCHOR_HREF_RE.finditer(homepage_html):
        href_raw = m.group(1).strip()
        anchor_text = re.sub(r"<[^>]+>", "", m.group(2)).strip()  # strip inner tags

        if not href_raw or href_raw.startswith(("javascript:", "mailto:", "tel:")):
            continue

        # Resolve relative URLs
        if href_raw.startswith("/"):
            full_url = base_origin + href_raw
        elif href_raw.startswith(("http://", "https://")):
            full_url = href_raw
        elif not href_raw.startswith(("http://", "https://", "/")):
            # Relative path like "contact.html"
            base_path = parsed_base.path.rsplit("/", 1)[0] if "/" in parsed_base.path else ""
            full_url = f"{base_origin}{base_path}/{href_raw}"
        else:
            continue

        # Same-origin check
        try:
            parsed_link = _urlparse.urlparse(full_url)
            link_netloc = parsed_link.netloc.lower().lstrip("www.")
        except Exception:
            continue
        if link_netloc != base_netloc:
            continue

        # Strip fragment for dedup (but keep query string — it may differentiate pages)
        _path_part = (parsed_link.path or "").rstrip("/")
        _query_part = f"?{parsed_link.query}" if parsed_link.query else ""
        dedup_key = f"{parsed_link.scheme}://{parsed_link.netloc}{_path_part}{_query_part}".lower()
        # Skip homepage self-links
        _base_path_part = (parsed_base.path or "").rstrip("/")
        _base_query_part = f"?{parsed_base.query}" if parsed_base.query else ""
        base_dedup = f"{parsed_base.scheme}://{parsed_base.netloc}{_base_path_part}{_base_query_part}".lower()
        if dedup_key == base_dedup or dedup_key in seen:
            continue

        # Check if path or anchor text matches contact/about patterns
        path = parsed_link.path or ""
        is_contact_path = bool(_CONTACT_PATH_RE.search(path))
        is_contact_text = bool(anchor_text and _CONTACT_ANCHOR_RE.search(anchor_text))

        if is_contact_path or is_contact_text:
            seen.add(dedup_key)
            results.append(full_url)
            if len(results) >= MAX_SUBPAGES:
                break

    return results


def _fetch_subpage_texts(
    urls: List[str],
    site_label: str = "unknown",
    ctx: Optional[BatchContext] = None,
) -> List[str]:
    """
    Fetch up to MAX_SUBPAGES subpage URLs and return their response texts.
    Failures are silently skipped (never raise).  Results are cached in
    ctx.page_text_cache under their canonical URL.
    """
    texts: List[str] = []
    for url in urls[:MAX_SUBPAGES]:
        canon = _canonical_url(url)
        # Check cache first
        if ctx is not None and canon and canon in ctx.page_text_cache:
            texts.append(ctx.page_text_cache[canon])
            if ctx is not None:
                ctx.incr_cache_hits()
            continue
        result = safe_get_text(url, site_label=site_label, ctx=ctx)
        if result["ok"] and result.get("text"):
            texts.append(result["text"])
            if ctx is not None and canon:
                with ctx.lock:
                    ctx.page_text_cache.setdefault(canon, result["text"])
    return texts


# ---------------------------------------------------------------------------
# Web search (controlled enrichment backend)
# ---------------------------------------------------------------------------
#
# `_web_search` is a small, defensive search frontend used to surface
# enrichment candidates for two downstream consumers:
#
#   1. Website discovery - search result URLs are added to the candidate
#      pool, then probed and scored by the *existing* heuristic. Search
#      results are never auto-trusted.
#   2. Phone candidate extraction - result titles + snippets are scanned
#      for phone numbers using the same regex as homepage scraping.
#      Search-derived phones are score-capped so they cannot, on their
#      own, push a candidate over the proposed-update threshold.
#
# Backends, tried in order:
#   a) Serper.dev JSON API     (preferred when SERPER_API_KEY is set)
#   b) Bing-compatible REST    (when BING_SEARCH_API_KEY is set)
#   c) DuckDuckGo HTML scrape  (no key required; best effort)
#
# All backends:
#   - return `[]` on any failure (never raise)
#   - share a single per-batch query cache (`ctx.search_cache`)
#   - obey `WEB_SEARCH_MAX_RESULTS` and `WEB_SEARCH_TIMEOUT`
# ---------------------------------------------------------------------------

# DDG HTML anchors look like:  <a class="result__a" href="URL">Title</a>
_DDG_ANCHOR_RE = re.compile(
    r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
# DDG snippet container directly after the anchor.
_DDG_SNIPPET_RE = re.compile(
    r'class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
# DDG sometimes wraps the real URL in /l/?uddg=<encoded>
_DDG_REDIRECT_RE = re.compile(r"/l/\?(?:.*?&)?uddg=([^&]+)")
# Cheap HTML-tag stripper for snippet text.
_TAG_STRIP_RE = re.compile(r"<[^>]+>")


def _strip_html_inline(s: str) -> str:
    """Strip HTML and collapse whitespace from a short snippet string."""
    if not s:
        return ""
    return re.sub(r"\s+", " ", _TAG_STRIP_RE.sub(" ", s)).strip()


def _normalize_search_url(href: str) -> Optional[str]:
    """Resolve DDG redirect wrappers, keep only http(s) URLs."""
    if not href:
        return None
    h = href.strip()
    # DDG redirect wrapper: //duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com
    m = _DDG_REDIRECT_RE.search(h)
    if m:
        try:
            h = _urlparse.unquote(m.group(1))
        except Exception:
            return None
    if h.startswith("//"):
        h = "https:" + h
    if not h.lower().startswith(("http://", "https://")):
        return None
    return h


def _web_search(
    query: str,
    ctx: Optional[BatchContext] = None,
    max_results: int = WEB_SEARCH_MAX_RESULTS,
) -> List[Dict[str, Any]]:
    """
    Run a single, bounded web search and return up to `max_results` items.

    Returns: `[{ "url": str, "title": str, "snippet": str, "source": str }, ...]`
    Always returns a list - never raises. An empty list means the backend
    is unavailable or produced no usable results.
    """
    if not ENABLE_WEB_SEARCH or not HAS_REQUESTS:
        return []
    q = (query or "").strip()
    if not q:
        return []

    cache_key = q.lower()
    if ctx is not None:
        with ctx.lock:
            if cache_key in ctx.search_cache:
                ctx.cache_hits += 1
                return ctx.search_cache[cache_key][:max_results]
        ctx.search_attempts += 1

    results: List[Dict[str, Any]] = []
    session = ctx.session if (ctx and ctx.session is not None) else requests

    # ---- Backend (a): Serper.dev ------------------------------------------------
    if not results and SERPER_API_KEY:
        try:
            resp = session.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
                json={"q": q, "num": max_results},
                timeout=WEB_SEARCH_TIMEOUT,
            )
            if ctx is not None:
                ctx.incr_requests()
            if resp.ok:
                data = resp.json() if resp.content else {}
                for item in (data.get("organic") or [])[:max_results]:
                    url = _normalize_search_url(item.get("link") or "")
                    if not url:
                        continue
                    results.append({
                        "url": url,
                        "title": (item.get("title") or "").strip(),
                        "snippet": (item.get("snippet") or "").strip(),
                        "source": "serper",
                    })
        except Exception as e:
            logger.warning(f"web_search serper backend failed: {type(e).__name__}: {e}")

    # ---- Backend (b): Bing-compatible REST -------------------------------------
    if not results and BING_SEARCH_API_KEY:
        try:
            resp = session.get(
                BING_SEARCH_ENDPOINT,
                headers={"Ocp-Apim-Subscription-Key": BING_SEARCH_API_KEY},
                params={"q": q, "count": max_results, "textDecorations": False, "responseFilter": "Webpages"},
                timeout=WEB_SEARCH_TIMEOUT,
            )
            if ctx is not None:
                ctx.incr_requests()
            if resp.ok:
                data = resp.json() if resp.content else {}
                for item in ((data.get("webPages") or {}).get("value") or [])[:max_results]:
                    url = _normalize_search_url(item.get("url") or "")
                    if not url:
                        continue
                    results.append({
                        "url": url,
                        "title": (item.get("name") or "").strip(),
                        "snippet": (item.get("snippet") or "").strip(),
                        "source": "bing",
                    })
        except Exception as e:
            logger.warning(f"web_search bing backend failed: {type(e).__name__}: {e}")

    # ---- Backend (c): DuckDuckGo HTML scrape -----------------------------------
    if not results:
        try:
            resp = session.post(
                "https://html.duckduckgo.com/html/",
                data={"q": q},
                headers={
                    "User-Agent": _SEARCH_BROWSER_UA,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                timeout=WEB_SEARCH_TIMEOUT,
                allow_redirects=True,
            )
            if ctx is not None:
                ctx.incr_requests()
            if resp.ok and resp.text:
                html = resp.text
                # Walk anchors in document order so the rank is preserved.
                seen_urls: set = set()
                # Build a parallel snippet index by scanning the same document.
                snippet_iter = _DDG_SNIPPET_RE.finditer(html)
                snippets_in_order = [
                    _strip_html_inline(m.group(1)) for m in snippet_iter
                ]
                anchor_idx = 0
                for m in _DDG_ANCHOR_RE.finditer(html):
                    if len(results) >= max_results:
                        break
                    url = _normalize_search_url(m.group(1))
                    if not url:
                        anchor_idx += 1
                        continue
                    canon = _canonical_url(url)
                    if canon and canon in seen_urls:
                        anchor_idx += 1
                        continue
                    if canon:
                        seen_urls.add(canon)
                    title = _strip_html_inline(m.group(2))
                    snippet = (
                        snippets_in_order[anchor_idx]
                        if anchor_idx < len(snippets_in_order)
                        else ""
                    )
                    results.append({
                        "url": url,
                        "title": title,
                        "snippet": snippet,
                        "source": "ddg",
                    })
                    anchor_idx += 1
        except Exception as e:
            logger.warning(f"web_search ddg backend failed: {type(e).__name__}: {e}")

    if ctx is not None:
        with ctx.lock:
            ctx.search_cache[cache_key] = results
            if results:
                ctx.search_hits += 1

    return results[:max_results]


def _build_site_search_query(site: Dict[str, Any]) -> str:
    """Compose the canonical enrichment query for a site."""
    name = (site.get("name") or "").strip()
    city = (site.get("city") or "").strip()
    state = (site.get("state") or "").strip()
    parts = [p for p in (name, city, state) if p]
    return " ".join(parts).strip()


def _perform_site_search(
    site: Dict[str, Any],
    ctx: Optional[BatchContext] = None,
) -> List[Dict[str, Any]]:
    """One bounded enrichment search per site. Cached in `ctx.search_cache`."""
    if not ENABLE_WEB_SEARCH:
        return []
    return _web_search(_build_site_search_query(site), ctx=ctx)


# ---------------------------------------------------------------------------
# Website discovery (for sites with no website on record)
# ---------------------------------------------------------------------------
#
# Design note:
# ------------
# The original intent was to issue a query like "<name> <city> <state>
# official website" to a public search engine (DuckDuckGo HTML / Bing / Brave)
# and rank the resulting URLs. In practice, all three public HTML endpoints
# either rate-limit, serve anti-bot pages with no scrapeable result anchors,
# or strip results entirely for non-browser User-Agents. A robust search-API
# integration would require a paid key (Serper, SerpAPI, Bing API, etc.).
#
# Since this pipeline must run without external API credentials, discovery
# uses a *deterministic candidate-domain probe* approach instead:
#
#   1. Tokenize the site name (drop stopwords like "food", "pantry").
#   2. Build a small set of plausible domains by concatenating tokens and
#      pairing them with .org / .com / .net TLDs (optionally suffixed with
#      the city for disambiguation).
#   3. HEAD/GET each candidate (bounded - max 6 probes per site, ~6s each)
#      reusing the pooled session.
#   4. For any candidate that responds 2xx/3xx, fetch the homepage text
#      (truncated) and verify by counting how many distinctive name tokens
#      appear in the body. This guards against parked / squat domains.
#   5. Score with `_score_candidate` (TLD weight + token overlap + content
#      verification boost). Best score >=0.9 -> high-quality proposed update.
#
# The blocklist, stopword list, scoring heuristic, and token extractor are
# kept generic so the implementation can be swapped to a real search API
# later by only replacing the "candidate generator" stage.
# ---------------------------------------------------------------------------
import urllib.parse as _urlparse

# Domains to reject as the "official site" even if they happen to match.
_DISCOVERY_BLOCKLIST = {
    "facebook.com", "m.facebook.com", "instagram.com", "twitter.com", "x.com",
    "yelp.com", "linkedin.com", "tiktok.com", "youtube.com",
    "yellowpages.com", "mapquest.com", "manta.com", "tripadvisor.com",
    "bbb.org", "guidestar.org", "charitynavigator.org",
    "google.com", "bing.com", "duckduckgo.com",
}
# Words to ignore when generating candidate domain bases or matching tokens.
_DISCOVERY_STOPWORDS = {
    "the", "a", "an", "of", "and", "for", "to", "in", "on", "at",
    "inc", "llc", "corp", "corporation", "co",
    "food", "pantry", "ministries", "ministry", "church", "center", "centre",
    "association", "society", "community", "services", "service",
    "incorporated", "foundation", "council", "organization",
}
# TLDs to probe, in priority order.
_DISCOVERY_TLDS = (".org", ".com", ".net")
# Per-site probe budget. With ~3 bases x 3 TLDs we'd have 9, capped here.
_DISCOVERY_MAX_PROBES = 6
_DISCOVERY_PROBE_TIMEOUT = 6
_DISCOVERY_PROBE_MAX_BYTES = 60_000

# Free / generic email providers - we cannot derive an org's website from
# these because the domain belongs to the provider, not the org.
_FREE_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com",
    "yahoo.com", "yahoo.co.uk", "ymail.com", "rocketmail.com",
    "hotmail.com", "outlook.com", "live.com", "msn.com",
    "aol.com", "icloud.com", "me.com", "mac.com",
    "protonmail.com", "proton.me", "pm.me",
    "mail.com", "gmx.com", "gmx.net", "zoho.com",
    "comcast.net", "verizon.net", "att.net", "sbcglobal.net", "bellsouth.net",
    "cox.net", "earthlink.net", "frontier.com", "charter.net",
    "yandex.com", "yandex.ru", "qq.com", "163.com", "126.com",
}


def _tokens_from_name(name: str) -> set:
    """Return the unordered set of distinctive name tokens (for scoring)."""
    raw = re.findall(r"[a-z0-9]+", (name or "").lower())
    return {t for t in raw if t not in _DISCOVERY_STOPWORDS and len(t) >= 3}


def _tokens_list_from_name(name: str) -> list:
    """Return tokens in name order (for building candidate domain bases)."""
    raw = re.findall(r"[a-z0-9]+", (name or "").lower())
    seen = set()
    out = []
    for t in raw:
        if t in _DISCOVERY_STOPWORDS or len(t) < 3 or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


# ---------------------------------------------------------------------------
# Entity drift prevention — identity validation helpers
# ---------------------------------------------------------------------------
# These functions guard against proposing values from the wrong entity.
# The scraper can find a valid-looking phone/website that belongs to a
# completely different organization with a similar name or on the same
# umbrella domain.  These helpers add guardrails so proposals only
# surface when identity, location, and domain relevance all check out.

# Domains whose core word indicates an unrelated business category.
# A food pantry should never adopt a technology company's website.
_UNRELATED_DOMAIN_KEYWORDS = {
    "solutions", "consulting", "software", "tech", "digital", "analytics",
    "law", "legal", "attorney", "dental", "dentist", "medical", "clinic",
    "insurance", "realty", "realtor", "mortgage", "auto", "plumbing",
    "electric", "hvac", "roofing", "landscaping", "construction",
}

# Domain keywords that suggest a directory/listing page, not an official site.
_DIRECTORY_DOMAIN_KEYWORDS = {
    "foodpantries", "pantrylocator", "yellowpages", "whitepages",
    "chamberofcommerce", "chamber", "countyclerk", "directory",
    "listing", "locator", "finder", "211",
}

# Domain keywords that are positive signals for nonprofit/pantry sites.
_NONPROFIT_DOMAIN_KEYWORDS = {
    "pantry", "church", "ministry", "mission", "food", "outreach",
    "parish", "diocese", "charity", "salvation", "goodwill", "habitat",
    "ymca", "ywca", "unitedway", "feedingamerica", "stvincentdepaul",
    "catholic", "lutheran", "methodist", "baptist", "presbyterian",
}

# ---------------------------------------------------------------------------
# Source-tag classification (labelling only — no scoring/gating impact)
# ---------------------------------------------------------------------------

# Email domains belonging to website-builder or hosting platforms.
_PLATFORM_EMAIL_DOMAINS = {
    "churchspring.com", "wordpress.com", "wix.com", "squarespace.com",
    "godaddysites.com", "weebly.com", "siteground.com", "bluehost.com",
    "hostgator.com", "jimdo.com", "duda.co", "webflow.io",
    "carrd.co", "mailchimp.com", "constantcontact.com",
}

# Email domains that are generic / consumer providers (lower confidence).
_GENERIC_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "icloud.com", "protonmail.com", "zoho.com", "mail.com", "yandex.com",
    "live.com", "msn.com", "comcast.net", "sbcglobal.net", "att.net",
    "verizon.net", "cox.net", "charter.net", "earthlink.net",
}

# Website domains belonging to third-party directories or social platforms.
_THIRD_PARTY_WEBSITE_DOMAINS = {
    "facebook.com", "fb.com", "instagram.com", "twitter.com", "x.com",
    "youtube.com", "tiktok.com", "linkedin.com", "nextdoor.com",
    "foodpantries.org", "pantrylocator.com", "foodbanks.net",
    "chamberofcommerce.com", "countyoffice.org", "yelp.com",
    "findhelp.org", "auntbertha.com", "211.org", "unitedway211.org",
    "yellowpages.com", "whitepages.com", "superpages.com",
    "mapquest.com", "bbb.org", "guidestar.org", "candid.org",
    "greatnonprofits.org", "charitynavigator.org",
}


def _classify_source_tag(
    field_type: str,
    proposed_value: Optional[str],
    site_name: str = "",
) -> Optional[str]:
    """Classify a proposed email or website value with a source tag.

    Returns one of:
      - ``"platform_email"``      – email domain is a website-builder/platform
      - ``"third_party_domain"``  – website domain is a directory/social site
      - ``"official_domain"``     – domain clearly matches org identity
      - ``None``                  – not classifiable / not applicable

    This is a **labelling-only** function.  It MUST NOT alter confidence,
    change status, or suppress proposals.
    """
    if not proposed_value:
        return None

    value_lc = proposed_value.strip().lower()

    if field_type == "email":
        # Extract domain part after @
        at_idx = value_lc.rfind("@")
        if at_idx < 0:
            return None
        domain = value_lc[at_idx + 1:]
        if domain in _PLATFORM_EMAIL_DOMAINS:
            return "platform_email"
        if domain in _GENERIC_EMAIL_DOMAINS:
            return "platform_email"   # treat generic providers the same tag
        # Check if domain contains platform substrings
        for pd in _PLATFORM_EMAIL_DOMAINS:
            base = pd.split(".")[0]    # e.g. "churchspring" from "churchspring.com"
            if base in domain:
                return "platform_email"
        return None

    if field_type == "website":
        domain = _domain_of(value_lc)
        if not domain:
            return None

        # Third-party / directory check
        for tp in _THIRD_PARTY_WEBSITE_DOMAINS:
            if domain == tp or domain.endswith("." + tp):
                return "third_party_domain"
        for kw in _DIRECTORY_DOMAIN_KEYWORDS:
            if kw in domain:
                return "third_party_domain"

        # Official domain heuristic: domain contains distinctive tokens
        # from the org name (e.g. "gracechapel.org" for "Grace Chapel").
        if site_name:
            name_tokens = _tokens_from_name(site_name)
            domain_base = domain.split(".")[0]  # e.g. "gracechapel"
            matches = sum(1 for t in name_tokens if t in domain_base)
            if matches >= 2 or (matches >= 1 and len(name_tokens) <= 2):
                return "official_domain"

        return None

    return None


_ENTITY_NAME_STOPWORDS = {
    "the", "a", "an", "of", "and", "for", "to", "in", "on", "at",
    "inc", "llc", "corp", "ministry", "church", "outreach", "center",
    "centre", "pantry", "food", "distribution", "organization",
    "association", "community", "services", "service", "foundation",
    "office", "parish", "dept", "department", "branch", "location",
    "site", "program", "project", "warehouse", "depot", "mission",
    "fellowship", "temple", "congregation", "chapel", "society",
    "bank", "closet", "cupboard", "kitchen", "soup", "meals",
    "assistance", "aid", "relief", "shelter", "housing",
}

# Keywords that indicate the TYPE of entity.  If the candidate has
# type-keywords that conflict with the target entity's apparent type,
# that's strong evidence of a different entity even when name tokens
# overlap (e.g., "Brightwater" matches both "Brightwater Food Pantry" and
# "Brightwater Solutions").
_ENTITY_TYPE_COMMERCIAL = {
    "solutions", "consulting", "software", "tech", "technology",
    "digital", "analytics", "agency", "group", "partners", "advisors",
    "labs", "enterprises", "systems", "innovations", "strategies",
    "ventures", "capital", "holdings", "investments", "properties",
    "management", "logistics", "marketing", "media", "creative",
    "design", "engineering", "development",
}
_ENTITY_TYPE_PROFESSIONAL = {
    "law", "legal", "attorney", "attorneys", "lawyer", "lawyers",
    "dental", "dentist", "dentistry", "orthodontics",
    "medical", "clinic", "hospital", "physician", "doctors",
    "insurance", "realty", "realtor", "mortgage", "title",
    "accounting", "tax", "financial", "wealth",
    "veterinary", "vet", "animal",
    "chiropractic", "chiropractor",
}
_ENTITY_TYPE_TRADE = {
    "auto", "automotive", "plumbing", "plumber", "electric",
    "electrical", "electrician", "hvac", "roofing", "roofer",
    "landscaping", "construction", "contractor", "paving",
    "towing", "moving", "storage", "trucking", "freight",
    "welding", "fabrication", "machining",
}
# Union of all commercial/professional/trade keywords
_ENTITY_TYPE_CONFLICTING = (
    _ENTITY_TYPE_COMMERCIAL | _ENTITY_TYPE_PROFESSIONAL | _ENTITY_TYPE_TRADE
)

# Keywords that indicate a nonprofit / food-assistance entity.
_ENTITY_TYPE_NONPROFIT = {
    "pantry", "food", "church", "ministry", "mission", "outreach",
    "parish", "diocese", "charity", "charities", "salvation",
    "goodwill", "habitat", "ymca", "ywca", "unitedway",
    "stvincentdepaul", "catholic", "lutheran", "methodist",
    "baptist", "presbyterian", "episcopal", "covenant",
    "rescue", "shelter", "meals", "soup", "kitchen",
    "thrift", "assistance", "aid", "relief", "feeding",
}


def _normalize_entity_name(name: str) -> str:
    """
    Normalize an entity name for comparison: lowercase, strip punctuation,
    collapse whitespace, remove common stopwords.
    """
    if not name:
        return ""
    s = re.sub(r"[^\w\s]", " ", name.lower())
    s = re.sub(r"\s+", " ", s).strip()
    tokens = [t for t in s.split() if t not in _ENTITY_NAME_STOPWORDS and len(t) >= 2]
    return " ".join(tokens)


def _compute_name_overlap(target_name: str, candidate_text: str) -> float:
    """
    Compute how well a candidate text matches the target entity name.

    Returns a ratio 0.0–1.0:
      1.0 = all distinctive tokens from target appear in candidate
      0.0 = no overlap at all
    """
    target_norm = _normalize_entity_name(target_name)
    if not target_norm:
        return 0.0
    target_tokens = set(target_norm.split())
    if not target_tokens:
        return 0.0
    # Extract tokens from candidate text the same way
    cand_norm = _normalize_entity_name(candidate_text)
    cand_tokens = set(cand_norm.split())
    if not cand_tokens:
        return 0.0
    matches = target_tokens & cand_tokens
    return len(matches) / len(target_tokens)


def _detect_entity_type_conflict(
    target_name: str,
    candidate_text: str,
) -> Dict[str, Any]:
    """
    Detect whether the candidate text indicates a fundamentally different
    type of organization than the target.

    This catches cases where simple token overlap succeeds but the entities
    are clearly different:
      - "Brightwater Food Pantry" vs "Brightwater Solutions" (pantry vs tech)
      - "Grace Church Pantry" vs "Grace Dental Care" (church vs dental)

    Returns:
      {
        "conflict": bool,
        "reason":   str,
        "target_type":    str,   # "nonprofit" | "unknown"
        "candidate_type": str,   # "commercial" | "professional" | "trade" |
                                 #   "nonprofit" | "unknown"
        "conflict_words": list,
      }
    """
    target_lc = (target_name or "").lower()
    cand_lc = (candidate_text or "").lower()

    target_words = set(re.findall(r"[a-z]+", target_lc))
    cand_words = set(re.findall(r"[a-z]+", cand_lc))

    # Determine target entity type
    target_nonprofit_hits = target_words & _ENTITY_TYPE_NONPROFIT
    target_is_nonprofit = bool(target_nonprofit_hits)

    # Look for conflicting type keywords in the candidate that the target
    # does NOT have.
    cand_conflict_words = []
    for w in cand_words:
        if w in _ENTITY_TYPE_CONFLICTING and w not in target_words:
            cand_conflict_words.append(w)

    # Determine candidate type
    if cand_conflict_words:
        cand_commercial = any(w in _ENTITY_TYPE_COMMERCIAL for w in cand_conflict_words)
        cand_professional = any(w in _ENTITY_TYPE_PROFESSIONAL for w in cand_conflict_words)
        cand_trade = any(w in _ENTITY_TYPE_TRADE for w in cand_conflict_words)
        if cand_professional:
            cand_type = "professional"
        elif cand_commercial:
            cand_type = "commercial"
        elif cand_trade:
            cand_type = "trade"
        else:
            cand_type = "unknown"
    else:
        cand_type = "unknown"
        cand_nonprofit_hits = cand_words & _ENTITY_TYPE_NONPROFIT
        if cand_nonprofit_hits:
            cand_type = "nonprofit"

    target_type = "nonprofit" if target_is_nonprofit else "unknown"

    if cand_conflict_words:
        return {
            "conflict": True,
            "reason": (
                f"Candidate contains {cand_type} keyword(s) "
                f"({', '.join(sorted(cand_conflict_words)[:3])}) "
                f"not present in target entity name."
            ),
            "target_type": target_type,
            "candidate_type": cand_type,
            "conflict_words": sorted(cand_conflict_words),
        }

    return {
        "conflict": False,
        "reason": "No entity type conflict detected.",
        "target_type": target_type,
        "candidate_type": cand_type,
        "conflict_words": [],
    }


def _entity_name_match(
    target_name: str,
    candidate_text: str,
) -> Dict[str, Any]:
    """
    Comprehensive entity name matching.  Combines normalized token overlap,
    bidirectional similarity, and entity-type conflict detection into a
    single verdict.

    Returns:
      {
        "accept":          bool,
        "reason":          str,
        "overlap":         float,   # 0.0-1.0  target -> candidate
        "reverse_overlap": float,   # 0.0-1.0  candidate -> target
        "jaccard":         float,   # 0.0-1.0  intersection / union
        "type_conflict":   bool,
        "type_detail":     dict,
      }
    """
    overlap = _compute_name_overlap(target_name, candidate_text)

    # Reverse overlap: does the target contain candidate's distinctive tokens?
    target_norm = _normalize_entity_name(target_name)
    cand_norm = _normalize_entity_name(candidate_text)
    target_tokens = set(target_norm.split()) if target_norm else set()
    cand_tokens = set(cand_norm.split()) if cand_norm else set()

    if cand_tokens:
        reverse_overlap = len(target_tokens & cand_tokens) / len(cand_tokens)
    else:
        reverse_overlap = 0.0

    # Jaccard: intersection / union
    union = target_tokens | cand_tokens
    jaccard = len(target_tokens & cand_tokens) / len(union) if union else 0.0

    # Entity type conflict
    type_result = _detect_entity_type_conflict(target_name, candidate_text)
    type_conflict = type_result["conflict"]

    base = {
        "overlap": overlap,
        "reverse_overlap": reverse_overlap,
        "jaccard": jaccard,
        "type_conflict": type_conflict,
        "type_detail": type_result,
    }

    # HARD REJECT: entity type conflict
    if type_conflict:
        return {
            **base, "accept": False,
            "reason": f"Entity type conflict: {type_result['reason']}",
        }

    # HARD REJECT: single-token target with low Jaccard
    # "Brightwater" (1 token) vs "Brightwater Something Else" -> overlap=1.0
    # but jaccard=0.33 -> likely different organization
    if overlap >= 0.9 and jaccard < 0.4 and len(target_tokens) <= 1:
        return {
            **base, "accept": False,
            "reason": (
                f"Single-token entity name with low bidirectional similarity "
                f"(jaccard={jaccard:.0%}); likely a different organization."
            ),
        }

    # SOFT REJECT: low overlap AND low Jaccard
    if overlap < 0.4 and jaccard < 0.3:
        return {
            **base, "accept": False,
            "reason": (
                f"Weak entity name match "
                f"(overlap={overlap:.0%}, jaccard={jaccard:.0%})."
            ),
        }

    # ACCEPT
    return {
        **base, "accept": True,
        "reason": "Entity name match validated.",
    }


# ---------------------------------------------------------------------------
# Location / address matching helpers
# ---------------------------------------------------------------------------

# Common US state full-name → abbreviation lookup (used for location matching)
_US_STATE_NAMES: Dict[str, str] = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "district of columbia": "DC", "florida": "FL", "georgia": "GA", "hawaii": "HI",
    "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME",
    "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM",
    "new york": "NY", "north carolina": "NC", "north dakota": "ND", "ohio": "OH",
    "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI",
    "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}
# Reverse: abbreviation → full name
_US_STATE_ABBREV_TO_NAME: Dict[str, str] = {v: k for k, v in _US_STATE_NAMES.items()}

# Regex for 5-digit US ZIP codes (standalone or with +4 extension)
_ZIP_RE = re.compile(r"\b(\d{5})(?:-\d{4})?\b")

# Common street suffixes (for street-token extraction)
_STREET_SUFFIXES = frozenset({
    "st", "street", "ave", "avenue", "blvd", "boulevard", "dr", "drive",
    "rd", "road", "ln", "lane", "ct", "court", "pl", "place", "way",
    "cir", "circle", "pkwy", "parkway", "hwy", "highway", "trl", "trail",
})


def _extract_zip_codes(text: str) -> set:
    """Extract all 5-digit US ZIP codes from text."""
    if not text:
        return set()
    return set(_ZIP_RE.findall(text))


def _street_tokens(address: str) -> set:
    """
    Extract meaningful tokens from a street address for comparison.

    Keeps building numbers, street names, and significant words.
    Drops generic suffixes ('street', 'road', etc.) and short tokens.
    """
    if not address:
        return set()
    tokens = re.findall(r"[a-z0-9]+", address.lower())
    result: Set[str] = set()
    for t in tokens:
        if t in _STREET_SUFFIXES:
            continue
        if len(t) < 2:
            continue
        result.add(t)
    return result


def _street_token_overlap(site_address: str, candidate_text: str) -> float:
    """
    Compute token overlap between a site's street address and candidate text.

    Returns 0.0–1.0 (fraction of site address tokens found in candidate text).
    """
    site_tokens = _street_tokens(site_address)
    if not site_tokens:
        return 0.0
    text_lc = (candidate_text or "").lower()
    hits = sum(1 for t in site_tokens if t in text_lc)
    return hits / len(site_tokens)


def _detect_different_city(
    site_city: str,
    site_state: str,
    candidate_text: str,
) -> Optional[str]:
    """
    Detect if candidate text mentions a DIFFERENT city in the same state.

    Uses a simple heuristic: looks for "CityName, ST" patterns in the text
    where ST matches the site's state but CityName differs.  Returns the
    detected different city or None.
    """
    if not site_state or not candidate_text:
        return None
    site_city_lc = (site_city or "").strip().lower()
    state_upper = site_state.strip().upper()
    if len(state_upper) != 2:
        return None

    # Pattern: "City, ST" or "City, State"
    # Also matches "City, ST 12345"
    pat = re.compile(
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*,\s*"
        + re.escape(state_upper)
        + r"(?:\s+\d{5})?\b",
    )
    for m in pat.finditer(candidate_text):
        city_found = m.group(1).strip().lower()
        if city_found and site_city_lc and city_found != site_city_lc:
            return m.group(1).strip()

    # Also check full state name pattern
    state_full = _US_STATE_ABBREV_TO_NAME.get(state_upper, "").lower()
    if state_full and len(state_full) > 3:
        pat2 = re.compile(
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*,\s*"
            + re.escape(state_full.title())
            + r"(?:\s+\d{5})?\b",
        )
        for m in pat2.finditer(candidate_text):
            city_found = m.group(1).strip().lower()
            if city_found and site_city_lc and city_found != site_city_lc:
                return m.group(1).strip()

    return None


def _location_match_detail(
    site: Dict[str, Any],
    candidate_text: str,
) -> Dict[str, Any]:
    """
    Comprehensive location matching between a site record and candidate text.

    Compares city, state, ZIP, and street address tokens.  Returns a rich
    dict that downstream gates can use for nuanced accept/reject/downgrade
    decisions — much richer than the old match/conflict/neutral trichotomy.

    Returns:
      {
        "city_match":    bool,
        "state_match":   bool,
        "zip_match":     bool,
        "street_overlap": float,  # 0.0–1.0
        "different_city": str | None,  # detected different city in same state
        "different_state": str | None, # detected different state abbreviation
        "zip_conflict":  bool,    # site ZIP present AND text has a different ZIP
        "score":         float,   # 0.0 (hard conflict) → 1.0 (perfect local)
        "verdict":       str,     # local_match | same_area | different_location
                                  # | different_city | neutral
      }
    """
    site_city = (site.get("city") or "").strip().lower()
    site_state = (site.get("state") or "").strip().upper()
    site_zip = (site.get("zip") or "").strip()
    site_address = (site.get("streetAddress") or "").strip()

    text_lc = (candidate_text or "").lower()
    if not text_lc:
        return {
            "city_match": False, "state_match": False, "zip_match": False,
            "street_overlap": 0.0, "different_city": None,
            "different_state": None, "zip_conflict": False,
            "score": 0.5, "verdict": "neutral",
        }

    # --- City ---
    city_match = bool(site_city and len(site_city) >= 3 and site_city in text_lc)

    # --- State ---
    state_match = False
    if site_state and len(site_state) == 2:
        state_lc = site_state.lower()
        state_match = (
            state_lc in text_lc
            or bool(re.search(r"\b" + re.escape(site_state) + r"\b", candidate_text or ""))
        )
        # Also check full state name
        state_full = _US_STATE_ABBREV_TO_NAME.get(site_state, "").lower()
        if state_full and state_full in text_lc:
            state_match = True

    # --- ZIP ---
    zip_match = False
    zip_conflict = False
    if site_zip and len(site_zip) >= 5:
        site_zip5 = site_zip[:5]
        text_zips = _extract_zip_codes(candidate_text or "")
        if site_zip5 in text_zips:
            zip_match = True
        elif text_zips:
            # Text has ZIP codes but NONE match the site — this is a signal
            # that the text refers to a different physical location.
            zip_conflict = True

    # --- Street address ---
    street_overlap = _street_token_overlap(site_address, candidate_text)

    # --- Different city in same state ---
    different_city = None
    if site_city and not city_match:
        different_city = _detect_different_city(site_city, site_state, candidate_text or "")

    # --- Different state ---
    different_state = None
    if site_state and len(site_state) == 2 and not state_match:
        _excl = {"us", "am", "pm", "po", "dr", "st", "rd", "ct", "av"}
        other_states = re.findall(r"\b([A-Z]{2})\b", candidate_text or "")
        for st in other_states:
            if st.upper() != site_state and st.lower() not in _excl:
                # Verify it's actually a state abbreviation
                if st.upper() in _US_STATE_ABBREV_TO_NAME:
                    different_state = st.upper()
                    break

    # --- Score computation ---
    score = 0.5  # neutral baseline

    # Positive signals
    if city_match:
        score += 0.25
    if state_match:
        score += 0.1
    if zip_match:
        score += 0.2
    if street_overlap >= 0.5:
        score += 0.15
    elif street_overlap >= 0.25:
        score += 0.05

    # Negative signals
    if different_state:
        score -= 0.35
    if different_city:
        score -= 0.25
    if zip_conflict:
        score -= 0.20

    score = max(0.0, min(1.0, score))

    # --- Verdict ---
    if city_match and (zip_match or street_overlap >= 0.5):
        verdict = "local_match"
    elif city_match:
        verdict = "same_area"
    elif different_state:
        verdict = "different_location"
    elif different_city:
        verdict = "different_city"
    elif zip_conflict and not city_match:
        verdict = "different_location"
    else:
        verdict = "neutral"

    return {
        "city_match": city_match,
        "state_match": state_match,
        "zip_match": zip_match,
        "street_overlap": street_overlap,
        "different_city": different_city,
        "different_state": different_state,
        "zip_conflict": zip_conflict,
        "score": round(score, 3),
        "verdict": verdict,
    }


def _location_consistency_check(
    site: Dict[str, Any],
    candidate_text: str,
) -> str:
    """
    Check whether candidate text is location-consistent with the site.

    Returns:
      "match"    - candidate mentions the site's city/state
      "conflict" - candidate mentions a DIFFERENT city/state that's clearly wrong
      "neutral"  - not enough location info to decide
    """
    site_city = (site.get("city") or "").strip().lower()
    site_state = (site.get("state") or "").strip().lower()
    if not site_city and not site_state:
        return "neutral"

    text_lc = candidate_text.lower() if candidate_text else ""
    if not text_lc:
        return "neutral"

    city_found = site_city and site_city in text_lc
    state_found = site_state and (
        site_state in text_lc
        or (len(site_state) == 2 and re.search(r"\b" + re.escape(site_state) + r"\b", text_lc))
    )

    if city_found:
        return "match"
    if state_found and not city_found:
        # State matches but city doesn't — might be same state, different city.
        # Look for signs of a different city explicitly mentioned.
        # For now, treat as neutral (not a hard conflict).
        return "neutral"

    # The text has content but doesn't mention our city or state.
    # Check if it mentions a different US state abbreviation prominently.
    if site_state and len(site_state) == 2:
        # Common state abbreviations pattern
        other_states = re.findall(r"\b([A-Z]{2})\b", candidate_text or "")
        for st in other_states:
            if st.lower() != site_state and st.lower() not in {"us", "am", "pm", "po", "dr", "st", "rd", "ct", "av"}:
                return "conflict"

    return "neutral"


def _domain_relevance_check(domain: str, org_name: str) -> str:
    """
    Check whether a domain is relevant for a nonprofit/pantry.

    Returns:
      "good"       - domain contains nonprofit-related keywords or org name tokens
      "unrelated"  - domain contains keywords from unrelated business categories
      "directory"  - domain looks like a directory/listing page
      "neutral"    - can't determine
    """
    if not domain:
        return "neutral"
    domain_lc = domain.lower()
    domain_core = domain_lc.rsplit(".", 1)[0] if "." in domain_lc else domain_lc
    domain_clean = re.sub(r"[^a-z0-9]", "", domain_core)

    # Check unrelated business categories
    for kw in _UNRELATED_DOMAIN_KEYWORDS:
        if kw in domain_clean:
            # But verify the org name doesn't itself contain this keyword
            org_clean = re.sub(r"[^a-z0-9]", "", (org_name or "").lower())
            if kw not in org_clean:
                return "unrelated"

    # Check directory patterns
    for kw in _DIRECTORY_DOMAIN_KEYWORDS:
        if kw in domain_clean:
            return "directory"

    # Check positive nonprofit signals
    for kw in _NONPROFIT_DOMAIN_KEYWORDS:
        if kw in domain_clean:
            return "good"

    # Check org name token overlap with domain
    name_tokens = _tokens_from_name(org_name)
    if name_tokens:
        hits = sum(1 for t in name_tokens if t in domain_clean)
        if hits >= 1:
            return "good"

    return "neutral"


def _detect_parent_office_drift(
    site: Dict[str, Any],
    candidate_text: str,
    proposed_value: str,
    page_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Detect likely "same umbrella, wrong office" drift.

    Returns a rich dict (not just bool) so callers can choose between
    hard-reject and downgrade based on drift strength and source.

    Returns:
      {
        "drift":       bool,   # True → drift detected
        "umbrella":    bool,   # site is a known umbrella-org member
        "admin_hit":   bool,   # admin/HQ keywords found in page
        "reason":      str,
        "loc_detail":  dict,   # _location_match_detail result
      }
    """
    site_name = site.get("name") or ""
    site_city = (site.get("city") or "").strip().lower()

    no_drift = {
        "drift": False, "umbrella": False, "admin_hit": False,
        "reason": "", "loc_detail": {},
    }

    if not site_city or not candidate_text:
        return no_drift

    text_lc = candidate_text.lower()
    url_lc = (page_url or "").lower()

    # Comprehensive location detail — used for ZIP/street signals
    loc_detail = _location_match_detail(site, candidate_text)

    site_name_lc = site_name.lower()
    is_umbrella = any(p in site_name_lc for p in _UMBRELLA_ORG_PATTERNS)

    # --- Admin keyword check (ALL orgs, not just umbrella) ---
    admin_hit = any(kw in text_lc or kw in url_lc for kw in _ADMIN_PAGE_KEYWORDS)

    base = {
        "umbrella": is_umbrella,
        "admin_hit": admin_hit,
        "loc_detail": loc_detail,
    }

    # If the page matches our city AND ZIP (or street) → no drift
    if loc_detail["city_match"] and (loc_detail["zip_match"] or loc_detail["street_overlap"] >= 0.5):
        return {**base, **no_drift, "umbrella": is_umbrella, "admin_hit": admin_hit,
                "loc_detail": loc_detail}

    # City matches but ZIP conflicts → possible wrong campus
    if loc_detail["city_match"] and loc_detail["zip_conflict"]:
        if site.get("streetAddress") and loc_detail["street_overlap"] < 0.3:
            return {
                **base, "drift": True,
                "reason": (
                    f"Same city but different ZIP/street "
                    f"(street overlap {loc_detail['street_overlap']:.0%}); "
                    f"likely different campus/office."
                ),
            }
        return {**base, **no_drift, "umbrella": is_umbrella, "admin_hit": admin_hit,
                "loc_detail": loc_detail}

    # City matches with no conflict → no drift
    if site_city in text_lc:
        # Even with city match, admin keywords on umbrella org = drift
        if is_umbrella and admin_hit:
            return {
                **base, "drift": True,
                "reason": (
                    "Page mentions admin/HQ keywords for an umbrella org "
                    "even though city matches."
                ),
            }
        return {**base, **no_drift, "umbrella": is_umbrella, "admin_hit": admin_hit,
                "loc_detail": loc_detail}

    # --- Past this point: city does NOT match ---

    # Umbrella org with any location mismatch = drift
    if is_umbrella:
        if loc_detail["verdict"] in ("different_location", "different_city"):
            return {
                **base, "drift": True,
                "reason": (
                    f"Umbrella org location mismatch: "
                    f"verdict={loc_detail['verdict']}."
                ),
            }
        if loc_detail["zip_conflict"]:
            return {
                **base, "drift": True,
                "reason": "Umbrella org with ZIP conflict and no city match.",
            }
        if admin_hit:
            return {
                **base, "drift": True,
                "reason": (
                    "Umbrella org page with admin/HQ keywords and "
                    "no city match."
                ),
            }
        location_check = _location_consistency_check(site, candidate_text)
        if location_check == "conflict":
            return {
                **base, "drift": True,
                "reason": "Umbrella org with location conflict.",
            }

    # Non-umbrella: admin keywords + no city match = drift
    if admin_hit and not loc_detail["city_match"]:
        return {
            **base, "drift": True,
            "reason": (
                "Page contains admin/HQ keywords with no city match; "
                "likely a central office page."
            ),
        }

    # Non-umbrella: different city + ZIP conflict = drift
    if loc_detail["different_city"] and loc_detail["zip_conflict"]:
        return {
            **base, "drift": True,
            "reason": (
                f"Different city ({loc_detail['different_city']}) "
                f"with ZIP conflict; likely wrong office."
            ),
        }

    # Non-umbrella: different_location verdict (state match + no city match
    # + ZIP conflict) = drift
    if loc_detail["verdict"] == "different_location" and loc_detail["zip_conflict"]:
        return {
            **base, "drift": True,
            "reason": (
                "Page points to a different location with ZIP conflict; "
                "likely wrong office."
            ),
        }

    return {**base, **no_drift, "umbrella": is_umbrella, "admin_hit": admin_hit,
            "loc_detail": loc_detail}


# ---- Extended umbrella patterns (used by both _detect_parent_office_drift
#      and _classify_page_scope for consistent coverage) ----
_UMBRELLA_ORG_PATTERNS: List[str] = [
    "catholic charities", "diocese", "archdiocese", "salvation army",
    "united way", "feeding america", "goodwill", "habitat for humanity",
    "ymca", "ywca", "red cross", "st vincent de paul",
    "knights of columbus", "jewish federation",
    # Additional networked nonprofits
    "community action", "second harvest", "gleaners",
    "society of st. andrew", "meals on wheels",
    "lutheran services", "jewish family services",
    "methodist", "baptist convention", "presbyterian",
    "food bank", "regional food bank",
]

_ADMIN_PAGE_KEYWORDS: List[str] = [
    "headquarters", "main office", "central office",
    "admin office", "administration office", "administrative office",
    "regional office", "national office", "corporate office",
    "home office", "executive office",
]

_BRANCH_FINDER_KEYWORDS: List[str] = [
    "find a location", "find a pantry", "find food",
    "our locations", "all locations", "location finder",
    "branch finder", "find a branch", "our parishes",
    "our sites", "service locations", "our offices",
    "locations near you", "find us",
]


def _classify_page_scope(
    site: Dict[str, Any],
    page_html: Optional[str],
    page_url: Optional[str] = None,
    search_results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Classify whether a source page/URL is:
      - **local_site**: specific to the target entity's physical location
      - **umbrella_office**: central admin / headquarters / parent office
      - **ambiguous**: could be either (not enough signals)

    The classification enables downstream gates to apply the local-site
    preference rule: *prefer local evidence over umbrella-office evidence*
    without suppressing all umbrella data.

    Signals examined:
      1. Admin/HQ keywords in visible page text or URL path
      2. Branch-finder / multi-location page patterns
      3. Umbrella org name in site record
      4. Multiple distinct addresses or phone numbers on the page
      5. Location detail (does the page match this specific site?)

    Returns:
      {
        "scope":          str,   # local_site | umbrella_office | ambiguous
        "is_umbrella_org": bool, # site name matches known umbrella patterns
        "admin_keywords": list,  # which admin keywords were found
        "branch_page":    bool,  # page is a branch-finder / locations page
        "location_match": bool,  # page location matches site's location
        "signals":        list,  # human-readable summary of signals found
      }
    """
    org_name = (site.get("name") or "").lower()
    text = _strip_tags(page_html) if page_html else ""
    text_lc = text.lower()
    url_lc = (page_url or "").lower()

    signals: List[str] = []

    # --- Is this an umbrella-type organization? ---
    is_umbrella_org = any(p in org_name for p in _UMBRELLA_ORG_PATTERNS)

    # --- Admin / HQ keywords in page text or URL ---
    found_admin: List[str] = []
    for kw in _ADMIN_PAGE_KEYWORDS:
        if kw in text_lc or kw in url_lc:
            found_admin.append(kw)
    if found_admin:
        signals.append(f"Admin keywords: {', '.join(found_admin[:3])}")

    # --- Branch finder / multi-location page ---
    is_branch_page = False
    for kw in _BRANCH_FINDER_KEYWORDS:
        if kw in text_lc or kw in url_lc:
            is_branch_page = True
            signals.append(f"Branch-finder keyword: {kw}")
            break

    # --- Multiple distinct addresses on the page ---
    # Count distinct ZIP codes as a proxy for multiple locations
    if page_html:
        zips = _extract_zip_codes(text)
        if len(zips) >= 3:
            signals.append(f"Multiple ZIP codes on page ({len(zips)})")

    # --- Multiple distinct phone numbers ---
    if page_html:
        visible = text
        phone_digits_seen: set = set()
        for pm in _PHONE_RE.finditer(visible):
            d = pm.group(1) + pm.group(2) + pm.group(3)
            if len(d) == 10:
                phone_digits_seen.add(d)
        if len(phone_digits_seen) >= 4:
            signals.append(f"Multiple phone numbers ({len(phone_digits_seen)})")

    # --- URL path hints ---
    # Paths like /about-us, /contact-us, /locations indicate top-level
    # pages that might be admin-level rather than site-specific.
    if page_url:
        from urllib.parse import urlparse as _url_parse
        path = _url_parse(page_url).path.lower()
        admin_paths = ("/about", "/contact", "/locations", "/offices",
                       "/branches", "/find-", "/our-")
        if any(seg in path for seg in admin_paths):
            # Only count as a signal for umbrella orgs (for small orgs,
            # /about and /contact are their own pages, not HQ pages).
            if is_umbrella_org:
                signals.append(f"URL path suggests umbrella page: {path}")

    # --- Location match ---
    loc_detail = _location_match_detail(site, text) if text else None
    location_match = False
    if loc_detail:
        location_match = (
            loc_detail["city_match"]
            and (loc_detail["zip_match"] or loc_detail["street_overlap"] >= 0.3)
        )

    # --- Classify scope ---
    umbrella_signal_count = len(signals)

    if location_match and umbrella_signal_count == 0:
        scope = "local_site"
    elif location_match and umbrella_signal_count <= 1:
        # Location matches even though there's a mild umbrella signal
        # (e.g., umbrella org name but page is about this specific site)
        scope = "local_site"
    elif umbrella_signal_count >= 2:
        scope = "umbrella_office"
    elif umbrella_signal_count == 1 and not location_match:
        scope = "umbrella_office"
    elif is_umbrella_org and not location_match:
        scope = "ambiguous"
    else:
        scope = "ambiguous"

    return {
        "scope": scope,
        "is_umbrella_org": is_umbrella_org,
        "admin_keywords": found_admin,
        "branch_page": is_branch_page,
        "location_match": location_match,
        "signals": signals,
    }


def _entity_drift_verdict(
    site: Dict[str, Any],
    candidate_domain: Optional[str],
    candidate_text: str,
    proposed_value: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Master entity drift check. Combines all guardrails into a single verdict.

    Returns:
      {
        "accept": bool,          # True = OK to propose, False = block
        "reason": str,           # Human-readable explanation
        "name_overlap": float,   # 0.0–1.0
        "location": str,         # "match" | "conflict" | "neutral"
        "location_detail": dict, # rich location match info
        "domain_relevance": str, # "good" | "unrelated" | "directory" | "neutral"
        "parent_drift": bool,    # True if umbrella office drift detected
      }
    """
    org_name = site.get("name") or ""
    name_overlap = _compute_name_overlap(org_name, candidate_text)
    location = _location_consistency_check(site, candidate_text)
    loc_detail = _location_match_detail(site, candidate_text)
    domain_rel = _domain_relevance_check(candidate_domain, org_name) if candidate_domain else "neutral"
    _pd = _detect_parent_office_drift(site, candidate_text, proposed_value or "")
    parent_drift = _pd["drift"]

    # Entity name match check (bidirectional + type conflict)
    _name_result = _entity_name_match(org_name, candidate_text)

    # Decision logic — any hard rejection blocks the proposal
    reasons = []

    base = {
        "name_overlap": name_overlap,
        "location": location,
        "location_detail": loc_detail,
        "domain_relevance": domain_rel,
        "parent_drift": parent_drift,
    }

    # HARD REJECT: entity type conflict (e.g., pantry vs solutions)
    if _name_result.get("type_conflict"):
        return {**base, "accept": False, "reason": _name_result["reason"]}

    # HARD REJECT: name match fails (Jaccard, single-token, weak overlap)
    if not _name_result["accept"]:
        return {**base, "accept": False, "reason": _name_result["reason"]}

    # HARD REJECT: unrelated business domain
    if domain_rel == "unrelated":
        return {
            **base, "accept": False,
            "reason": f"Domain '{candidate_domain}' belongs to an unrelated business category.",
        }

    # HARD REJECT: location conflict (e.g., Midlothian VA vs Brightwater IL)
    if location == "conflict":
        return {
            **base, "accept": False,
            "reason": "Candidate location conflicts with site location.",
        }

    # HARD REJECT: detailed location shows different city/location
    if loc_detail["verdict"] == "different_location":
        return {
            **base, "accept": False,
            "reason": (
                f"Candidate points to a different location"
                f"{' (' + loc_detail['different_state'] + ')' if loc_detail['different_state'] else ''}"
                f"{'; ZIP mismatch' if loc_detail['zip_conflict'] else ''}."
            ),
        }

    if loc_detail["verdict"] == "different_city" and loc_detail["zip_conflict"]:
        return {
            **base, "accept": False,
            "reason": (
                f"Candidate mentions {loc_detail['different_city']} "
                f"(site is in {(site.get('city') or 'unknown')}) with a different ZIP code."
            ),
        }

    # HARD REJECT: parent office drift detected
    if parent_drift:
        return {
            **base, "accept": False,
            "reason": "Candidate appears to be a parent/admin office, not this specific location.",
        }

    # ACCEPT with notes
    if domain_rel == "directory":
        reasons.append("directory page (cannot be proposed as official website)")

    if loc_detail["verdict"] == "different_city":
        reasons.append(f"location caution: candidate may reference {loc_detail['different_city']}")

    return {
        **base, "accept": True,
        "reason": "; ".join(reasons) if reasons else "Entity identity validated.",
    }


# ---------------------------------------------------------------------------
# Phone-specific identity validation helpers
# ---------------------------------------------------------------------------

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def _extract_page_title(page_html: str) -> str:
    """Extract the <title> tag contents from HTML. Returns '' if none found."""
    if not page_html:
        return ""
    m = _TITLE_RE.search(page_html)
    if m:
        title = re.sub(r"<[^>]+>", "", m.group(1))
        title = re.sub(r"&[^;]+;", " ", title)
        return re.sub(r"\s+", " ", title).strip()
    return ""


# US area code → state abbreviation mapping (compact).
# Not exhaustive for every overlay code but covers the vast majority.
_STATE_AREA_CODES_RAW: Dict[str, str] = {
    "AL": "205 251 256 334 938",
    "AK": "907",
    "AZ": "480 520 602 623 928",
    "AR": "479 501 870",
    "CA": "209 213 279 310 323 341 350 408 415 424 442 510 530 559 562 619 626 628 650 657 661 669 707 714 747 760 805 818 831 858 909 916 925 949 951",
    "CO": "303 719 720 970",
    "CT": "203 475 860 959",
    "DE": "302",
    "DC": "202",
    "FL": "239 305 321 352 386 407 561 727 754 772 786 813 850 863 904 941 954",
    "GA": "229 404 470 478 678 706 762 770 912 943",
    "HI": "808",
    "ID": "208 986",
    "IL": "217 224 309 312 331 447 464 618 630 708 773 779 815 847 872",
    "IN": "219 260 317 463 574 765 812 930",
    "IA": "319 515 563 641 712",
    "KS": "316 620 785 913",
    "KY": "270 364 502 606 859",
    "LA": "225 318 337 504 985",
    "ME": "207",
    "MD": "240 301 410 443 667",
    "MA": "339 351 413 508 617 774 781 857 978",
    "MI": "231 248 269 313 517 586 616 734 810 906 947 989",
    "MN": "218 320 507 612 651 763 952",
    "MS": "228 601 662 769",
    "MO": "314 417 573 636 660 816",
    "MT": "406",
    "NE": "308 402 531",
    "NV": "702 725 775",
    "NH": "603",
    "NJ": "201 551 609 732 848 856 862 908 973",
    "NM": "505 575",
    "NY": "212 315 332 347 516 518 585 607 631 646 680 716 718 838 845 914 917 929 934",
    "NC": "252 336 704 743 828 910 919 980 984",
    "ND": "701",
    "OH": "216 220 234 283 326 330 380 419 440 513 567 614 740 937",
    "OK": "405 539 580 918",
    "OR": "458 503 541 971",
    "PA": "215 223 267 272 412 445 484 570 610 717 724 814 835 878",
    "PR": "787 939",
    "RI": "401",
    "SC": "803 843 854 864",
    "SD": "605",
    "TN": "423 615 629 731 865 901 931",
    "TX": "210 214 254 281 325 346 361 409 430 432 469 512 682 713 726 737 806 817 830 832 903 915 936 940 956 972 979",
    "UT": "385 435 801",
    "VT": "802",
    "VA": "276 434 540 571 703 757 804",
    "WA": "206 253 360 425 509 564",
    "WV": "304 681",
    "WI": "262 414 534 608 715 920",
    "WY": "307",
}
_AREA_CODE_STATE: Dict[str, str] = {}
for _st, _codes in _STATE_AREA_CODES_RAW.items():
    for _ac in _codes.split():
        _AREA_CODE_STATE[_ac] = _st


def _check_phone_area_code(phone_digits: str, site_state: str) -> str:
    """
    Check if a phone number's area code belongs to the site's state.

    Returns:
      "match"    - area code belongs to the site's state
      "mismatch" - area code belongs to a different state
      "unknown"  - area code not in mapping or insufficient info
    """
    if not phone_digits or len(phone_digits) < 3 or not site_state:
        return "unknown"
    area_code = phone_digits[:3]
    state_upper = site_state.upper().strip()
    if len(state_upper) != 2:
        return "unknown"
    mapped_state = _AREA_CODE_STATE.get(area_code)
    if not mapped_state:
        return "unknown"
    return "match" if mapped_state == state_upper else "mismatch"


def _phone_proposal_gate(
    site: Dict[str, Any],
    page_text: str,
    candidate: Dict[str, Any],
    name_overlap_score: float,
    name_match: bool,
    location_match: bool,
    shared_site: bool,
    xref: str,
    search_results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Comprehensive phone proposal identity gate.  Evaluates whether a phone
    candidate should be promoted, downgraded, or rejected based on:

      1. Entity name overlap (page title + visible text)
      2. Area code vs site state
      3. Source quality (official page, corroborated, directory, weak)
      4. Parent office drift
      5. Location consistency

    Returns:
      {
        "accept":   bool,   # False → block (suspect_entity_match)
        "downgrade": bool,  # True → force proposed_update_low_confidence
        "reason":   str,
        "name_overlap": float,
        "area_code":    str,   # match | mismatch | unknown
        "source_quality": str, # official | corroborated | strong_page_match |
                               #   partial_match | directory_only | search_only | weak
        "parent_drift":  bool,
        "location":      str,  # match | conflict | neutral
      }
    """
    org_name = site.get("name") or ""
    site_state = (site.get("state") or "").strip().upper()

    # --- Area code ---
    ac_check = _check_phone_area_code(candidate.get("digits", ""), site_state)

    # --- Domain relevance ---
    page_domain = _domain_of(
        site.get("website") or site.get("publicWebsite") or ""
    )
    domain_rel = (
        _domain_relevance_check(page_domain, org_name)
        if page_domain else "neutral"
    )

    # --- Source quality classification ---
    is_structured = candidate.get("from_structured_data", False)
    is_search_only = (
        candidate.get("from_search", False)
        and not candidate.get("from_search_corroborated", False)
    )
    is_corroborated = (
        candidate.get("from_search_corroborated", False)
        or xref == "proposed"
    )

    if is_structured:
        source_quality = "official"
    elif domain_rel == "good" and name_overlap_score >= 0.4:
        source_quality = "official"
    elif is_corroborated and name_match:
        source_quality = "corroborated"
    elif domain_rel == "directory":
        source_quality = "directory_only"
    elif is_search_only:
        source_quality = "search_only"
    elif name_match and location_match:
        source_quality = "strong_page_match"
    elif name_match:
        source_quality = "partial_match"
    else:
        source_quality = "weak"

    # --- Parent office drift ---
    _pd = _detect_parent_office_drift(
        site, page_text or "", candidate.get("display", "")
    )
    parent_drift = _pd["drift"]

    # --- Location consistency ---
    location = _location_consistency_check(site, page_text or "")
    loc_detail = _location_match_detail(site, page_text or "")

    base = {
        "name_overlap": name_overlap_score,
        "area_code": ac_check,
        "source_quality": source_quality,
        "parent_drift": parent_drift,
        "location": location,
        "location_detail": loc_detail,
    }

    # ===== HARD REJECT rules =====

    # Unrelated business domain
    if domain_rel == "unrelated":
        return {
            **base, "accept": False, "downgrade": False,
            "reason": f"Domain '{page_domain}' belongs to an unrelated business category.",
        }

    # Parent/admin office drift
    if parent_drift:
        return {
            **base, "accept": False, "downgrade": False,
            "reason": f"Phone appears to belong to a parent/admin office: {_pd['reason']}",
        }

    # Location conflict + area code mismatch (double signal)
    if location == "conflict" and ac_check == "mismatch":
        return {
            **base, "accept": False, "downgrade": False,
            "reason": "Phone area code and page location both conflict with site location.",
        }

    # Different location with area code mismatch (address-level conflict)
    if loc_detail["verdict"] == "different_location" and ac_check == "mismatch":
        return {
            **base, "accept": False, "downgrade": False,
            "reason": (
                f"Page location points to a different area"
                f"{' (' + loc_detail['different_state'] + ')' if loc_detail['different_state'] else ''}"
                f" and phone area code does not match site state."
            ),
        }

    # Different city + ZIP conflict (same umbrella, wrong campus)
    if loc_detail["different_city"] and loc_detail["zip_conflict"]:
        return {
            **base, "accept": False, "downgrade": False,
            "reason": (
                f"Page references {loc_detail['different_city']} with a different ZIP code "
                f"(site is in {(site.get('city') or 'unknown')}); likely wrong office/campus."
            ),
        }

    # Very weak name match + no positive domain signal + not structured
    if name_overlap_score < 0.3 and domain_rel not in ("good",) and not is_structured:
        return {
            **base, "accept": False, "downgrade": False,
            "reason": f"Weak entity name match ({name_overlap_score:.0%}) with no positive domain signal.",
        }

    # Search-only source with no name match on the snippet
    if is_search_only and not name_match:
        return {
            **base, "accept": False, "downgrade": False,
            "reason": "Phone found in search snippet only with no entity name match.",
        }

    # ===== DOWNGRADE rules (accept but force low_confidence) =====

    # Area code mismatch — always downgrade, even for "official" sources.
    # Structured data from a page in a different state (e.g. a different
    # branch of a multi-location chain) is still wrong-location data and
    # MUST NOT be auto-promoted at full confidence.
    if ac_check == "mismatch":
        return {
            **base, "accept": True, "downgrade": True,
            "reason": "Phone area code maps to a different state than site; downgraded for review.",
        }

    # Different city in same state (no ZIP conflict — softer signal)
    if loc_detail["different_city"] and not loc_detail["city_match"]:
        if source_quality not in ("official", "corroborated"):
            return {
                **base, "accept": True, "downgrade": True,
                "reason": (
                    f"Page may reference {loc_detail['different_city']} "
                    f"(site is in {(site.get('city') or 'unknown')}); downgraded for review."
                ),
            }

    # ZIP conflict without city confirmation
    if loc_detail["zip_conflict"] and not loc_detail["city_match"]:
        if source_quality not in ("official", "corroborated"):
            return {
                **base, "accept": True, "downgrade": True,
                "reason": "Page ZIP code does not match site; possible wrong-office source.",
            }

    # Directory-only source — not strong enough for a correction
    if source_quality == "directory_only":
        return {
            **base, "accept": True, "downgrade": True,
            "reason": "Phone found on directory page only; not strong enough for full confidence.",
        }

    # Weak source without corroboration or structured data
    if source_quality == "weak":
        return {
            **base, "accept": True, "downgrade": True,
            "reason": "Phone source has weak identity signals; needs corroboration.",
        }

    # Location conflict alone (without area code double-signal)
    if location == "conflict" and source_quality not in ("official", "corroborated"):
        return {
            **base, "accept": True, "downgrade": True,
            "reason": "Page location may conflict with site; downgraded for review.",
        }

    # ===== ACCEPT =====
    return {
        **base, "accept": True, "downgrade": False,
        "reason": "Phone identity validated.",
    }


# ---------------------------------------------------------------------------
# Website-specific identity validation gate
# ---------------------------------------------------------------------------

def _website_proposal_gate(
    site: Dict[str, Any],
    discovery: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Comprehensive website proposal identity gate.  Evaluates whether a
    discovered website URL should be promoted as the official website.

    Uses the rich discovery dict (url, domain, score, confidence, reason,
    candidates with content_matches/city_match) to make a thorough decision
    instead of relying only on the domain name.

    Returns:
      {
        "accept":    bool,   # False = block (suspect_entity_match)
        "downgrade": bool,   # True  = force proposed_update_low_confidence
        "reason":    str,
        "domain_relevance": str,  # good | unrelated | directory | neutral
        "name_overlap":     float,
        "location":         str,  # match | conflict | neutral
      }
    """
    org_name = site.get("name") or ""
    url = discovery.get("url") or ""
    domain = _domain_of(url) or discovery.get("domain") or ""

    # --- Domain relevance ---
    domain_rel = _domain_relevance_check(domain, org_name) if domain else "neutral"

    # --- Name overlap: use domain text + reason + candidate data ---
    composite_parts = [domain, discovery.get("reason", "")]
    for c in discovery.get("candidates", []):
        composite_parts.append(c.get("url", ""))
        composite_parts.append(c.get("domain", ""))
    composite_text = " ".join(composite_parts)
    name_overlap = _compute_name_overlap(org_name, composite_text)

    # Also check how many org-name tokens appear in the bare domain
    name_tokens = _tokens_from_name(org_name)
    domain_clean = re.sub(r"[^a-z0-9]", "", domain.lower()) if domain else ""
    domain_token_hits = sum(1 for t in name_tokens if t in domain_clean)

    # Entity name match — bidirectional + type conflict detection.
    # Expand domain into individual words so concatenated domains like
    # "hopefoodpantry.org" are recognized as containing "hope", "food",
    # "pantry" tokens.  Without this, _entity_name_match normalizes the
    # domain as a single opaque token and misses the match.
    _domain_expanded = domain_clean  # already lowercased, no punctuation
    # Insert spaces before org-name tokens found as substrings in domain
    for t in name_tokens:
        if t in _domain_expanded:
            _domain_expanded = _domain_expanded.replace(t, f" {t} ")
    _domain_expanded = re.sub(r"\s+", " ", _domain_expanded).strip()
    _ent_text = _domain_expanded + " " + discovery.get("reason", "")
    _ent_match = _entity_name_match(org_name, _ent_text)

    # --- Content verification from discovery candidates ---
    best_candidate = {}
    if discovery.get("candidates"):
        best_candidate = discovery["candidates"][0]
    content_matches = best_candidate.get("content_matches", 0)
    city_match = best_candidate.get("city_match", False)
    disc_score = discovery.get("score", 0)

    # --- Location consistency ---
    # Prefer the actual fetched page HTML for location checks — it
    # contains the real address / footer text (e.g. "Riverton, SC
    # 29707") which is invisible in the domain-only composite_text.
    _page_html = (best_candidate.get("page_html") or "") if best_candidate else ""
    _loc_text = _page_html if _page_html else composite_text
    location = _location_consistency_check(site, _loc_text)
    loc_detail = _location_match_detail(site, _loc_text)

    # --- Parent office drift ---
    _pd = _detect_parent_office_drift(
        site, _loc_text, url,
    )
    parent_drift = _pd["drift"]

    # --- Page scope classification ---
    _page_scope = _classify_page_scope(
        site,
        _page_html if _page_html else None,
        page_url=url,
    )

    base = {
        "domain_relevance": domain_rel,
        "name_overlap": name_overlap,
        "location": location,
        "location_detail": loc_detail,
        "parent_drift": parent_drift,
        "page_scope": _page_scope["scope"],
    }

    # ===== HARD REJECT rules =====

    # Entity type conflict (e.g., pantry vs tech/dental/law)
    if _ent_match.get("type_conflict"):
        return {
            **base, "accept": False, "downgrade": False,
            "reason": f"Entity type conflict: {_ent_match['reason']}",
        }

    # Entity name match fails (Jaccard, single-token, weak overlap)
    # BUT: skip this rejection when the domain itself contains org-name
    # tokens AND the page has content verification — the domain proves
    # ownership even when the normalized name is very short (e.g., "Hope
    # Food Pantry" normalizes to just "hope", but hopefoodpantry.org
    # clearly belongs to them).
    _domain_verified = domain_token_hits >= 1 and (content_matches > 0 or city_match)
    if not _ent_match["accept"] and not _domain_verified:
        return {
            **base, "accept": False, "downgrade": False,
            "reason": f"Entity name mismatch: {_ent_match['reason']}",
        }

    # PART 1: Directory domains must NEVER become official websites
    if domain_rel == "directory":
        return {
            **base, "accept": False, "downgrade": False,
            "reason": f"Domain '{domain}' is a directory/listing site, not an official website.",
        }

    # PART 2: Unrelated business domain
    if domain_rel == "unrelated":
        return {
            **base, "accept": False, "downgrade": False,
            "reason": f"Domain '{domain}' belongs to an unrelated business category.",
        }

    # PART 3: Location conflict with no content verification
    if location == "conflict" and not city_match and content_matches == 0:
        return {
            **base, "accept": False, "downgrade": False,
            "reason": "Discovered website points to a different location with no content verification.",
        }

    # PART 3b: Detailed location → different location entirely
    if loc_detail["verdict"] == "different_location" and not city_match:
        return {
            **base, "accept": False, "downgrade": False,
            "reason": (
                f"Discovered website points to a different location"
                f"{' (' + loc_detail['different_state'] + ')' if loc_detail['different_state'] else ''}"
                f" with no city match on page."
            ),
        }

    # PART 3c: Different city in same state + no city match on page
    if loc_detail["different_city"] and loc_detail["zip_conflict"] and not city_match:
        return {
            **base, "accept": False, "downgrade": False,
            "reason": (
                f"Website references {loc_detail['different_city']} "
                f"(site is in {(site.get('city') or 'unknown')}) with a different ZIP code."
            ),
        }

    # PART 4: Very weak entity match — no domain token overlap AND low
    # content/name overlap AND discovery score is mediocre
    if domain_token_hits == 0 and name_overlap < 0.3 and disc_score < 0.7:
        return {
            **base, "accept": False, "downgrade": False,
            "reason": f"Domain has no org-name tokens and weak entity match ({name_overlap:.0%}).",
        }

    # PART 4 cont: No content verification at all AND domain doesn't match
    if content_matches == 0 and not city_match and domain_token_hits == 0:
        return {
            **base, "accept": False, "downgrade": False,
            "reason": "No on-page content verification and domain does not match entity name.",
        }

    # PART 5: Parent/admin office drift — website belongs to umbrella HQ
    if parent_drift:
        return {
            **base, "accept": False, "downgrade": False,
            "reason": f"Website appears to belong to a parent/admin office: {_pd['reason']}",
        }

    # ===== DOWNGRADE rules (accept but force low_confidence) =====

    # Umbrella office page scope — page is classified as central/admin
    # but didn't trigger a hard reject (e.g., location is neutral rather
    # than conflicting).  Downgrade so a human reviews it.
    if _page_scope["scope"] == "umbrella_office" and not city_match:
        return {
            **base, "accept": True, "downgrade": True,
            "reason": (
                f"Website page classified as umbrella/admin office "
                f"({'; '.join(_page_scope['signals'][:2])}); needs review."
            ),
        }

    # Location conflict when there IS some content match
    if location == "conflict" and (city_match or content_matches > 0):
        return {
            **base, "accept": True, "downgrade": True,
            "reason": "Location may conflict; page has some content match but needs review.",
        }

    # Different city detected (softer signal — no ZIP conflict)
    if loc_detail["different_city"] and not loc_detail["city_match"]:
        return {
            **base, "accept": True, "downgrade": True,
            "reason": (
                f"Website may reference {loc_detail['different_city']} "
                f"(site is in {(site.get('city') or 'unknown')}); needs review."
            ),
        }

    # ZIP conflict without city confirmation — possible wrong-campus
    if loc_detail["zip_conflict"] and not loc_detail["city_match"]:
        return {
            **base, "accept": True, "downgrade": True,
            "reason": "Website ZIP code does not match site; possible wrong-office source.",
        }

    # Weak content verification: domain matches but page didn't verify
    if content_matches == 0 and not city_match and domain_token_hits >= 1:
        return {
            **base, "accept": True, "downgrade": True,
            "reason": "Domain matches entity name but page content is unverified.",
        }

    # Neutral domain (no nonprofit signals, no name tokens in domain)
    # with only partial content match
    if domain_rel == "neutral" and content_matches < 2 and not city_match:
        return {
            **base, "accept": True, "downgrade": True,
            "reason": "Domain has no clear nonprofit signal; partial content match only.",
        }

    # ===== ACCEPT =====
    return {
        **base, "accept": True, "downgrade": False,
        "reason": "Website identity validated.",
    }


def _domain_of(url: str) -> Optional[str]:
    try:
        netloc = _urlparse.urlparse(url).netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc or None
    except Exception:
        return None


def _score_candidate(
    url: str,
    name_tokens: set,
    content_matches: int = 0,
    city_match: bool = False,
    zip_match: bool = False,
    street_overlap: float = 0.0,
) -> float:
    """
    Heuristic score for a candidate official-site URL. Returns 0 if rejected.
    `content_matches` is the count of distinctive name tokens found in the
    fetched homepage body, used to verify the candidate is genuinely related.
    `city_match` indicates whether the site's city appears in the page body
    (a strong disambiguator - a generic national org won't mention the city).
    `zip_match` indicates whether the site's ZIP code appears on the page.
    `street_overlap` is the fraction of street address tokens matched (0–1).
    """
    domain = _domain_of(url)
    if not domain:
        return 0.0
    if domain in _DISCOVERY_BLOCKLIST:
        return 0.0
    for bad in _DISCOVERY_BLOCKLIST:
        if domain.endswith("." + bad):
            return 0.0

    score = 0.0
    if domain.endswith(".org"):
        score += 0.4
    elif domain.endswith(".com"):
        score += 0.25
    elif domain.endswith(".net"):
        score += 0.15
    else:
        score += 0.05

    # Token overlap between site name and the domain core.
    core = domain.rsplit(".", 1)[0]
    core_clean = re.sub(r"[^a-z0-9]", "", core)
    matches = sum(1 for t in name_tokens if t in core_clean)
    if name_tokens:
        score += 0.5 * min(matches / max(len(name_tokens), 1), 1.0)
        if matches >= 2:
            score += 0.1

    # Prefer root domains over deep paths.
    path = _urlparse.urlparse(url).path or ""
    if path in ("", "/"):
        score += 0.05
    elif path.count("/") > 3:
        score -= 0.1

    # Content verification: did the fetched page mention the org?
    if content_matches >= 2:
        score += 0.2
    elif content_matches >= 1:
        score += 0.1
    else:
        score -= 0.10

    # City disambiguator: a true local org's homepage almost always names
    # its city. A generic national org with a similar name will not.
    if city_match:
        score += 0.15

    # Local site preference: ZIP code match is a strong signal the page
    # refers to the exact physical location, not a different campus.
    if zip_match:
        score += 0.10

    # Street address overlap: even partial overlap (e.g., building number)
    # further confirms this is the right branch/location.
    if street_overlap >= 0.5:
        score += 0.10
    elif street_overlap >= 0.25:
        score += 0.05

    return max(score, 0.0)


def _candidate_domains(tokens: list, city: str) -> list:
    """
    Build a deduplicated, ordered list of plausible domain names from the
    distinctive name tokens (and optionally a city for disambiguation).
    """
    if not tokens:
        return []

    bases: list = []
    seen_bases: set = set()

    def _add_base(b: str) -> None:
        if not b or len(b) < 4 or b in seen_bases:
            return
        seen_bases.add(b)
        bases.append(b)

    # Full token concatenation.
    _add_base("".join(tokens))
    # First two tokens (e.g. "helpinghands" from "Helping Hands Food Pantry").
    if len(tokens) >= 2:
        _add_base(tokens[0] + tokens[1])
    # Hyphenated full form.
    _add_base("-".join(tokens))
    # City-suffixed disambiguator (only if city isn't already in tokens).
    city_clean = re.sub(r"[^a-z0-9]", "", (city or "").lower())
    if city_clean and len(city_clean) >= 3 and city_clean not in tokens:
        _add_base("".join(tokens) + city_clean)
        if len(tokens) >= 2:
            _add_base(tokens[0] + tokens[1] + city_clean)

    # Cross with TLDs.
    domains: list = []
    seen_domains: set = set()
    for base in bases:
        for tld in _DISCOVERY_TLDS:
            d = base + tld
            if d in seen_domains:
                continue
            seen_domains.add(d)
            domains.append(d)
    return domains


def _probe_candidate(url: str, ctx: Optional[BatchContext]) -> Optional[Dict[str, Any]]:
    """
    Bounded GET probe used during discovery. Returns {status, text, final_url}
    on success, or None on any failure (DNS, timeout, non-2xx/3xx, etc.).
    Intentionally quiet (no per-attempt logging) since many candidates miss.
    """
    if not HAS_REQUESTS:
        return None
    session = ctx.session if (ctx and ctx.session is not None) else requests
    try:
        resp = session.get(
            url,
            timeout=_DISCOVERY_PROBE_TIMEOUT,
            allow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.1"},
        )
    except Exception:
        return None
    try:
        if not (200 <= resp.status_code < 400):
            return None
        body = resp.content[:_DISCOVERY_PROBE_MAX_BYTES] if resp.content else b""
        try:
            text = body.decode(resp.encoding or "utf-8", errors="ignore")
        except (LookupError, AttributeError, TypeError):
            text = body.decode("utf-8", errors="ignore")
        if ctx is not None:
            with ctx.lock:
                ctx.requests_made += 1
                # Seed the page-text cache so phone / address extractors can
                # mine discovered-website probes without re-fetching.
                canon = _canonical_url(resp.url) if resp.url else None
                if canon and text:
                    ctx.page_text_cache.setdefault(canon, text)
        return {"status": resp.status_code, "text": text, "final_url": resp.url}
    finally:
        try:
            resp.close()
        except Exception:
            pass


def _email_domain_extract(email: str) -> Optional[str]:
    """Return the bare lowercase domain from an email, or None if unusable.

    Returns None for free email providers (gmail, yahoo, etc.) and for
    blocklisted domains - those cannot represent an organization's site.
    """
    if not email or "@" not in email:
        return None
    try:
        _local, domain = email.rsplit("@", 1)
    except ValueError:
        return None
    domain = domain.strip().lower().rstrip(".")
    if not domain or "." not in domain:
        return None
    if domain in _FREE_EMAIL_DOMAINS:
        return None
    if domain in _DISCOVERY_BLOCKLIST:
        return None
    for bad in _DISCOVERY_BLOCKLIST:
        if domain.endswith("." + bad):
            return None
    return domain


def _discover_website_from_email(
    site: Dict[str, Any],
    site_label: str,
    ctx: Optional[BatchContext] = None,
    avoid_domain: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Derive a likely official website from the org's `publicEmail` domain.

    When an organization uses a custom-domain email like
    `contact@example.org`, the email domain is almost always the org's
    own website. This is a much stronger signal than name-token guessing,
    so we try it first.

    Steps:
      1. Pull `publicEmail` (or `email`); skip free providers (gmail, etc).
      2. Construct `https://<domain>/` and probe with a bounded GET.
      3. Verify the homepage actually loads. Where the org's name tokens
         or city appear on the page, classify as high quality. Otherwise
         (reachable but unverified) surface as low quality - guards
         against parked vanity domains.
      4. Return a discovery dict in the same shape as `_discover_website`.

    `avoid_domain` lets the caller skip when the org's current (broken)
    website lives at the same domain as their email - in that case, the
    alternative wouldn't differ.
    """
    if not HAS_REQUESTS:
        return None

    email = (site.get("publicEmail") or site.get("email") or "").strip()
    domain = _email_domain_extract(email)
    if not domain:
        return None
    if avoid_domain and domain == avoid_domain.lower():
        return None

    name = (site.get("name") or "").strip()
    city = (site.get("city") or "").strip()
    tokens_set = _tokens_from_name(name)

    # Cache key is the bare email domain; identical domains across sites
    # in the same batch should reuse the probe.
    cache_key = f"email:{domain}"
    if ctx is not None:
        with ctx.lock:
            if cache_key in ctx.discovery_cache:
                ctx.cache_hits += 1
                return ctx.discovery_cache[cache_key]
        ctx.discovery_attempts += 1

    probe = None
    for scheme in ("https", "http"):
        probe = _probe_candidate(f"{scheme}://{domain}", ctx)
        if probe is not None:
            break

    if probe is None:
        if ctx is not None:
            with ctx.lock:
                ctx.discovery_cache[cache_key] = None
        return None

    final_url = probe.get("final_url") or f"https://{domain}"
    page_text_lc = (probe.get("text") or "").lower()
    city_lc = city.lower().strip() if city else ""
    content_matches = sum(1 for t in tokens_set if t in page_text_lc)
    city_match = bool(city_lc and len(city_lc) >= 3 and city_lc in page_text_lc)

    # Local site preference: check ZIP and street address against page
    _page_text_raw = probe.get("text") or ""
    site_zip = (site.get("zip") or "").strip()
    site_zip5 = site_zip[:5] if len(site_zip) >= 5 else ""
    site_address = (site.get("streetAddress") or "").strip()
    _email_zip_match = bool(site_zip5 and site_zip5 in _extract_zip_codes(_page_text_raw))
    _email_street_overlap = _street_token_overlap(site_address, _page_text_raw)

    # Email-domain discovery starts with a confidence floor because the
    # signal itself (custom-domain email) is strong. Final tier depends on
    # independent verification (city / org-name tokens appear on page).
    if city_match or (tokens_set and content_matches >= len(tokens_set)):
        confidence = 0.92
        reason = "discovered_via_email_domain (locality / full-name verified)"
        high_quality = True
    elif content_matches >= 1:
        confidence = 0.88
        reason = "discovered_via_email_domain (partial content match)"
        high_quality = True
    else:
        # Reachable, but no on-page evidence the domain belongs to this org.
        # Could be a parked vanity domain - surface as low confidence.
        confidence = 0.6
        reason = "discovered_via_email_domain (reachable, content unverified)"
        high_quality = False

    final_domain = _domain_of(final_url) or domain
    score = (
        0.4
        + 0.5 * min(content_matches / max(len(tokens_set), 1), 1.0)
        + (0.15 if city_match else 0.0)
        + (0.10 if _email_zip_match else 0.0)
        + (0.10 if _email_street_overlap >= 0.5 else 0.05 if _email_street_overlap >= 0.25 else 0.0)
    )
    result = {
        "url": final_url,
        "domain": final_domain,
        "score": round(score, 2),
        "confidence": confidence,
        "reason": reason,
        "high_quality": high_quality,
        "source": "email_domain",
        "email_domain": domain,
        "candidates": [{
            "url": final_url,
            "domain": final_domain,
            "content_matches": content_matches,
            "city_match": city_match,
            "zip_match": _email_zip_match,
            "street_overlap": _email_street_overlap,
            "status": probe.get("status"),
            "source": "email_domain",
            "page_html": probe.get("text") or "",
        }],
    }

    if ctx is not None:
        with ctx.lock:
            if high_quality:
                ctx.discovery_hits += 1
            ctx.discovery_cache[cache_key] = result

    return result


def _discover_website(
    site: Dict[str, Any],
    site_label: str,
    ctx: Optional[BatchContext] = None,
    search_results: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Discover a likely official website for a site that has no website on
    record. Generates plausible domain candidates from the site name and
    HEAD/GET-probes them. Returns a discovery dict or None:

      {
        "url": "<best candidate>",
        "domain": "<bare domain>",
        "score": float,           # heuristic 0..~1.3
        "confidence": float,      # mapped to 0.45..0.92
        "reason": str,
        "high_quality": bool,
        "candidates": [...]       # top few for debug
      }

    When `search_results` are provided (from `_perform_site_search`), the
    URLs they contain are added to the candidate pool. Search-derived URLs
    are still probed and scored by the same heuristic - they're never
    auto-trusted; they just widen the set of candidates considered.
    """
    if not HAS_REQUESTS:
        return None

    name = (site.get("name") or "").strip()
    if not name:
        return None
    city = (site.get("city") or "").strip()

    tokens_list = _tokens_list_from_name(name)
    if not tokens_list:
        return None
    tokens_set = set(tokens_list)

    # Cache key is the org name + city so duplicate sites don't re-probe.
    # Include a marker if search candidates were supplied so a later run
    # without them doesn't reuse a degraded cache entry.
    cache_key_suffix = "|s" if search_results else ""
    cache_key = f"{name.lower()}|{city.lower()}{cache_key_suffix}"
    if ctx is not None:
        with ctx.lock:
            if cache_key in ctx.discovery_cache:
                ctx.cache_hits += 1
                return ctx.discovery_cache[cache_key]
        ctx.discovery_attempts += 1

    name_token_candidates = _candidate_domains(tokens_list, city)[:_DISCOVERY_MAX_PROBES]

    # Build the unified candidate URL list: name-token probes first
    # (deterministic, cheap), then search-derived URLs deduped against them.
    candidates: List[Dict[str, Any]] = []
    seen_urls: set = set()
    for domain in name_token_candidates:
        # Two schemes per name-token candidate are tried inside the probe loop
        # below; tag with source for downstream debug.
        for scheme in ("https", "http"):
            url = f"{scheme}://{domain}"
            canon = _canonical_url(url)
            if canon and canon in seen_urls:
                continue
            if canon:
                seen_urls.add(canon)
            candidates.append({"url": url, "source": "name_tokens"})
            # Only one scheme variant is enqueued; _probe_candidate retries.
            break

    if search_results:
        for item in search_results:
            url = item.get("url")
            if not url:
                continue
            domain = _domain_of(url) or ""
            if not domain:
                continue
            # Drop obvious aggregators / social up front so we don't waste a probe.
            if domain in _DISCOVERY_BLOCKLIST or any(
                domain.endswith("." + bad) for bad in _DISCOVERY_BLOCKLIST
            ):
                continue
            canon = _canonical_url(url)
            if canon and canon in seen_urls:
                continue
            if canon:
                seen_urls.add(canon)
            candidates.append({"url": url, "source": "web_search"})

    if not candidates:
        if ctx is not None:
            with ctx.lock:
                ctx.discovery_cache[cache_key] = None
        return None

    scored = []
    city_lc = city.lower().strip() if city else ""
    site_zip = (site.get("zip") or "").strip()
    site_zip5 = site_zip[:5] if len(site_zip) >= 5 else ""
    site_address = (site.get("streetAddress") or "").strip()
    for cand in candidates:
        probe_url = cand["url"]
        probe = _probe_candidate(probe_url, ctx)
        if probe is None and cand["source"] == "name_tokens":
            # Name-token domains: also try http if https failed.
            alt = probe_url.replace("https://", "http://", 1)
            if alt != probe_url:
                probe = _probe_candidate(alt, ctx)
        if probe is None:
            continue
        final_url = probe.get("final_url") or probe_url
        page_text_lc = (probe.get("text") or "").lower()
        content_matches = sum(1 for t in tokens_set if t in page_text_lc)
        # City verification: does the candidate page mention the org's city?
        city_match = bool(city_lc and len(city_lc) >= 3 and city_lc in page_text_lc)
        # Local site preference: ZIP and street address matching
        _page_text_raw = probe.get("text") or ""
        _cand_zip_match = bool(site_zip5 and site_zip5 in _extract_zip_codes(_page_text_raw))
        _cand_street_overlap = _street_token_overlap(site_address, _page_text_raw)
        score = _score_candidate(
            final_url,
            tokens_set,
            content_matches=content_matches,
            city_match=city_match,
            zip_match=_cand_zip_match,
            street_overlap=_cand_street_overlap,
        )
        if score <= 0:
            continue
        scored.append({
            "score": score,
            "url": final_url,
            "domain": _domain_of(final_url) or _domain_of(probe_url) or "",
            "content_matches": content_matches,
            "city_match": city_match,
            "zip_match": _cand_zip_match,
            "street_overlap": _cand_street_overlap,
            "status": probe.get("status"),
            "source": cand["source"],
            "page_html": probe.get("text") or "",
        })

    if not scored:
        result = None
    else:
        scored.sort(key=lambda x: x["score"], reverse=True)
        best = scored[0]

        # Verification check - relaxed to allow partial token matches.
        # "verified" means there is *some* independent on-page evidence
        # that this candidate is related to the org, not that every single
        # name token and the city appear. A single distinctive name token
        # on the page, OR the city mentioned, is sufficient.
        verified = best["city_match"] or (
            best["content_matches"] >= 1
        )

        # Domain-name match: does the domain contain at least 2 name tokens?
        # This is a strong structural signal independent of page content.
        domain_core = re.sub(r"[^a-z0-9]", "", (best["domain"] or "").rsplit(".", 1)[0])
        domain_token_hits = sum(1 for t in tokens_set if t in domain_core) if domain_core else 0
        domain_match = domain_token_hits >= 2

        if best["score"] >= 0.9 and verified:
            confidence = 0.92
            reason = "discovered_via_probe (strong name+content+locality match)"
            high_quality = True
        elif best["score"] >= 0.7 and verified:
            confidence = 0.85
            reason = "discovered_via_probe (name+content match, verified)"
            high_quality = True
        elif best["score"] >= 0.6 and (domain_match or verified):
            # Domain matches org name OR page has partial content match.
            # Page loaded successfully (we have a probe result). -> propose.
            confidence = 0.78
            reason = "discovered_via_probe (domain/partial match, page loads)"
            high_quality = True
        elif best["score"] >= 0.5 and domain_match:
            # Domain aligns with org name but weaker overall score.
            # Surface as proposed_update_low_confidence for review.
            confidence = 0.65
            reason = "discovered_via_probe (domain match, lower confidence)"
            high_quality = False  # will surface as proposed_update_low_confidence
        elif best["score"] >= 0.5:
            confidence = 0.55
            reason = "discovered_via_probe (partial match)"
            high_quality = False
        else:
            confidence = 0.4
            reason = "discovered_via_probe (weak match)"
            high_quality = False

        result = {
            "url": best["url"],
            "domain": best["domain"],
            "score": round(best["score"], 2),
            "confidence": confidence,
            "reason": reason,
            "high_quality": high_quality,
            "candidates": [
                {
                    "url": c["url"],
                    "domain": c["domain"],
                    "score": round(c["score"], 2),
                    "content_matches": c["content_matches"],
                    "city_match": c["city_match"],
                    "source": c.get("source", "name_tokens"),
                    "page_html": c.get("page_html", ""),
                }
                for c in scored[:5]
            ],
        }
        if ctx is not None and high_quality:
            with ctx.lock:
                ctx.discovery_hits += 1

    if ctx is not None:
        with ctx.lock:
            ctx.discovery_cache[cache_key] = result

    return result


# ---------------------------------------------------------------------------
# Phone extraction
# ---------------------------------------------------------------------------
#
# Mines candidate phone numbers from a fetched homepage and scores each by
# context (proximity to "phone"/"call"/"contact" keywords, `tel:` href use,
# placement in footer / contact sections, repetition).
#
# Used by the phone evidence stage to decide:
#   - confirmed:       a candidate's digits match the stored phone
#   - proposed_update: a strong (>=0.85) candidate's digits differ from stored
#   - uncertain:       weak candidates only - keep for triage, don't propose
#   - not_evaluable:   no page text / no candidates
#
# Formatting differences are filtered out via digit-only comparison upstream
# (see ai_validate `_values_equivalent`); only genuinely different digit
# sequences ever surface as detected changes.
# ---------------------------------------------------------------------------

# Match common North American formats:
#   (555) 010-0091  |  555-010-0091  |  555.010.0091  |  +1 555 010 0091
#   555 010 0091    |  5550100091
# Area code first digit must be 2-9 (NANP rule) to reduce false positives
# from year ranges, SKUs, etc.
_PHONE_RE = re.compile(
    r"""(?xi)
    (?:(?<![\w\d])|^)               # left boundary - not preceded by word char
    (?:\+?1[\s.\-\u2013\u2014]*)?  # optional country code
    \(? ([2-9]\d{2}) \)?            # area code (NANP)
    [\s.\-\u2013\u2014]?            # separator
    (\d{3})                         # exchange
    [\s.\-\u2013\u2014]?            # separator
    (\d{4})                         # subscriber
    (?!\d)                          # right boundary - not followed by digit
    """
)

# `tel:` hrefs are an unambiguous signal the site means it as a phone number.
_TEL_HREF_RE = re.compile(r'href\s*=\s*["\']tel:([^"\']+)["\']', re.IGNORECASE)

# Score ceiling for candidates that come only from web-search snippets/titles.
# A search-only candidate must never cross the 0.70 proposed-update threshold
# on its own - search results are enrichment, not authoritative evidence.
_SEARCH_ONLY_PHONE_SCORE_CAP = 0.65

# Keywords whose nearby presence raises confidence.
_PHONE_CONTEXT_WORDS = (
    "phone", "tel", "call", "contact", "office", "telephone",
    "fax", "mobile", "cell", "hotline", "helpline",
)
_PHONE_CONTEXT_WINDOW = 60   # chars on either side of a match
# A simple proxy for footer placement: byte offset > 75% of page length.
_FOOTER_OFFSET_RATIO = 0.75


# ---------------------------------------------------------------------------
# Email extraction patterns and constants
# ---------------------------------------------------------------------------
# Email addresses appear in HTML as mailto: links, visible text, and
# schema.org structured data. We extract from all three sources and
# score/gate them similarly to phone candidates.

_EMAIL_RE = re.compile(
    r"""(?xi)
    \b
    ([a-z0-9](?:[a-z0-9._%+\-]*[a-z0-9])?)  # local part
    @
    ([a-z0-9](?:[a-z0-9\-]*[a-z0-9])?       # domain label
     (?:\.[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?)* # sub-domains
     \.[a-z]{2,})                             # TLD
    \b
    """,
)

_MAILTO_RE = re.compile(
    r'href\s*=\s*["\']mailto:([^"\'?]+)',
    re.IGNORECASE,
)

# Context keywords whose nearby presence raises confidence for emails.
_EMAIL_CONTEXT_WORDS = (
    "email", "e-mail", "contact", "reach", "write", "send",
    "info", "office", "questions", "inquir",
)
_EMAIL_CONTEXT_WINDOW = 80  # chars on either side of a match

# Prefixes that suggest admin / central-office emails (not local site)
_ADMIN_EMAIL_PREFIXES = {
    "admin", "administrator", "webmaster", "postmaster", "noreply",
    "no-reply", "donotreply", "do-not-reply", "support", "help",
    "helpdesk", "it", "hr", "finance", "accounting", "payroll",
    "marketing", "communications", "media", "press",
    "development", "fundraising", "donate", "donations",
    "executive", "ceo", "cfo", "president", "director",
    "board", "volunteer", "volunteers", "careers", "jobs",
    "compliance", "legal",
}

# Prefixes that suggest a local-site / public-contact email
_LOCAL_EMAIL_PREFIXES = {
    "info", "contact", "office", "pantry", "foodpantry",
    "church", "parish", "pastor", "minister", "deacon",
    "outreach", "services", "intake", "reception", "front",
    "main", "general",
}


def _extract_email_candidates(
    page_html: str,
    locality_terms: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Extract candidate email addresses from a fetched webpage.

    Sources (in priority order):
      1. mailto: hrefs — authoritative intent signal
      2. schema.org JSON-LD — machine-readable structured data
      3. Visible text — regex scan of stripped HTML

    Returns a list of dicts (one per distinct email address):
      {
        "email":  "info@example.org",
        "local_part": "info",
        "domain": "example.org",
        "occurrences": int,
        "in_mailto": bool,
        "in_visible_text": bool,
        "from_structured_data": bool,
        "near_contact_keyword": bool,
        "near_locality": bool,
        "in_footer": bool,
      }
    """
    if not page_html:
        return []

    locality_terms = [t for t in (locality_terms or []) if t and len(t) >= 2]

    by_email: Dict[str, Dict[str, Any]] = {}

    def _add_or_update(addr: str, **flags):
        addr_lc = addr.strip().lower()
        if not addr_lc or "@" not in addr_lc:
            return
        local_part, domain = addr_lc.rsplit("@", 1)
        if not local_part or not domain or "." not in domain:
            return
        # Blocklisted domains are always skipped
        if domain in _DISCOVERY_BLOCKLIST:
            return
        for bad in _DISCOVERY_BLOCKLIST:
            if domain.endswith("." + bad):
                return
        # Skip image/asset false positives
        if domain.endswith((".png", ".jpg", ".gif", ".svg", ".css", ".js")):
            return
        # Free-email providers (gmail, yahoo, etc.): only extract when
        # there is a strong contextual signal — mailto href, structured
        # data, or near a contact keyword.  Many small nonprofits and
        # churches use gmail as their official contact, so we must not
        # blanket-skip them when they appear in a "Contact Us" section.
        is_free = domain in _FREE_EMAIL_DOMAINS
        if is_free:
            has_strong_signal = (
                flags.get("in_mailto")
                or flags.get("from_structured_data")
                or flags.get("near_contact_keyword")
            )
            if not has_strong_signal:
                return

        entry = by_email.get(addr_lc)
        if entry is None:
            entry = {
                "email": addr_lc,
                "local_part": local_part,
                "domain": domain,
                "occurrences": 0,
                "in_mailto": False,
                "in_visible_text": False,
                "from_structured_data": False,
                "near_contact_keyword": False,
                "near_locality": False,
                "in_footer": False,
                "free_provider": is_free,
            }
            by_email[addr_lc] = entry
        for k, v in flags.items():
            if v:
                entry[k] = True

    # --- 1. mailto: hrefs ---
    for m in _MAILTO_RE.finditer(page_html):
        raw = m.group(1).strip()
        _add_or_update(raw, in_mailto=True)

    # --- 2. Schema.org JSON-LD ---
    for m in _JSONLD_RE.finditer(page_html):
        try:
            raw = m.group(1).strip()
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            for email_field in ("email", "contactPoint"):
                if email_field == "email" and item.get("email"):
                    val = str(item["email"]).replace("mailto:", "")
                    _add_or_update(val, from_structured_data=True,
                                   near_contact_keyword=True)
                elif email_field == "contactPoint":
                    for cp in (item.get("contactPoint") or []):
                        if isinstance(cp, dict) and cp.get("email"):
                            val = str(cp["email"]).replace("mailto:", "")
                            _add_or_update(val, from_structured_data=True,
                                           near_contact_keyword=True)
            # @graph
            for graph_item in (item.get("@graph") or []):
                if isinstance(graph_item, dict):
                    if graph_item.get("email"):
                        val = str(graph_item["email"]).replace("mailto:", "")
                        _add_or_update(val, from_structured_data=True,
                                       near_contact_keyword=True)
                    for cp in (graph_item.get("contactPoint") or []):
                        if isinstance(cp, dict) and cp.get("email"):
                            val = str(cp["email"]).replace("mailto:", "")
                            _add_or_update(val, from_structured_data=True,
                                           near_contact_keyword=True)

    # --- 3. Visible text ---
    visible = _strip_tags(page_html)
    visible_lc = visible.lower()
    total_len = max(len(visible), 1)

    for m in _EMAIL_RE.finditer(visible):
        full = m.group(0)
        # Pre-check context window BEFORE _add_or_update so free-provider
        # emails near contact keywords are not prematurely rejected.
        start = max(m.start() - _EMAIL_CONTEXT_WINDOW, 0)
        end = min(m.end() + _EMAIL_CONTEXT_WINDOW, total_len)
        window = visible_lc[start:end]
        _near_contact = any(w in window for w in _EMAIL_CONTEXT_WORDS)
        _near_loc = bool(locality_terms and any(t in window for t in locality_terms))
        _in_footer = m.start() / total_len >= _FOOTER_OFFSET_RATIO

        _add_or_update(
            full,
            in_visible_text=True,
            near_contact_keyword=_near_contact,
            near_locality=_near_loc,
            in_footer=_in_footer,
        )
        entry = by_email.get(full.lower())
        if entry is None:
            continue
        entry["occurrences"] = entry.get("occurrences", 0) + 1

    return list(by_email.values())


def _extract_email_candidates_from_search(
    search_results: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """
    Mine candidate email addresses from web-search titles + snippets.

    Returns enrichment candidates with `from_search=True`. These are
    score-capped and can never auto-promote on their own.
    """
    if not search_results:
        return []

    by_email: Dict[str, Dict[str, Any]] = {}
    for item in search_results:
        title = (item.get("title") or "").strip()
        snippet = (item.get("snippet") or "").strip()
        text = f"{title}  {snippet}"
        for m in _EMAIL_RE.finditer(text):
            addr_lc = m.group(0).strip().lower()
            if "@" not in addr_lc:
                continue
            local_part, domain = addr_lc.rsplit("@", 1)
            if domain in _FREE_EMAIL_DOMAINS or domain in _DISCOVERY_BLOCKLIST:
                continue
            if addr_lc not in by_email:
                by_email[addr_lc] = {
                    "email": addr_lc,
                    "local_part": local_part,
                    "domain": domain,
                    "occurrences": 0,
                    "in_mailto": False,
                    "in_visible_text": True,
                    "from_structured_data": False,
                    "near_contact_keyword": False,
                    "near_locality": False,
                    "in_footer": False,
                    "from_search": True,
                    "snippet_text": text,
                }
            by_email[addr_lc]["occurrences"] += 1

    return list(by_email.values())


def _score_email_candidate(
    cand: Dict[str, Any],
    domain_matches_website: bool = False,
    domain_matches_entity: bool = False,
    name_match: bool = False,
    location_match: bool = False,
    stored_email: str = "",
) -> float:
    """
    Score a candidate email in [0, 0.98].

    Base 0.40.
      +0.20 if found via mailto: href (authoritative signal)
      +0.25 if from schema.org structured data
      +0.10 if near contact keyword
      +0.10 if domain matches accepted official website domain
      +0.10 if domain contains org-name tokens
      +0.10 if org name appears on the page (name_match)
      +0.10 if location terms appear on the page (location_match)
      +0.05 if in footer
      +0.05 per extra occurrence (capped at +0.10)
    """
    score = 0.40
    if cand.get("in_mailto"):
        score += 0.20
    if cand.get("from_structured_data"):
        score += 0.25
    if cand.get("near_contact_keyword"):
        score += 0.10
    if domain_matches_website:
        score += 0.10
    if domain_matches_entity:
        score += 0.10
    if name_match:
        score += 0.10
    if location_match:
        score += 0.10
    if cand.get("in_footer"):
        score += 0.05
    extra = max(int(cand.get("occurrences", 1)) - 1, 0)
    score += min(extra * 0.05, 0.10)

    return min(round(score, 2), 0.98)


def _email_proposal_gate(
    site: Dict[str, Any],
    candidate: Dict[str, Any],
    page_text: str,
    name_match: bool,
    location_match: bool,
    website_domain: Optional[str],
) -> Dict[str, Any]:
    """
    Comprehensive email proposal identity gate.  Evaluates whether an
    email candidate should be promoted, downgraded, or rejected based on:

      1. Domain alignment (vs org name and accepted website)
      2. Admin-prefix detection (central office vs local site)
      3. Location consistency
      4. Entity name + type validation
      5. Source quality

    Returns:
      {
        "accept":    bool,
        "downgrade": bool,
        "reason":    str,
        "domain_match":    str,  # website | entity | none
        "location":        str,  # match | conflict | neutral
        "admin_prefix":    bool,
        "source_quality":  str,  # official | structured | strong | weak
      }
    """
    org_name = site.get("name") or ""
    email = candidate.get("email", "")
    email_domain = candidate.get("domain", "")
    local_part = candidate.get("local_part", "")

    # --- Domain alignment ---
    # Check whether the email domain matches the org's official website
    domain_match = "none"
    if website_domain and email_domain == website_domain:
        domain_match = "website"
    elif email_domain:
        # Check if domain contains org-name tokens
        name_tokens = _tokens_from_name(org_name)
        domain_core = re.sub(r"[^a-z0-9]", "", email_domain.rsplit(".", 1)[0])
        hits = sum(1 for t in name_tokens if t in domain_core) if name_tokens else 0
        if hits >= 1:
            domain_match = "entity"

    # --- Domain relevance (reuse existing helper) ---
    domain_rel = _domain_relevance_check(email_domain, org_name)

    # --- Admin prefix detection ---
    admin_prefix = local_part.lower() in _ADMIN_EMAIL_PREFIXES

    # --- Local prefix detection (boost signal) ---
    local_prefix = local_part.lower() in _LOCAL_EMAIL_PREFIXES

    # --- Page scope classification ---
    _page_scope = _classify_page_scope(site, page_text or None)

    # --- Location consistency ---
    location = _location_consistency_check(site, page_text or "")
    loc_detail = _location_match_detail(site, page_text or "")

    # --- Entity name match ---
    _page_title = _extract_page_title(page_text or "")
    _ent_match = _entity_name_match(
        org_name,
        _page_title if _page_title else (page_text or "")[:3000],
    )

    # --- Source quality ---
    is_structured = candidate.get("from_structured_data", False)
    is_mailto = candidate.get("in_mailto", False)
    is_search_only = candidate.get("from_search", False)

    if is_structured:
        source_quality = "official"
    elif is_mailto and name_match:
        source_quality = "official"
    elif is_mailto:
        source_quality = "structured"
    elif name_match and location_match:
        source_quality = "strong"
    else:
        source_quality = "weak"

    # --- Parent office drift ---
    _pd = _detect_parent_office_drift(
        site, page_text or "", email,
    )
    parent_drift = _pd["drift"]

    base = {
        "domain_match": domain_match,
        "location": location,
        "location_detail": loc_detail,
        "admin_prefix": admin_prefix,
        "local_prefix": local_prefix,
        "source_quality": source_quality,
        "parent_drift": parent_drift,
        "page_scope": _page_scope["scope"],
    }

    # ===== HARD REJECT rules =====

    # Entity type conflict (page belongs to a different kind of business)
    if _ent_match.get("type_conflict"):
        return {
            **base, "accept": False, "downgrade": False,
            "reason": f"Entity type conflict: {_ent_match['reason']}",
        }

    # Entity name mismatch (page title doesn't match org name at all)
    if not _ent_match["accept"]:
        return {
            **base, "accept": False, "downgrade": False,
            "reason": f"Entity name mismatch: {_ent_match['reason']}",
        }

    # Unrelated business domain
    if domain_rel == "unrelated":
        return {
            **base, "accept": False, "downgrade": False,
            "reason": f"Email domain '{email_domain}' belongs to an unrelated business category.",
        }

    # Free email provider — downgrade instead of hard-reject when the
    # email was found via strong signals (mailto, structured data, or
    # near a contact keyword) on a confirmed org page.  Small nonprofits
    # and churches frequently use gmail/yahoo as their official contact.
    if email_domain in _FREE_EMAIL_DOMAINS:
        has_strong_signal = (
            candidate.get("in_mailto")
            or candidate.get("from_structured_data")
            or candidate.get("near_contact_keyword")
        )
        if has_strong_signal:
            return {
                **base, "accept": True, "downgrade": True,
                "reason": (
                    f"Email uses free provider domain '{email_domain}'; "
                    f"found via {'mailto' if candidate.get('in_mailto') else 'contact context'}. "
                    f"Downgraded for review."
                ),
            }
        return {
            **base, "accept": False, "downgrade": False,
            "reason": f"Email uses free provider domain '{email_domain}'.",
        }

    # Location conflict: page clearly points to a different location
    if loc_detail["verdict"] == "different_location":
        return {
            **base, "accept": False, "downgrade": False,
            "reason": (
                f"Page location points to a different area"
                f"{' (' + loc_detail['different_state'] + ')' if loc_detail['different_state'] else ''}"
                f"; email likely belongs to wrong office."
            ),
        }

    # Different city + ZIP conflict
    if loc_detail["different_city"] and loc_detail["zip_conflict"]:
        return {
            **base, "accept": False, "downgrade": False,
            "reason": (
                f"Page references {loc_detail['different_city']} "
                f"(site is in {(site.get('city') or 'unknown')}); "
                f"email likely belongs to wrong office."
            ),
        }

    # Parent/admin office drift (umbrella org, wrong campus)
    if parent_drift:
        return {
            **base, "accept": False, "downgrade": False,
            "reason": f"Email appears to belong to a parent/admin office: {_pd['reason']}",
        }

    # No domain alignment + weak source = suspect
    if domain_match == "none" and source_quality == "weak":
        return {
            **base, "accept": False, "downgrade": False,
            "reason": (
                f"Email domain '{email_domain}' does not match org name "
                f"or website, and source evidence is weak."
            ),
        }

    # Search-only source with no domain alignment
    if is_search_only and domain_match == "none":
        return {
            **base, "accept": False, "downgrade": False,
            "reason": "Email found in search snippet only with no domain alignment.",
        }

    # Admin prefix + umbrella office page → hard reject
    # (e.g., ceo@example.org scraped from the diocese HQ page)
    if admin_prefix and _page_scope["scope"] == "umbrella_office":
        return {
            **base, "accept": False, "downgrade": False,
            "reason": (
                f"Email prefix '{local_part}' is admin-type on an umbrella "
                f"office page ({'; '.join(_page_scope['signals'][:2])}); "
                f"likely central office contact, not this site."
            ),
        }

    # ===== DOWNGRADE rules (accept but force low_confidence) =====

    # Umbrella office page scope without city match — page is central
    # office but email might still be valid for this site.  Downgrade
    # so a human reviews it.
    if _page_scope["scope"] == "umbrella_office" and not loc_detail["city_match"]:
        return {
            **base, "accept": True, "downgrade": True,
            "reason": (
                f"Email found on umbrella/admin office page "
                f"({'; '.join(_page_scope['signals'][:2])}); "
                f"needs review to confirm it applies to this specific site."
            ),
        }

    # Admin prefix on a local site record
    if admin_prefix and domain_match != "website":
        return {
            **base, "accept": True, "downgrade": True,
            "reason": (
                f"Email prefix '{local_part}' suggests admin/central office; "
                f"downgraded for review."
            ),
        }

    # Location conflict (old-style) — softer signal
    if location == "conflict":
        return {
            **base, "accept": True, "downgrade": True,
            "reason": "Page location may conflict with site; email downgraded for review.",
        }

    # Different city without ZIP conflict — softer
    if loc_detail["different_city"] and not loc_detail["city_match"]:
        return {
            **base, "accept": True, "downgrade": True,
            "reason": (
                f"Page may reference {loc_detail['different_city']} "
                f"(site is in {(site.get('city') or 'unknown')}); "
                f"email downgraded for review."
            ),
        }

    # No domain alignment but source is somewhat OK
    if domain_match == "none" and source_quality not in ("official",):
        return {
            **base, "accept": True, "downgrade": True,
            "reason": (
                f"Email domain '{email_domain}' does not match org name or website; "
                f"needs verification."
            ),
        }

    # Weak source quality
    if source_quality == "weak":
        return {
            **base, "accept": True, "downgrade": True,
            "reason": "Email source has weak identity signals; needs corroboration.",
        }

    # ===== ACCEPT =====
    return {
        **base, "accept": True, "downgrade": False,
        "reason": "Email identity validated.",
    }


# ---------------------------------------------------------------------------
# Email evidence
# ---------------------------------------------------------------------------

_SEARCH_ONLY_EMAIL_SCORE_CAP = 0.60


def _email_evidence(
    site: Dict[str, Any],
    page_text: Optional[str],
    site_label: str,
    web_ok: bool,
    website_domain: Optional[str] = None,
    ctx: Optional[BatchContext] = None,
    search_results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Build email evidence by mining the homepage HTML and search snippets.

    Decision rules:
      - candidate == stored email             -> confirmed (>=0.90 conf)
      - best different candidate score >= 0.70 -> proposed_update
      - best different candidate score 0.50-0.69
          + domain match + name_match         -> proposed_update_low_confidence
      - below 0.50 or weak signals            -> uncertain (NOT proposed)
      - no candidates / no page text          -> uncertain or not_evaluable
    """
    stored = site.get("publicEmail") or site.get("email")
    stored_lc = (stored or "").strip().lower()

    # Build locality terms for context proximity
    city = (site.get("city") or "").strip().lower()
    state = (site.get("state") or "").strip().lower()
    locality_terms: List[str] = []
    if city and len(city) >= 3:
        locality_terms.append(city)
    if state and len(state) >= 2:
        locality_terms.append(state)

    # Search-snippet extraction (enrichment only)
    search_candidates = _extract_email_candidates_from_search(search_results)

    if not page_text:
        if not search_candidates:
            return {
                "status": "uncertain",
                "current_value": stored,
                "proposed_value": None,
                "confidence": 0.4 if web_ok else 0.2,
                "reason": (
                    "Email not found on website."
                    if web_ok else "Website unreachable; email not evaluable."
                ),
                "evidence_source_type": "web_scrape" if web_ok else None,
            }
        # Score search-only candidates (weak — no page context)
        for c in search_candidates:
            raw = _score_email_candidate(c, stored_email=stored_lc)
            c["score"] = min(raw, _SEARCH_ONLY_EMAIL_SCORE_CAP)
        search_candidates.sort(key=lambda c: c["score"], reverse=True)
        # Confirmation path
        if stored_lc:
            for c in search_candidates:
                if c["email"] == stored_lc:
                    return {
                        "status": "confirmed",
                        "current_value": stored,
                        "proposed_value": stored,
                        "confidence": max(c["score"], 0.80),
                        "reason": "Stored email matches a web-search snippet.",
                        "evidence_source_type": "web_search",
                        "candidates": search_candidates[:5],
                    }
        best = search_candidates[0]
        return {
            "status": "uncertain",
            "current_value": stored,
            "proposed_value": None,
            "confidence": best["score"],
            "reason": (
                f"Email found in web-search snippet only "
                f"({best['email']}); not strong enough to propose."
            ),
            "evidence_source_type": "web_search",
            "candidates": search_candidates[:5],
        }

    page_text_lc = page_text.lower()
    name_tokens = _tokens_from_name(site.get("name") or "")
    name_match = bool(name_tokens) and any(t in page_text_lc for t in name_tokens)
    location_match = bool(locality_terms) and any(t in page_text_lc for t in locality_terms)

    page_candidates = _extract_email_candidates(page_text, locality_terms=locality_terms)

    # Merge search candidates (dedup by email address)
    page_emails_seen = {c["email"] for c in page_candidates}
    merged: List[Dict[str, Any]] = list(page_candidates)
    for sc in search_candidates:
        if sc["email"] in page_emails_seen:
            # Same email on page + search → mark as corroborated
            for pc in merged:
                if pc["email"] == sc["email"]:
                    pc["from_search_corroborated"] = True
                    break
        else:
            merged.append(sc)
    candidates = merged

    if not candidates:
        return {
            "status": "uncertain",
            "current_value": stored,
            "proposed_value": None,
            "confidence": 0.4,
            "reason": "No email addresses detected on homepage.",
            "evidence_source_type": "web_scrape",
        }

    # Domain alignment checks for scoring
    org_name = site.get("name") or ""
    for c in candidates:
        dom = c.get("domain", "")
        domain_matches_website = bool(website_domain and dom == website_domain)
        # Check if domain contains org-name tokens
        name_toks = _tokens_from_name(org_name)
        dom_core = re.sub(r"[^a-z0-9]", "", dom.rsplit(".", 1)[0]) if dom else ""
        domain_matches_entity = bool(name_toks and sum(1 for t in name_toks if t in dom_core) >= 1)

        raw = _score_email_candidate(
            c,
            domain_matches_website=domain_matches_website,
            domain_matches_entity=domain_matches_entity,
            name_match=name_match,
            location_match=location_match,
            stored_email=stored_lc,
        )
        if c.get("from_search") and not c.get("from_search_corroborated"):
            raw = min(raw, _SEARCH_ONLY_EMAIL_SCORE_CAP)
        c["score"] = raw

    candidates.sort(key=lambda c: c["score"], reverse=True)

    # Confirmation path: any candidate matches the stored email
    if stored_lc:
        for c in candidates:
            if c["email"] == stored_lc:
                return {
                    "status": "confirmed",
                    "current_value": stored,
                    "proposed_value": stored,
                    "confidence": max(c["score"], 0.90),
                    "reason": f"Stored email matches address on website.",
                    "evidence_source_type": "web_scrape",
                    "candidates": candidates[:5],
                }

    best = candidates[0]
    different = (not stored_lc) or (best["email"] != stored_lc)

    if different:
        # --- Email proposal gate ---
        _gate = _email_proposal_gate(
            site, best, page_text or "",
            name_match=name_match,
            location_match=location_match,
            website_domain=website_domain,
        )

        if not _gate["accept"]:
            logger.warning(
                f"[{site_label}] EMAIL GATE BLOCKED: "
                f"{best['email']} — {_gate['reason']}"
            )
            _eg_status = (
                "suspect_parent_office_drift"
                if _gate.get("parent_drift")
                else "suspect_entity_match"
            )
            return {
                "status": _eg_status,
                "current_value": stored,
                "proposed_value": None,
                "confidence": best["score"] * 0.2,
                "reason": (
                    f"Email {best['email']} found but blocked: "
                    f"{_gate['reason']}"
                ),
                "evidence_source_type": "web_scrape",
                "candidates": candidates[:5],
                "email_gate": _gate,
            }

        force_low_conf = _gate.get("downgrade", False)

        if best["score"] >= 0.70:
            _e_status = "proposed_update"
            _e_conf = best["score"]
            if force_low_conf:
                _e_status = "proposed_update_low_confidence"
                _e_conf = min(best["score"], 0.65)

            logger.info(
                f"[{site_label}] email candidate: {best['email']} "
                f"(score={best['score']}, domain_match={_gate['domain_match']})"
            )
            return {
                "status": _e_status,
                "current_value": stored,
                "proposed_value": best["email"],
                "confidence": _e_conf,
                "reason": (
                    f"Email on website differs from stored value"
                    f"{' [gate-downgraded: ' + _gate['reason'] + ']' if force_low_conf else ''}."
                ),
                "evidence_source_type": "web_scrape",
                "candidates": candidates[:5],
            }

        # Moderate evidence (0.50-0.69) with domain match
        dom = best.get("domain", "")
        has_domain_alignment = (
            (website_domain and dom == website_domain)
            or bool(_tokens_from_name(org_name) and sum(
                1 for t in _tokens_from_name(org_name)
                if t in re.sub(r"[^a-z0-9]", "", dom.rsplit(".", 1)[0])
            ) >= 1)
        )
        if best["score"] >= 0.50 and name_match and has_domain_alignment:
            logger.info(
                f"[{site_label}] email candidate (low conf): {best['email']} "
                f"(score={best['score']})"
            )
            return {
                "status": "proposed_update_low_confidence",
                "current_value": stored,
                "proposed_value": best["email"],
                "confidence": best["score"],
                "reason": (
                    f"Email on website differs from stored value, "
                    f"moderate evidence."
                ),
                "evidence_source_type": "web_scrape",
                "candidates": candidates[:5],
            }

    # Below threshold — surface for triage
    return {
        "status": "uncertain",
        "current_value": stored,
        "proposed_value": None,
        "confidence": best["score"],
        "reason": (
            f"Email {best['email']} found but evidence is "
            f"{'moderate' if best['score'] >= 0.50 else 'weak'} "
            f"(score={best['score']})."
        ),
        "evidence_source_type": "web_scrape",
        "candidates": candidates[:5],
    }


def _strip_tags(html: str) -> str:
    """Strip HTML tags so we can scan visible text for phone numbers.
    Lightweight - regex-based, no external HTML parser dependency."""
    if not html:
        return ""
    # Drop <script>...</script> and <style>...</style> first so their
    # contents (which often contain digit sequences) don't pollute results.
    no_script = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ",
                       html, flags=re.IGNORECASE | re.DOTALL)
    return re.sub(r"<[^>]+>", " ", no_script)


def _phone_digits_local(s: Any) -> str:
    """Return only the digits from a phone-like value. Mirrors the same
    helper in ai_validate so format-only diffs never count as changes."""
    if not s:
        return ""
    digits = re.sub(r"\D+", "", str(s))
    # Drop a leading US country-code "1" so comparisons are length-stable
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def _format_phone(area: str, exch: str, sub: str) -> str:
    """Return a canonical display form for a parsed phone tuple."""
    return f"({area}) {exch}-{sub}"


# ---------------------------------------------------------------------------
# Schema.org JSON-LD structured data extraction
# ---------------------------------------------------------------------------
# Many org websites embed machine-readable contact info via schema.org
# JSON-LD or microdata. When present, these are FAR more reliable than
# regex phone extraction from visible text because the site operator
# explicitly declared the phone number in structured markup.

_JSONLD_RE = re.compile(
    r'<script[^>]+type\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def _extract_phones_from_structured_data(page_html: str) -> List[Dict[str, Any]]:
    """
    Extract phone numbers from schema.org JSON-LD blocks in page HTML.

    Returns a list of candidate dicts with `from_structured_data=True`.
    These candidates get a scoring boost because the site operator
    explicitly declared the phone in machine-readable markup.
    """
    if not page_html:
        return []

    candidates: Dict[str, Dict[str, Any]] = {}

    for m in _JSONLD_RE.finditer(page_html):
        try:
            raw = m.group(1).strip()
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue

        # JSON-LD can be a single object or an array of objects
        items = data if isinstance(data, list) else [data]

        for item in items:
            if not isinstance(item, dict):
                continue
            # Check telephone field at top level and nested contactPoint
            phone_fields: List[str] = []
            if item.get("telephone"):
                phone_fields.append(str(item["telephone"]))
            for cp in (item.get("contactPoint") or []):
                if isinstance(cp, dict) and cp.get("telephone"):
                    phone_fields.append(str(cp["telephone"]))
            # Also check @graph for nested entities
            for graph_item in (item.get("@graph") or []):
                if isinstance(graph_item, dict):
                    if graph_item.get("telephone"):
                        phone_fields.append(str(graph_item["telephone"]))
                    for cp in (graph_item.get("contactPoint") or []):
                        if isinstance(cp, dict) and cp.get("telephone"):
                            phone_fields.append(str(cp["telephone"]))

            for phone_str in phone_fields:
                digits = _phone_digits_local(phone_str)
                if len(digits) != 10:
                    continue
                if digits not in candidates:
                    area, exch, sub = digits[:3], digits[3:6], digits[6:]
                    candidates[digits] = {
                        "digits": digits,
                        "display": _format_phone(area, exch, sub),
                        "occurrences": 1,
                        "in_visible_text": False,
                        "in_tel_href": False,
                        "near_contact_keyword": True,   # structured data implies contact
                        "near_locality": True,           # it's the org's own markup
                        "in_footer": False,
                        "from_structured_data": True,
                    }

    return list(candidates.values())


# ---------------------------------------------------------------------------
# Shared / umbrella website detection
# ---------------------------------------------------------------------------
# Detect when a website likely serves multiple organizations (e.g., a
# diocesan cluster site hosting 12 parishes). When detected, phone
# candidates from the page are less trustworthy because the numbers
# may belong to a different org on the same site.

def _is_shared_website(
    page_html: Optional[str],
    org_name: str,
    website_url: Optional[str],
) -> bool:
    """
    Heuristic: return True when the website likely serves multiple orgs,
    making page-scraped phone numbers less reliable.

    Signals:
      - Domain doesn't contain any distinctive tokens from the org name
        (e.g., cluster30.org for "St. Joseph Catholic Church")
      - Page title doesn't contain the org name
      - Multiple different phone numbers (>= 4) on the page
    """
    if not page_html or not org_name:
        return False

    name_tokens = _tokens_from_name(org_name)
    if not name_tokens:
        return False

    signals = 0

    # Signal 1: domain has no org name tokens
    if website_url:
        domain = _domain_of(website_url)
        if domain:
            domain_lc = domain.lower()
            if not any(t in domain_lc for t in name_tokens):
                signals += 1

    # Signal 2: page <title> doesn't contain any org name tokens
    title_match = re.search(r"<title[^>]*>(.*?)</title>", page_html, re.IGNORECASE | re.DOTALL)
    if title_match:
        title_lc = title_match.group(1).strip().lower()
        if not any(t in title_lc for t in name_tokens):
            signals += 1
    else:
        # No title tag at all — mildly suspicious
        signals += 1

    # Signal 3: many distinct phone numbers on the page (umbrella sites
    # typically list multiple locations with different numbers)
    visible = _strip_tags(page_html)
    phone_digits_seen: set = set()
    for pm in _PHONE_RE.finditer(visible):
        d = pm.group(1) + pm.group(2) + pm.group(3)
        if len(d) == 10:
            phone_digits_seen.add(d)
    if len(phone_digits_seen) >= 4:
        signals += 1

    # Need at least 2 signals to flag as shared (reduces false positives)
    return signals >= 2


# ---------------------------------------------------------------------------
# Closure detection
# ---------------------------------------------------------------------------
# Scan page text and search results for signals that a site/organization
# is permanently closed. This is high-priority information for TackleHunger
# because a closed food pantry means people are being directed somewhere
# that no longer serves food.

# Phrases that strongly indicate permanent closure. Matched case-insensitively
# against visible page text. Each phrase is checked as a whole (not individual
# words) to avoid false positives (e.g., "closed today" should NOT match).
_CLOSURE_PHRASES = [
    "permanently closed",
    "permanently shut down",
    "no longer operating",
    "no longer open",
    "no longer in operation",
    "no longer in service",
    "no longer serving",
    "this location has closed",
    "this location is closed",
    "this site has closed",
    "this pantry has closed",
    "this food pantry has closed",
    "we have closed",
    "has been closed permanently",
    "closed its doors",
    "ceased operations",
    "ceased operation",
    "discontinue operations",
    "discontinued operations",
    "is no longer active",
    "no longer exists",
    "has shut down",
    "has been shut down",
]

# Compile once for performance
_CLOSURE_RE = re.compile(
    "|".join(re.escape(p) for p in _CLOSURE_PHRASES),
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Geocoding cross-validation
# ---------------------------------------------------------------------------
# Uses the free OpenStreetMap Nominatim API to verify that a site's address
# components (city, state, ZIP) are geographically consistent.  This is a
# *supplementary* check that never blocks or overrides the existing pipeline;
# it adds a geo_validation section to the evidence report so reviewers can
# see when address components look inconsistent.
#
# Rate-limit: Nominatim's usage policy requires ≤1 req/s and an identifying
# User-Agent.  We honour both by adding a short sleep and reusing the
# TackleHunger UA.
# ---------------------------------------------------------------------------
GEOCODE_TIMEOUT: int = 6
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# US state abbreviation → full name mapping (subset used for Nominatim)
# (reuses _US_STATE_ABBREV_TO_NAME if already defined, else falls back)
_GEO_STATE_NAMES: Dict[str, str] = {}
try:
    _GEO_STATE_NAMES = _US_STATE_ABBREV_TO_NAME  # type: ignore[name-defined]
except NameError:
    pass


def geocode_validate(
    site: Dict[str, Any],
    *,
    site_label: str = "unknown",
    ctx: Optional[BatchContext] = None,
) -> Dict[str, Any]:
    """
    Cross-validate a site's address fields using geocoding.

    Sends the full address to Nominatim and compares the returned city /
    state / ZIP with the site record.  Returns a lightweight result dict:

        {
            "geocoded": True/False,
            "city_match": True/False/None,
            "state_match": True/False/None,
            "zip_match": True/False/None,
            "returned_city": str | None,
            "returned_state": str | None,
            "returned_zip": str | None,
            "confidence": float,   # 0.0–1.0 summary
            "note": str,           # human-readable summary
        }

    The result is purely informational — it does NOT change any existing
    confidence scores, classifications, or proposed values.
    """
    empty_result: Dict[str, Any] = {
        "geocoded": False,
        "city_match": None, "state_match": None, "zip_match": None,
        "returned_city": None, "returned_state": None, "returned_zip": None,
        "confidence": 0.0,
        "note": "geocoding skipped",
    }

    if not HAS_REQUESTS:
        empty_result["note"] = "requests library not available"
        return empty_result

    street = (site.get("streetAddress") or "").strip()
    city = (site.get("city") or "").strip()
    state = (site.get("state") or "").strip()
    zip_code = (site.get("zip") or "").strip()

    # Build a query string from available address parts
    parts = [p for p in (street, city, state, zip_code) if p]
    if len(parts) < 2:
        empty_result["note"] = "insufficient address fields for geocoding"
        return empty_result

    query = ", ".join(parts)

    # Respect Nominatim rate limit (1 req/s)
    time.sleep(1.1)

    try:
        session = ctx.session if ctx else None
        requester = session or requests
        resp = requester.get(
            NOMINATIM_URL,
            params={
                "q": query,
                "format": "json",
                "addressdetails": "1",
                "limit": "1",
                "countrycodes": "us",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=GEOCODE_TIMEOUT,
        )
        resp.raise_for_status()
        results = resp.json()

        if ctx:
            ctx.incr_requests()

    except Exception as e:
        logger.warning("[%s] geocode request failed: %s: %s", site_label, type(e).__name__, e)
        empty_result["note"] = f"geocode request failed: {type(e).__name__}"
        return empty_result

    if not results:
        empty_result["note"] = "geocode returned no results"
        return empty_result

    addr = results[0].get("address", {})
    returned_city = (
        addr.get("city")
        or addr.get("town")
        or addr.get("village")
        or addr.get("hamlet")
        or ""
    ).strip()
    returned_state = (addr.get("state") or "").strip()
    returned_zip = (addr.get("postcode") or "").strip()

    # --- Compare ---
    city_lc = city.lower()
    ret_city_lc = returned_city.lower()
    city_match = bool(city_lc and ret_city_lc and city_lc == ret_city_lc) if city else None

    state_upper = state.upper()
    # Nominatim returns full state name; compare against both abbreviation and full name
    ret_state_upper = returned_state.upper()
    state_full = _GEO_STATE_NAMES.get(state_upper, "").upper()
    state_match = (
        bool(state_upper and (state_upper == ret_state_upper or state_full == ret_state_upper))
        if state else None
    )

    site_zip5 = zip_code[:5] if len(zip_code) >= 5 else zip_code
    ret_zip5 = returned_zip[:5] if len(returned_zip) >= 5 else returned_zip
    zip_match = bool(site_zip5 and ret_zip5 and site_zip5 == ret_zip5) if zip_code else None

    # Confidence heuristic: proportion of matched fields
    checks = [v for v in (city_match, state_match, zip_match) if v is not None]
    if checks:
        geo_conf = sum(1 for v in checks if v) / len(checks)
    else:
        geo_conf = 0.0

    # Build human-readable note
    mismatches = []
    if city_match is False:
        mismatches.append(f"city: expected '{city}', got '{returned_city}'")
    if state_match is False:
        mismatches.append(f"state: expected '{state}', got '{returned_state}'")
    if zip_match is False:
        mismatches.append(f"zip: expected '{zip_code}', got '{returned_zip}'")

    if not mismatches:
        note = "address components verified by geocoding"
    else:
        note = "geocoding mismatch: " + "; ".join(mismatches)

    # Log only the confidence score and match/mismatch count — avoid
    # logging raw address values (CodeQL: py/clear-text-logging-sensitive-data).
    logger.info(
        "[%s] geocode validation: conf=%.2f, mismatches=%d",
        site_label, geo_conf, len(mismatches),
    )

    return {
        "geocoded": True,
        "city_match": city_match,
        "state_match": state_match,
        "zip_match": zip_match,
        "returned_city": returned_city or None,
        "returned_state": returned_state or None,
        "returned_zip": returned_zip or None,
        "confidence": round(geo_conf, 2),
        "note": note,
    }


def _detect_closure(
    page_html: Optional[str],
    search_results: Optional[List[Dict[str, Any]]] = None,
    status_code: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Check whether a site appears to be permanently closed.

    Examines three signal sources:
      1. Visible text on the page for closure phrases
      2. Search result snippets for closure phrases
      3. HTTP status codes (410 Gone)

    Context-aware filtering (reduces false positives):
      - Negation check: skips matches preceded by "not", "isn't", etc.
      - Active-indicator check: if the page has business hours, upcoming
        events, or donation links, closure confidence is downgraded.
      - Proximity check: closure phrase must be in the first 3000 chars
        of visible text (title / main content area) to score full
        confidence; phrases buried deep in footer/sidebar score lower.

    Returns:
      {
        "detected": bool,
        "confidence": float,    # 0.0 - 1.0
        "signals": list[str],   # human-readable signal descriptions
        "source": str,          # "page" | "search" | "http" | None
      }
    """
    signals: List[str] = []
    source: Optional[str] = None
    confidence = 0.0

    # Signal 1: HTTP 410 Gone (server explicitly says resource is gone)
    if status_code == 410:
        signals.append(f"HTTP {status_code} Gone response")
        source = "http"
        confidence = max(confidence, 0.85)

    # Signal 2: Closure phrases in page visible text
    if page_html:
        visible = _strip_tags(page_html)
        visible_lc = visible.lower()

        # --- Active-indicator detection ---
        # Pages with business hours, upcoming events, donation buttons,
        # or "open" language are very unlikely to be permanently closed.
        # These are strong counter-signals that reduce confidence.
        _active_patterns = [
            r"\b(?:mon|tue|wed|thu|fri|sat|sun)\w*\s*[-–:]\s*\d",  # business hours
            r"\bhours\s*(?:of\s+)?(?:operation|service)\b",         # "hours of operation"
            r"\bopen\s+(?:mon|tue|wed|thu|fri|sat|sun|daily)\b",    # "open Monday..."
            r"\bopens?\s+at\s+\d",                                  # "opens at 9am"
            r"\bupcoming\s+events?\b",                               # upcoming events
            r"\bdonate\s+(?:now|today|here)\b",                      # active donation
            r"\bvolunteer\s+(?:sign\s*up|with\s+us|today)\b",       # active volunteering
            r"\bserving\s+(?:the\s+)?communit",                      # "serving the community"
            r"\bnow\s+(?:accepting|serving|open)\b",                 # "now accepting/serving"
        ]
        has_active_indicators = any(
            re.search(p, visible_lc) for p in _active_patterns
        )

        # --- Negation pattern ---
        _NEGATION_RE = re.compile(
            r"\b(?:not|n[''o]t|never|isn[''t]|aren[''t]|won[''t]|will\s+not"
            r"|have\s+not|has\s+not|do\s+not|does\s+not)\s+",
            re.IGNORECASE,
        )

        matches = _CLOSURE_RE.finditer(visible)
        accepted_phrases: List[str] = []
        for m in matches:
            phrase = m.group().lower()
            start = m.start()

            # Check for negation within 20 chars before the match
            prefix_start = max(0, start - 25)
            prefix = visible[prefix_start:start]
            if _NEGATION_RE.search(prefix):
                continue  # "we are NOT permanently closed" → skip

            # Proximity: closure phrase in first 3000 chars of visible text
            # is more likely to be about the entity vs. buried in unrelated content
            is_prominent = start < 3000

            accepted_phrases.append(phrase)

            if not is_prominent:
                # Phrase is buried deep in page — weak signal
                signals.append(f'Page contains "{phrase}" (non-prominent)')
                source = source or "page"
                confidence = max(confidence, 0.50)  # below detection threshold alone
            else:
                signals.append(f'Page contains "{phrase}"')
                source = source or "page"
                confidence = max(confidence, 0.80 if len(accepted_phrases) >= 2 else 0.70)

        # Active-indicator downgrade: if the page clearly shows the org is
        # operating (business hours, events, etc.), the closure phrase is
        # likely about something else (an old location, a program, etc.)
        if has_active_indicators and accepted_phrases and source == "page":
            confidence = min(confidence, 0.55)
            signals.append("Active indicators found (business hours/events) — downgraded")

    # Signal 3: Closure phrases in search result snippets
    if search_results:
        for item in search_results:
            snippet = f"{item.get('title', '')} {item.get('snippet', '')}"
            snippet_matches = _CLOSURE_RE.findall(snippet)
            if snippet_matches:
                phrase = snippet_matches[0].lower()
                signals.append(f'Search result: "{phrase}"')
                source = source or "search"
                confidence = max(confidence, 0.65)
                break  # one search signal is enough

    detected = len(signals) >= 1 and confidence >= 0.65
    return {
        "detected": detected,
        "confidence": confidence if detected else 0.0,
        "signals": signals,
        "source": source,
    }


def _closure_identity_gate(
    site: Dict[str, Any],
    closure: Dict[str, Any],
    page_html: Optional[str],
    search_results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Identity gate for closure/status proposals.  Validates that a detected
    closure signal actually belongs to the target entity — not a different
    org on a shared page, a different listing in search results, or an
    umbrella page mentioning another branch.

    Closure is high-impact (open → closed), so the bar is higher than for
    phone/email/website proposals.

    Checks:
      1. Entity name match — page title must reference the target org
      2. Location match — page must reference the target site's area
      3. Shared website detection — umbrella pages need extra scrutiny
      4. Closure phrase attribution — is the phrase near the org name?
      5. Source strength — HTTP 410 is authoritative, search-only is weak

    Returns:
      {
        "accept":    bool,   # True → promote closure_detected
        "downgrade": bool,   # True → force low-confidence closure
        "reason":    str,
        "entity_match":  dict,  # _entity_name_match result
        "location_detail": dict, # _location_match_detail result
        "shared_site":   bool,
      }
    """
    org_name = site.get("name") or ""
    closure_source = closure.get("source")

    # --- HTTP 410 is authoritative (server says it's gone) ---
    # Still verify entity identity but with a lower bar.
    is_http_410 = closure_source == "http"

    # --- Extract page identity signals ---
    page_title = _extract_page_title(page_html or "")
    page_text_for_match = page_title if page_title else (page_html or "")[:5000]

    # When there's no page content, fall back to search result titles
    # for entity name matching.  Titles are typically the entity name and
    # produce a much cleaner match than full snippet text (which dilutes
    # jaccard scores with unrelated words).
    if not page_text_for_match and search_results:
        titles = " ".join(
            item.get("title", "") for item in search_results if item.get("title")
        )
        page_text_for_match = titles[:5000] if titles.strip() else ""

    # Entity name match against page title/text (or search snippet text)
    ent_match = _entity_name_match(org_name, page_text_for_match)

    # Location match detail
    loc_detail = _location_match_detail(site, page_html or "")

    # Shared/umbrella website detection
    website = site.get("website") or site.get("publicWebsite") or ""
    shared_site = _is_shared_website(page_html, org_name, website) if page_html else False

    base = {
        "entity_match": ent_match,
        "location_detail": loc_detail,
        "shared_site": shared_site,
    }

    # ===== HARD REJECT — closure signal does NOT belong to this entity =====

    # Entity type conflict (page belongs to a different kind of business)
    if ent_match.get("type_conflict"):
        return {
            **base, "accept": False, "downgrade": False,
            "reason": (
                f"Closure signal rejected: page belongs to a different entity type. "
                f"{ent_match['reason']}"
            ),
        }

    # Entity name mismatch (page title doesn't reference our org at all)
    # Exception: HTTP 410 is the server itself responding — if the domain
    # is the org's own domain, the 410 is still meaningful.
    if not ent_match["accept"] and not is_http_410:
        return {
            **base, "accept": False, "downgrade": False,
            "reason": (
                f"Closure signal rejected: page does not match entity name. "
                f"{ent_match['reason']}"
            ),
        }

    # Different location entirely (different state)
    if loc_detail["verdict"] == "different_location" and not is_http_410:
        return {
            **base, "accept": False, "downgrade": False,
            "reason": (
                f"Closure signal rejected: page points to a different location"
                f"{' (' + loc_detail['different_state'] + ')' if loc_detail['different_state'] else ''}."
            ),
        }

    # Different city + ZIP conflict → wrong campus/office
    if loc_detail["different_city"] and loc_detail["zip_conflict"] and not is_http_410:
        return {
            **base, "accept": False, "downgrade": False,
            "reason": (
                f"Closure signal rejected: page references "
                f"{loc_detail['different_city']} "
                f"(site is in {(site.get('city') or 'unknown')})."
            ),
        }

    # Search-only closure with no page-level confirmation
    # (search snippets can match the wrong listing entirely)
    if closure_source == "search" and not page_html:
        # For search-only, we need the snippet to mention the org name
        search_has_name = False
        name_tokens = _tokens_from_name(org_name)
        if search_results and name_tokens:
            for item in (search_results or []):
                snippet_text = f"{item.get('title', '')} {item.get('snippet', '')}"
                snippet_lc = snippet_text.lower()
                if sum(1 for t in name_tokens if t in snippet_lc) >= max(len(name_tokens) // 2, 1):
                    search_has_name = True
                    break
        if not search_has_name:
            return {
                **base, "accept": False, "downgrade": False,
                "reason": (
                    "Closure signal rejected: found in search snippet only "
                    "with no entity name confirmation."
                ),
            }

    # ===== DOWNGRADE — closure signal is plausible but not certain =====

    # Shared/umbrella website — closure phrase may refer to a different
    # org hosted on the same site. Accept but force low confidence so
    # a human reviews it.
    if shared_site:
        return {
            **base, "accept": True, "downgrade": True,
            "reason": (
                "Closure signal on shared/umbrella website; "
                "may refer to a different organization on the same site."
            ),
        }

    # Closure from search only (not page) — even with name match, this
    # is a weaker signal than on-page detection.
    if closure_source == "search":
        return {
            **base, "accept": True, "downgrade": True,
            "reason": (
                "Closure signal from search snippet only; "
                "needs on-page or official confirmation."
            ),
        }

    # Single closure phrase on page without name match in title
    # (weaker than title-confirmed closure)
    if page_html and not page_title:
        return {
            **base, "accept": True, "downgrade": True,
            "reason": (
                "Closure signal found on page but page has no title; "
                "identity less certain."
            ),
        }

    # Entity name match is weak (accepted but low overlap/jaccard)
    if ent_match["accept"] and ent_match.get("jaccard", 1.0) < 0.4:
        return {
            **base, "accept": True, "downgrade": True,
            "reason": (
                f"Closure signal found but entity name match is weak "
                f"(jaccard={ent_match.get('jaccard', 0):.0%}); needs review."
            ),
        }

    # Location is neutral (neither confirmed nor conflicting)
    if loc_detail["verdict"] == "neutral" and not is_http_410:
        # Not necessarily wrong, but we can't confirm the closure is
        # specifically about THIS location vs another branch.
        if not loc_detail["city_match"] and not loc_detail["state_match"]:
            return {
                **base, "accept": True, "downgrade": True,
                "reason": (
                    "Closure signal found but no location confirmation; "
                    "may refer to a different branch/location."
                ),
            }

    # ===== ACCEPT — strong identity confirmation =====
    return {
        **base, "accept": True, "downgrade": False,
        "reason": "Closure signal confirmed for target entity.",
    }


# ---------------------------------------------------------------------------
# Cross-reference: search corroboration check
# ---------------------------------------------------------------------------
# When the scraper finds a phone that DIFFERS from the stored phone,
# check whether web search results corroborate the stored number vs.
# the proposed number. If search results contain the stored number
# but NOT the proposed number, the scraper likely picked up a wrong
# number from a shared/umbrella page.

def _search_corroborates_phone(
    search_results: Optional[List[Dict[str, Any]]],
    stored_digits: str,
    proposed_digits: str,
) -> str:
    """
    Check which phone number web search results support.

    Returns:
      "proposed"  - search results contain the proposed number (or both)
      "stored"    - search results contain the stored number but NOT proposed
      "neither"   - search results contain neither
      "no_search" - no search results available
    """
    if not search_results:
        return "no_search"

    stored_found = False
    proposed_found = False

    for item in search_results:
        text = f"{item.get('title', '')} {item.get('snippet', '')}"
        digits_in_text = set()
        for pm in _PHONE_RE.finditer(text):
            d = pm.group(1) + pm.group(2) + pm.group(3)
            if len(d) == 10:
                digits_in_text.add(d)
        if stored_digits in digits_in_text:
            stored_found = True
        if proposed_digits in digits_in_text:
            proposed_found = True

    if proposed_found:
        return "proposed"
    if stored_found:
        return "stored"
    return "neither"


def _extract_phone_candidates(
    page_html: str,
    locality_terms: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Extract candidate phones from a fetched homepage.

    `locality_terms` is an optional list of lowercase strings (typically the
    org's city / state / state abbreviation). When provided, each candidate
    is marked `near_locality=True` if any locality term appears within
    `_PHONE_CONTEXT_WINDOW` chars of the phone in the visible text.

    Returns a list of dicts (one per *distinct* digit sequence):
      {
        "digits": "5550100091",      # normalized
        "display": "(555) 010-0091",
        "occurrences": int,          # visible-text occurrences
        "in_visible_text": bool,     # found in stripped page text >= once
        "in_tel_href": bool,         # found in tel: href
        "near_contact_keyword": bool,
        "near_locality": bool,       # near org city/state in visible text
        "in_footer": bool,
        "from_structured_data": bool, # found in schema.org JSON-LD
      }
    """
    if not page_html:
        return []

    locality_terms = [t for t in (locality_terms or []) if t and len(t) >= 2]

    # `tel:` hrefs are extracted first - they're authoritative.
    tel_digits: set = set()
    for m in _TEL_HREF_RE.finditer(page_html):
        digits = _phone_digits_local(m.group(1))
        if len(digits) == 10:
            tel_digits.add(digits)

    visible = _strip_tags(page_html)
    visible_lc = visible.lower()
    total_len = max(len(visible), 1)

    by_digits: Dict[str, Dict[str, Any]] = {}
    for m in _PHONE_RE.finditer(visible):
        area, exch, sub = m.group(1), m.group(2), m.group(3)
        digits = area + exch + sub
        if len(digits) != 10:
            continue
        entry = by_digits.get(digits)
        if entry is None:
            entry = {
                "digits": digits,
                "display": _format_phone(area, exch, sub),
                "occurrences": 0,
                "in_visible_text": True,
                "in_tel_href": digits in tel_digits,
                "near_contact_keyword": False,
                "near_locality": False,
                "in_footer": False,
                "from_structured_data": False,
            }
            by_digits[digits] = entry
        entry["occurrences"] += 1
        entry["in_visible_text"] = True

        # Context window for keyword / locality proximity.
        start = max(m.start() - _PHONE_CONTEXT_WINDOW, 0)
        end = min(m.end() + _PHONE_CONTEXT_WINDOW, total_len)
        window = visible_lc[start:end]
        if any(w in window for w in _PHONE_CONTEXT_WORDS):
            entry["near_contact_keyword"] = True
        if locality_terms and any(t in window for t in locality_terms):
            entry["near_locality"] = True

        # Footer heuristic - position in the page body.
        if m.start() / total_len >= _FOOTER_OFFSET_RATIO:
            entry["in_footer"] = True

    # Any tel:-href digits that didn't appear in the visible scan still count.
    for digits in tel_digits:
        if digits not in by_digits and len(digits) == 10:
            by_digits[digits] = {
                "digits": digits,
                "display": _format_phone(digits[:3], digits[3:6], digits[6:]),
                "occurrences": 0,
                "in_visible_text": False,
                "in_tel_href": True,
                "near_contact_keyword": False,
                "near_locality": False,
                "in_footer": False,
                "from_structured_data": False,
            }
    return list(by_digits.values())


def _extract_phone_candidates_from_search(
    search_results: Optional[List[Dict[str, Any]]],
    locality_terms: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Mine candidate phone numbers from web-search titles + snippets.

    These are *enrichment* candidates only: the returned dicts carry
    `from_search=True` so the caller knows to apply the search-only
    score cap. Snippets are tiny so we conservatively flag
    `in_visible_text=True` (they ARE visible text - just not on the
    org's own page), `in_tel_href=False`, and locality proximity is
    detected within the snippet itself.
    """
    if not search_results:
        return []

    locality_terms = [t for t in (locality_terms or []) if t and len(t) >= 2]
    by_digits: Dict[str, Dict[str, Any]] = {}

    for item in search_results:
        title = (item.get("title") or "").strip()
        snippet = (item.get("snippet") or "").strip()
        if not title and not snippet:
            continue
        text = f"{title}  {snippet}"
        text_lc = text.lower()
        for m in _PHONE_RE.finditer(text):
            area, exch, sub = m.group(1), m.group(2), m.group(3)
            digits = area + exch + sub
            if len(digits) != 10:
                continue
            entry = by_digits.get(digits)
            if entry is None:
                entry = {
                    "digits": digits,
                    "display": _format_phone(area, exch, sub),
                    "occurrences": 0,
                    "in_visible_text": True,
                    "in_tel_href": False,
                    "near_contact_keyword": False,
                    "near_locality": False,
                    "in_footer": False,
                    "from_search": True,
                    "snippet_text": text,  # for location preference
                }
                by_digits[digits] = entry
            else:
                # Accumulate snippet text for richer location matching
                entry["snippet_text"] = (entry.get("snippet_text", "") + " " + text).strip()
            entry["occurrences"] += 1
            start = max(m.start() - _PHONE_CONTEXT_WINDOW, 0)
            end = min(m.end() + _PHONE_CONTEXT_WINDOW, len(text))
            window = text_lc[start:end]
            if any(w in window for w in _PHONE_CONTEXT_WORDS):
                entry["near_contact_keyword"] = True
            if locality_terms and any(t in window for t in locality_terms):
                entry["near_locality"] = True

    return list(by_digits.values())


def _score_phone_candidate(
    cand: Dict[str, Any],
    name_match: bool = False,
    location_match: bool = False,
    stored_digits: str = "",
) -> float:
    """
    Score a candidate phone in [0, 0.98].

    Base signals:
      Base 0.50.
      +0.25 if found inside a `tel:` href (authoritative).
      +0.15 if appears within 60 chars of "phone"/"call"/"contact"/etc.
      +0.10 if appears in the bottom 25% of the page (footer proxy).
      +0.05 per extra on-page occurrence, capped at +0.15.

    Trust boost (different stored value):
      +0.20 when the page contains both the org name AND the org city
      AND the candidate's digits differ from the stored value. This is
      strong contextual evidence we're looking at the right organization
      and the stored number really is out of date.

    Plain-text locality boost:
      +0.20 when the candidate appears in visible text (NOT only inside a
      `tel:` href) AND sits near the org's city/state mention. Catches
      real-world contact blocks like "Office: 123 Example St, Anytown ST -
      (555) 010-0000" where there is no `tel:` link.
    """
    score = 0.50
    if cand.get("in_tel_href"):
        score += 0.25
    if cand.get("near_contact_keyword"):
        score += 0.15
    if cand.get("in_footer"):
        score += 0.10
    extra = max(int(cand.get("occurrences", 1)) - 1, 0)
    score += min(extra * 0.05, 0.15)

    # Structured data boost: the site operator explicitly declared this
    # phone in schema.org JSON-LD. This is the strongest page-level signal.
    if cand.get("from_structured_data"):
        score += 0.25

    # Trust boost: org name + city + digits differ -> very strong signal
    digits_differ = bool(stored_digits) and cand.get("digits") != stored_digits
    if name_match and location_match and digits_differ:
        score += 0.20
    # Partial trust boost: org name matches but no locality (relaxed).
    # Treats homepage-level name match as valid even without structured
    # section placement. Enough to lift a candidate over the threshold
    # when combined with tel: or contact-keyword signals.
    elif name_match and digits_differ:
        score += 0.10

    # Plain-text locality boost: visible (not tel-only) + near locality
    if cand.get("in_visible_text") and cand.get("near_locality"):
        score += 0.20

    return min(round(score, 2), 0.98)


def _phone_evidence(
    site: Dict[str, Any],
    page_text: Optional[str],
    site_label: str,
    web_ok: bool,
    ctx: Optional[BatchContext] = None,
    search_results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Build phone evidence by mining the homepage HTML when available, and
    (optionally) by scanning enrichment search snippets / titles for
    additional candidate phone numbers.

    Decision rules (formatting differences are NEVER treated as a change -
    digit comparison via `_phone_digits_local`):
      - candidate digits == stored phone digits   -> confirmed (>=0.90 conf)
      - best different candidate score >= 0.70    -> proposed_update
      - best different candidate score 0.50-0.69  -> uncertain (NOT proposed)
      - best different candidate score <  0.50    -> uncertain (weak)
      - no candidates / no page text              -> uncertain or not_evaluable

    Context boosts (applied during scoring):
      - name + location both present on page + digits differ  -> +0.20
      - candidate in visible text + near org city / state      -> +0.20

    Search-derived candidates: candidates extracted only from web-search
    snippets/titles are score-capped (<= 0.65) so they can NEVER cross the
    0.70 proposed-update threshold on their own. They CAN, however, raise
    confidence (and the visible "occurrences" count) for a candidate that
    is also independently observed on the org's own page.
    """
    stored = site.get("phone") or site.get("publicPhone")
    stored_digits = _phone_digits_local(stored)

    # Build locality terms (city, state, state-abbrev) for proximity scoring.
    # Done up-front because both page-text and search-snippet extractors use them.
    city = (site.get("city") or "").strip().lower()
    state = (site.get("state") or "").strip().lower()
    locality_terms: List[str] = []
    if city and len(city) >= 3:
        locality_terms.append(city)
    if state and len(state) >= 2:
        locality_terms.append(state)

    # Always attempt search-snippet extraction when search results are present;
    # these are pure enrichment and never override page-derived evidence.
    search_candidates = _extract_phone_candidates_from_search(
        search_results, locality_terms=locality_terms
    )

    if not page_text:
        # No homepage text - fall back to search-snippet candidates if any.
        if not search_candidates:
            return {
                "status": "uncertain",
                "current_value": stored,
                "proposed_value": None,
                "confidence": 0.4 if web_ok else 0.2,
                "reason": (
                    "Phone number not found on website."
                    if web_ok else "Website unreachable; phone not evaluable."
                ),
                "evidence_source_type": "web_scrape" if web_ok else None,
            }
        # Score search-only candidates (no page context => name/location_match=False).
        for c in search_candidates:
            raw_score = _score_phone_candidate(
                c, name_match=False, location_match=False, stored_digits=stored_digits,
            )
            c["score"] = min(raw_score, _SEARCH_ONLY_PHONE_SCORE_CAP)
        search_candidates.sort(key=lambda c: c["score"], reverse=True)
        # Confirmation path against search snippets.
        if stored_digits:
            for c in search_candidates:
                if c["digits"] == stored_digits:
                    return {
                        "status": "confirmed",
                        "current_value": stored,
                        "proposed_value": stored,
                        "confidence": max(c["score"], 0.80),
                        "reason": "Stored phone matches a web-search snippet.",
                        "evidence_source_type": "web_search",
                        "candidates": search_candidates[:5],
                    }
        best = search_candidates[0]
        return {
            "status": "uncertain",
            "current_value": stored,
            "proposed_value": None,
            "confidence": best["score"],
            "reason": (
                f"Phone candidate found in web-search snippet only "
                f"(best {best['display']}, score={best['score']}); not strong enough to propose."
            ),
            "evidence_source_type": "web_search",
            "candidates": search_candidates[:5],
        }

    page_text_lc = page_text.lower()
    name_tokens = _tokens_from_name(site.get("name") or "")
    name_match = bool(name_tokens) and any(t in page_text_lc for t in name_tokens)
    location_match = bool(locality_terms) and any(t in page_text_lc for t in locality_terms)

    # Phone-specific: compute name overlap score for stronger identity check.
    # Uses both page title and visible text (first 3000 chars) for coverage.
    _page_title = _extract_page_title(page_text)
    name_overlap_score = max(
        _compute_name_overlap(site.get("name", ""), _page_title),
        _compute_name_overlap(site.get("name", ""), page_text[:3000]),
    )

    # Entity name match — bidirectional + type conflict detection.
    # Run against the page title (most descriptive) to catch cases like
    # "Brightwater Food Pantry" vs page titled "Brightwater Solutions".
    _ent_match = _entity_name_match(
        site.get("name", ""),
        _page_title if _page_title else page_text[:3000],
    )

    page_candidates = _extract_phone_candidates(page_text, locality_terms=locality_terms)

    # Schema.org structured data extraction — highest-signal source.
    structured_candidates = _extract_phones_from_structured_data(page_text)
    structured_digits = {c["digits"] for c in structured_candidates}

    # Merge structured data candidates into page candidates (dedup by digits).
    for sc in structured_candidates:
        existing = next((pc for pc in page_candidates if pc["digits"] == sc["digits"]), None)
        if existing:
            # Mark the existing candidate as also found in structured data
            existing["from_structured_data"] = True
        else:
            page_candidates.append(sc)

    # Shared/umbrella website detection — caps confidence for proposals
    # from pages that likely serve multiple organizations.
    shared_site = _is_shared_website(
        page_text,
        site.get("name") or "",
        site.get("website") or site.get("publicWebsite") or "",
    )
    if shared_site:
        logger.info(f"[{site_label}] shared/umbrella website detected — phone proposals will require corroboration")

    # Merge: page candidates first, then search-only candidates (deduped by digits).
    page_digits_seen = {c["digits"] for c in page_candidates}
    merged: List[Dict[str, Any]] = list(page_candidates)
    for sc in search_candidates:
        if sc["digits"] in page_digits_seen:
            # Same number appears both on the page and in search snippets -
            # boost the page candidate's count + flag it as search-corroborated.
            for pc in merged:
                if pc["digits"] == sc["digits"]:
                    pc["occurrences"] = int(pc.get("occurrences", 0)) + int(sc.get("occurrences", 0))
                    pc["from_search_corroborated"] = True
                    break
        else:
            merged.append(sc)
    candidates = merged

    if not candidates:
        return {
            "status": "uncertain",
            "current_value": stored,
            "proposed_value": None,
            "confidence": 0.4,
            "reason": "No phone numbers detected on homepage.",
            "evidence_source_type": "web_scrape",
        }

    # Score every candidate with full context, capping search-only ones.
    # Local site preference: compute location detail from the page to
    # inform downstream gates. For search-snippet candidates, check
    # whether their source text aligns with the site's location.
    _page_loc_detail = _location_match_detail(site, page_text or "")
    for c in candidates:
        raw_score = _score_phone_candidate(
            c,
            name_match=name_match,
            location_match=location_match,
            stored_digits=stored_digits,
        )
        if c.get("from_search") and not c.get("from_search_corroborated"):
            raw_score = min(raw_score, _SEARCH_ONLY_PHONE_SCORE_CAP)
            # Local site preference for search-derived phone candidates:
            # boost candidates whose search snippet mentions the site's city
            # or ZIP; penalize those that mention a different city.
            snippet_text = c.get("snippet_text", "")
            if snippet_text:
                _snip_loc = _location_match_detail(site, snippet_text)
                if _snip_loc["city_match"]:
                    raw_score = min(raw_score + 0.05, _SEARCH_ONLY_PHONE_SCORE_CAP)
                elif _snip_loc["different_city"] or _snip_loc["different_state"]:
                    raw_score = max(raw_score - 0.10, 0.0)
        c["score"] = raw_score
    candidates.sort(key=lambda c: c["score"], reverse=True)

    def _flags_str(c: Dict[str, Any]) -> str:
        flags = []
        if c.get("occurrences"):
            flags.append(f"{c['occurrences']}x visible")
        if c.get("in_tel_href"):
            flags.append("tel: link")
        if c.get("in_footer"):
            flags.append("footer")
        if c.get("near_contact_keyword"):
            flags.append("near contact text")
        if c.get("near_locality"):
            flags.append("near locality")
        return ", ".join(flags) if flags else "no context flags"

    # Confirmation path: any candidate matches the stored phone.
    if stored_digits:
        for c in candidates:
            if c["digits"] == stored_digits:
                return {
                    "status": "confirmed",
                    "current_value": stored,
                    "proposed_value": stored,
                    "confidence": max(c["score"], 0.90),
                    "reason": f"Stored phone matches number on website ({_flags_str(c)}).",
                    "evidence_source_type": "web_scrape",
                    "candidates": candidates[:5],
                }

    best = candidates[0]
    different = (not stored_digits) or (best["digits"] != stored_digits)

    # --- Cross-reference validation for proposed changes ---
    # When the best candidate differs from the stored phone, check whether
    # web search results corroborate the stored or proposed number. This
    # catches cases like shared/umbrella websites (e.g., cluster30.org
    # listing a diocese office number instead of the specific parish).
    xref = "no_search"
    if different and stored_digits:
        xref = _search_corroborates_phone(search_results, stored_digits, best["digits"])

    # --- Comprehensive phone identity gate ---
    # Before proposing any phone change, verify entity name overlap,
    # area code region, source quality, and parent office alignment.
    _phone_gate = None
    _force_low_conf = False
    if different:
        # Entity name match gate — reject before detailed phone checks
        # if the page clearly belongs to a different type of entity.
        if not _ent_match["accept"]:
            logger.warning(
                f"[{site_label}] ENTITY NAME MISMATCH blocked phone: "
                f"{best['display']} — {_ent_match['reason']} "
                f"(overlap={_ent_match['overlap']:.0%}, "
                f"jaccard={_ent_match['jaccard']:.0%}, "
                f"type_conflict={_ent_match['type_conflict']})"
            )
            return {
                "status": "suspect_entity_match",
                "current_value": stored,
                "proposed_value": None,
                "confidence": best["score"] * 0.2,
                "reason": (
                    f"Phone {best['display']} found but entity name mismatch: "
                    f"{_ent_match['reason']}"
                ),
                "evidence_source_type": "web_scrape",
                "candidates": candidates[:5],
                "entity_name_match": _ent_match,
            }

        _phone_gate = _phone_proposal_gate(
            site, page_text or "", best,
            name_overlap_score=name_overlap_score,
            name_match=name_match,
            location_match=location_match,
            shared_site=shared_site,
            xref=xref,
            search_results=search_results,
        )
        if not _phone_gate["accept"]:
            logger.warning(
                f"[{site_label}] PHONE GATE BLOCKED proposal: "
                f"{best['display']} — {_phone_gate['reason']} "
                f"(name_overlap={_phone_gate['name_overlap']:.0%}, "
                f"area_code={_phone_gate['area_code']}, "
                f"source={_phone_gate['source_quality']})"
            )
            _pg_status = (
                "suspect_parent_office_drift"
                if _phone_gate.get("parent_drift")
                else "suspect_entity_match"
            )
            return {
                "status": _pg_status,
                "current_value": stored,
                "proposed_value": None,
                "confidence": best["score"] * 0.3,
                "reason": (
                    f"Phone {best['display']} found but blocked: "
                    f"{_phone_gate['reason']}"
                ),
                "evidence_source_type": "web_scrape",
                "candidates": candidates[:5],
                "phone_gate": _phone_gate,
            }
        _force_low_conf = _phone_gate.get("downgrade", False)

    # Different from stored AND strong evidence (>=0.70) -> propose the update.
    if different and best["score"] >= 0.70:
        boost_note = []
        if name_match and location_match and stored_digits and best["digits"] != stored_digits:
            boost_note.append("name+location verified")
        if name_match and not location_match and stored_digits and best["digits"] != stored_digits:
            boost_note.append("name verified (partial)")
        if best.get("in_visible_text") and best.get("near_locality"):
            boost_note.append("visible text + locality")
        if best.get("from_structured_data"):
            boost_note.append("schema.org structured data")
        boost_str = f" [boosts: {'; '.join(boost_note)}]" if boost_note else ""

        # GUARD: shared website + search corroborates stored number ->
        # the page phone is likely wrong (belongs to another org on the
        # same site). Downgrade to uncertain instead of proposing.
        if shared_site and xref == "stored":
            logger.info(
                f"[{site_label}] BLOCKED phone proposal: shared website + "
                f"search corroborates stored {stored}. Candidate {best['display']} "
                f"(score={best['score']}) likely belongs to different org on same site."
            )
            return {
                "status": "uncertain",
                "current_value": stored,
                "proposed_value": None,
                "confidence": max(best["score"] * 0.5, 0.40),
                "reason": (
                    f"Phone {best['display']} found on shared/umbrella website but "
                    f"web search corroborates stored number. Likely belongs to "
                    f"different organization on same site."
                ),
                "evidence_source_type": "web_scrape",
                "candidates": candidates[:5],
            }

        # GUARD: shared website + search has no info -> downgrade to
        # low-confidence proposal so a human reviews it.
        if shared_site and xref != "proposed":
            logger.info(
                f"[{site_label}] phone proposal downgraded: shared website "
                f"detected, search does not corroborate. "
                f"Candidate {best['display']} (score={best['score']})"
            )
            return {
                "status": "proposed_update_low_confidence",
                "current_value": stored,
                "proposed_value": best["display"],
                "confidence": min(best["score"], 0.65),
                "reason": (
                    f"Phone on shared/umbrella website differs from stored value "
                    f"({_flags_str(best)}){boost_str}. Needs manual verification — "
                    f"website serves multiple organizations."
                ),
                "evidence_source_type": "web_scrape",
                "candidates": candidates[:5],
            }

        # GUARD: NOT a shared site, but search specifically corroborates
        # the stored number and NOT the proposed → downgrade.
        if xref == "stored" and not best.get("from_structured_data"):
            logger.info(
                f"[{site_label}] phone proposal downgraded: search corroborates "
                f"stored {stored}, not proposed {best['display']}"
            )
            return {
                "status": "proposed_update_low_confidence",
                "current_value": stored,
                "proposed_value": best["display"],
                "confidence": min(best["score"], 0.65),
                "reason": (
                    f"Phone on website differs from stored value "
                    f"({_flags_str(best)}){boost_str}, but web search "
                    f"corroborates the stored number. Needs manual verification."
                ),
                "evidence_source_type": "web_scrape",
                "candidates": candidates[:5],
            }

        # GUARD: stored phone area code matches site state BUT search
        # does not corroborate the proposed number → downgrade.
        # This catches cases where the page contains a secondary or
        # volunteer phone (e.g. a personal cell listed alongside the
        # main office line) and the stored number is plausibly correct
        # but wasn't extractable from static HTML (rendered via JS,
        # embedded in an image, inside a widget, etc.).
        if (
            xref in ("neither", "no_search")
            and stored_digits
            and not best.get("from_structured_data")
            and _check_phone_area_code(stored_digits, site.get("state", "")) == "match"
        ):
            logger.info(
                f"[{site_label}] phone proposal downgraded: stored phone "
                f"area code matches site state and search does not "
                f"corroborate proposed {best['display']}"
            )
            return {
                "status": "proposed_update_low_confidence",
                "current_value": stored,
                "proposed_value": best["display"],
                "confidence": min(best["score"], 0.65),
                "reason": (
                    f"Phone on website differs from stored value "
                    f"({_flags_str(best)}){boost_str}. Stored phone area code "
                    f"matches site state and search does not corroborate the "
                    f"proposed number. Needs manual verification."
                ),
                "evidence_source_type": "web_scrape",
                "candidates": candidates[:5],
            }

        # Apply phone identity gate downgrade: if source quality, area code,
        # or location signals are weak, force low_confidence even with a
        # strong score.  This ensures directory-only or region-mismatched
        # phones are never auto-promoted.
        _p_status = "proposed_update"
        _p_conf = best["score"]
        if _force_low_conf:
            _p_status = "proposed_update_low_confidence"
            _p_conf = min(best["score"], 0.65)
            boost_str += f" [gate-downgraded: {_phone_gate['reason']}]"

        logger.info(
            f"[{site_label}] phone candidate from page: "
            f"{best['display']} (score={best['score']}, {_flags_str(best)}){boost_str}"
            f"{' [search-corroborated]' if xref == 'proposed' else ''}"
        )
        return {
            "status": _p_status,
            "current_value": stored,
            "proposed_value": best["display"],
            "confidence": _p_conf,
            "reason": (
                f"Phone on website differs from stored value "
                f"({_flags_str(best)}){boost_str}."
            ),
            "evidence_source_type": "web_scrape",
            "candidates": candidates[:5],
        }

    # Different with moderate evidence (0.50-0.69) AND on a matching domain
    # (name_match + meaningful name overlap proves we're on the right org's
    # page) -> surface as proposed_update_low_confidence.
    if different and best["score"] >= 0.50 and name_match and name_overlap_score >= 0.4:
        # Extra guard: if search corroborates stored number, block the proposal
        if xref == "stored":
            logger.info(
                f"[{site_label}] low-conf phone proposal blocked: search "
                f"corroborates stored {stored}"
            )
            return {
                "status": "uncertain",
                "current_value": stored,
                "proposed_value": None,
                "confidence": max(best["score"] * 0.5, 0.30),
                "reason": (
                    f"Phone {best['display']} found on website (moderate evidence) "
                    f"but web search corroborates stored number."
                ),
                "evidence_source_type": "web_scrape",
                "candidates": candidates[:5],
            }

        logger.info(
            f"[{site_label}] phone candidate (low conf) from page: "
            f"{best['display']} (score={best['score']}, {_flags_str(best)})"
        )
        return {
            "status": "proposed_update_low_confidence",
            "current_value": stored,
            "proposed_value": best["display"],
            "confidence": best["score"],
            "reason": (
                f"Phone on website differs from stored value, moderate evidence "
                f"({_flags_str(best)})."
            ),
            "evidence_source_type": "web_scrape",
            "candidates": candidates[:5],
        }

    # Different but mid/low evidence (0.50-0.69 or <0.50) - surface for triage.
    return {
        "status": "uncertain",
        "current_value": stored,
        "proposed_value": None,
        "confidence": best["score"],
        "reason": (
            f"Phone on website differs from stored value but evidence is "
            f"{'moderate' if best['score'] >= 0.50 else 'weak'} "
            f"(best candidate {best['display']}, score={best['score']}, {_flags_str(best)})."
            if stored_digits
            else f"Phone(s) found on site but evidence is "
                 f"{'moderate' if best['score'] >= 0.50 else 'weak'} "
                 f"(best candidate {best['display']}, score={best['score']}, {_flags_str(best)})."
        ),
        "evidence_source_type": "web_scrape",
        "candidates": candidates[:5],
    }


# ---------------------------------------------------------------------------
# Evidence gathering
# ---------------------------------------------------------------------------
def _website_evidence(site, site_label, ctx: Optional[BatchContext] = None,
                      search_results: Optional[List[Dict[str, Any]]] = None):
    """
    Probe the site's website with a bounded request.
    Falls back to `not_evaluable` / `uncertain` on failure instead of crashing.

    Caching: results are cached per canonical URL within a batch run so
    duplicate websites are only fetched once. This is the short-circuit
    path - we never make extra page fetches beyond the one canonical probe.

    Discovery: when the site has NO website on record, we attempt three
    discovery strategies (in order, highest signal first):
      1. Email-domain discovery - if the org has a custom-domain email
         like `info@example.org`, probe https://example.org/ and
         use it as the proposed website if it loads and matches.
      2. Name-token + web-search discovery - generate candidate domains
         from the organization name and (when `search_results` are
         supplied) merge in URLs from the enrichment search. All
         candidates flow through the same probe + scoring path.
      3. Same as (2) without search input (deterministic fallback).

    When the site DOES have a website on record but it's unreachable, we
    also attempt email-domain discovery as an alternative proposal (so a
    broken `oldwebsite.org` can be replaced by a live `currentdomain.org`
    derived from the org's email). A confirmed, reachable website is
    never overridden.
    """
    website = site.get("website")
    if not website:
        # ----- Branch A: website missing -----
        # Try email-domain discovery first (strongest signal).
        discovered = _discover_website_from_email(site, site_label, ctx=ctx)
        if discovered and discovered.get("high_quality"):
            # Website-specific identity gate
            _wg = _website_proposal_gate(site, discovered)
            if not _wg["accept"]:
                logger.warning(
                    f"[{site_label}] WEBSITE GATE BLOCKED proposal "
                    f"(email-domain): {discovered['url']} — {_wg['reason']}"
                )
            else:
                _ws_status = "proposed_update"
                _ws_conf = discovered["confidence"]
                if _wg.get("downgrade"):
                    _ws_status = "proposed_update_low_confidence"
                    _ws_conf = min(_ws_conf, 0.65)
                logger.info(
                    f"[{site_label}] discovered via email domain "
                    f"{discovered['url']} (conf={_ws_conf})"
                )
                return {
                    "status": _ws_status,
                    "current_value": None,
                    "proposed_value": discovered["url"],
                    "confidence": _ws_conf,
                    "reason": discovered["reason"],
                    "evidence_source_type": "email_domain",
                    "discovery": {
                        "source": "email_domain",
                        "score": discovered["score"],
                        "candidates": discovered["candidates"],
                    },
                }

        # Fall back to name-token + search discovery (search results, if any,
        # widen the candidate pool but never bypass the existing scoring).
        name_discovered = _discover_website(
            site, site_label, ctx=ctx, search_results=search_results
        )
        if name_discovered and name_discovered.get("high_quality"):
            # Website-specific identity gate
            _wg = _website_proposal_gate(site, name_discovered)
            if not _wg["accept"]:
                logger.warning(
                    f"[{site_label}] WEBSITE GATE BLOCKED proposal "
                    f"(name-discovery): {name_discovered['url']} — {_wg['reason']}"
                )
            else:
                _ws_status = "proposed_update"
                _ws_conf = name_discovered["confidence"]
                if _wg.get("downgrade"):
                    _ws_status = "proposed_update_low_confidence"
                    _ws_conf = min(_ws_conf, 0.65)
                logger.info(
                    f"[{site_label}] discovered candidate website "
                    f"{name_discovered['url']} (score={name_discovered['score']}, conf={_ws_conf})"
                )
                return {
                    "status": _ws_status,
                    "current_value": None,
                    "proposed_value": name_discovered["url"],
                    "confidence": _ws_conf,
                    "reason": name_discovered["reason"],
                    "evidence_source_type": "web_search",
                    "discovery": {
                        "source": "name_tokens",
                        "score": name_discovered["score"],
                        "candidates": name_discovered["candidates"],
                    },
                }

        # Prefer the email-domain low-quality result over name-token low-quality
        # if both exist (email signal is stronger even when unverified).
        weak = discovered or name_discovered
        if weak:
            logger.info(
                f"[{site_label}] discovery weak ({weak['url']} score={weak.get('score')})"
            )
            # If confidence >= 0.5 and there's a URL, surface as
            # proposed_update_low_confidence so reviewers see the candidate
            # in Detected Changes rather than silently swallowing it.
            if weak.get("confidence", 0) >= 0.5 and weak.get("url"):
                # Website-specific identity gate
                _wg = _website_proposal_gate(site, weak)
                if _wg["accept"]:
                    return {
                        "status": "proposed_update_low_confidence",
                        "current_value": None,
                        "proposed_value": weak["url"],
                        "confidence": weak["confidence"],
                        "reason": weak.get("reason") or "low_confidence_website",
                        "evidence_source_type": weak.get("source") or "web_search",
                        "discovery": {
                            "source": weak.get("source") or "name_tokens",
                            "score": weak.get("score"),
                            "candidates": weak.get("candidates"),
                        },
                    }
                else:
                    logger.warning(
                        f"[{site_label}] WEBSITE GATE BLOCKED weak proposal: "
                        f"{weak['url']} — {_wg['reason']}"
                    )
            return {
                "status": "uncertain",
                "current_value": None,
                "proposed_value": None,
                "confidence": weak["confidence"],
                "reason": "low_confidence_website",
                "evidence_source_type": weak.get("source") or "web_search",
                "discovery": {
                    "source": weak.get("source") or "name_tokens",
                    "score": weak.get("score"),
                    "candidates": weak.get("candidates"),
                },
            }
        # No usable discovery result
        return {
            "status": "not_evaluable",
            "current_value": None,
            "proposed_value": None,
            "confidence": 0.0,
            "reason": "Website not provided; no discovery match.",
            "evidence_source_type": None,
        }

    canonical = _canonical_url(website)

    # Cache lookup (per batch). Reuse evidence shape but rebind current_value
    # to this site's actual stored value so the output remains site-accurate.
    if ctx is not None and canonical and canonical in ctx.url_cache:
        ctx.incr_cache_hits()
        cached = dict(ctx.url_cache[canonical])  # shallow copy is enough
        cached["current_value"] = website
        cached["proposed_value"] = website
        return cached

    # `safe_get_text` returns body alongside status so downstream extractors
    # (phone, address) can mine the same page without a second fetch.
    result = safe_get_text(website, site_label=site_label, ctx=ctx)
    if result["ok"]:
        # --- Closure detection on reachable sites ---
        closure = _detect_closure(
            page_html=result.get("text"),
            search_results=search_results,
            status_code=result.get("status_code"),
        )
        if closure["detected"]:
            # --- Closure identity gate ---
            _cg = _closure_identity_gate(
                site, closure, result.get("text"), search_results,
            )
            if _cg["accept"]:
                _closure_conf = closure["confidence"]
                _closure_status = "closure_detected"
                if _cg.get("downgrade"):
                    _closure_conf = min(_closure_conf, 0.55)
                    _closure_status = "closure_detected"
                    logger.warning(
                        f"[{site_label}] CLOSURE DOWNGRADED on {website}: "
                        f"{_cg['reason']} (confidence capped at {_closure_conf})"
                    )
                else:
                    logger.warning(
                        f"[{site_label}] CLOSURE DETECTED on {website}: "
                        f"{'; '.join(closure['signals'])} (confidence={_closure_conf})"
                    )
                evidence = {
                    "status": _closure_status,
                    "current_value": website,
                    "proposed_value": website,
                    "confidence": _closure_conf,
                    "reason": f"Site may be permanently closed: {'; '.join(closure['signals'])}.",
                    "evidence_source_type": "web_request",
                    "closure_signals": closure["signals"],
                    **({"closure_gate": _cg["reason"]} if _cg.get("downgrade") else {}),
                }
            else:
                logger.warning(
                    f"[{site_label}] CLOSURE REJECTED on {website}: "
                    f"{_cg['reason']}"
                )
                evidence = {
                    "status": "confirmed",
                    "current_value": website,
                    "proposed_value": website,
                    "confidence": 0.85,
                    "reason": (
                        f"Website is live (HTTP {result['status_code']}); "
                        f"closure signal ignored: {_cg['reason']}"
                    ),
                    "evidence_source_type": "web_request",
                }
        else:
            evidence = {
                "status": "confirmed",
                "current_value": website,
                "proposed_value": website,
                "confidence": 0.95,
                "reason": f"Website is live and responsive (HTTP {result['status_code']}).",
                "evidence_source_type": "web_request",
            }
        # Stash page text for phone / address extractors.
        if ctx is not None and canonical and result.get("text"):
            with ctx.lock:
                ctx.page_text_cache.setdefault(canonical, result["text"])
    else:
        # Failed: do not block, mark uncertain/not_evaluable based on cause
        if result["error"] in ("timeout", "request_error:ConnectionError"):
            status = "uncertain"
            conf = 0.3
            reason = f"Website request failed: {result['error']}."
        elif result["error"] == "requests_not_installed":
            status = "not_evaluable"
            conf = 0.0
            reason = "Web request library unavailable; skipped."
        else:
            status = "uncertain"
            conf = 0.2
            reason = f"Website unreachable ({result['error']})."
        evidence = {
            "status": status,
            "current_value": website,
            "proposed_value": website,
            "confidence": conf,
            "reason": reason,
            "evidence_source_type": "web_request",
        }

        # --- Closure detection on unreachable sites ---
        # Even when the page didn't load, search snippets or HTTP 410
        # may indicate permanent closure.
        closure = _detect_closure(
            page_html=None,
            search_results=search_results,
            status_code=result.get("status_code"),
        )
        if closure["detected"]:
            # --- Closure identity gate (unreachable) ---
            _cg = _closure_identity_gate(
                site, closure, None, search_results,
            )
            if _cg["accept"]:
                _closure_conf = closure["confidence"]
                if _cg.get("downgrade"):
                    _closure_conf = min(_closure_conf, 0.55)
                    logger.warning(
                        f"[{site_label}] CLOSURE DOWNGRADED (unreachable) {website}: "
                        f"{_cg['reason']} (confidence capped at {_closure_conf})"
                    )
                else:
                    logger.warning(
                        f"[{site_label}] CLOSURE DETECTED (unreachable) {website}: "
                        f"{'; '.join(closure['signals'])} (confidence={_closure_conf})"
                    )
                evidence = {
                    "status": "closure_detected",
                    "current_value": website,
                    "proposed_value": website,
                    "confidence": _closure_conf,
                    "reason": f"Site may be permanently closed: {'; '.join(closure['signals'])}.",
                    "evidence_source_type": "web_request",
                    "closure_signals": closure["signals"],
                    **({"closure_gate": _cg["reason"]} if _cg.get("downgrade") else {}),
                }
            else:
                logger.warning(
                    f"[{site_label}] CLOSURE REJECTED (unreachable) {website}: "
                    f"{_cg['reason']}"
                )
                # Keep the original uncertain/not_evaluable evidence — don't
                # overwrite it with closure_detected.

        # The stored website is unreachable / low confidence. Try email-domain
        # discovery as an alternative proposal. Skip when the email lives at
        # the same domain as the broken website (no upgrade possible). The
        # confirmed branch above is left alone - a high-confidence website
        # is never overridden.
        if status != "not_evaluable":
            current_domain = _domain_of(website if website.lower().startswith(("http://", "https://")) else f"http://{website}")
            alt = _discover_website_from_email(
                site, site_label, ctx=ctx, avoid_domain=current_domain
            )
            if alt and alt.get("high_quality"):
                # Website-specific identity gate
                _wg = _website_proposal_gate(site, alt)
                if _wg["accept"]:
                    _ws_status = "proposed_update"
                    _ws_conf = alt["confidence"]
                    if _wg.get("downgrade"):
                        _ws_status = "proposed_update_low_confidence"
                        _ws_conf = min(_ws_conf, 0.65)
                    logger.info(
                        f"[{site_label}] proposing email-domain alternative "
                        f"{alt['url']} (current site unreachable)"
                    )
                    evidence = {
                        "status": _ws_status,
                        "current_value": website,
                        "proposed_value": alt["url"],
                        "confidence": _ws_conf,
                        "reason": f"Stored website unreachable; {alt['reason']}",
                        "evidence_source_type": "email_domain",
                        "discovery": {
                            "source": "email_domain",
                            "score": alt["score"],
                            "candidates": alt["candidates"],
                        },
                    }
                else:
                    logger.warning(
                        f"[{site_label}] WEBSITE GATE BLOCKED email-domain "
                        f"alternative: {alt['url']} — {_wg['reason']}"
                    )

    # Store in the batch cache so identical hosts later in the batch reuse it
    if ctx is not None and canonical:
        with ctx.lock:
            ctx.url_cache.setdefault(canonical, evidence)

    return evidence


def gather_evidence(site, site_label="unknown", ctx: Optional[BatchContext] = None):
    """
    Gathers external evidence for a given site.
    Web-derived fields use `safe_get`; other fields remain heuristic.

    Short-circuiting: once the canonical website probe completes (cached
    or fresh), no further per-site web fetches are made. We do not retry
    http vs https separately - `safe_get`'s redirect handling and the
    canonical cache key cover that already.

    Enrichment: when `ENABLE_WEB_SEARCH` is true, a single bounded web
    search is issued per site (cached per query in `ctx`). The results
    are passed to website discovery (as additional URL candidates) and
    to phone evidence (snippets are mined for phone numbers, with a
    score cap so they never bypass the existing decision thresholds).
    """
    # Single per-site enrichment search (cached). Cheap no-op when search
    # is disabled or no backend is reachable.
    search_results = _perform_site_search(site, ctx=ctx) if ENABLE_WEB_SEARCH else []

    website_ev = _website_evidence(site, site_label, ctx=ctx, search_results=search_results)
    web_ok = website_ev["status"] == "confirmed"
    closure_detected = website_ev["status"] == "closure_detected"

    # If website is unreachable or closed, downgrade web-scraped fields' confidence
    scrape_conf = 0.9 if web_ok else 0.5
    scrape_status = "confirmed" if web_ok else "uncertain"
    scrape_source = "web_scrape" if web_ok else None

    # Locate page text we may have fetched during the website probe or
    # during email/name-token discovery, so phone (and future) extractors
    # can mine it without an extra request.
    page_text: Optional[str] = None
    _website_url_for_crawl: Optional[str] = None
    if ctx is not None and ctx.page_text_cache:
        # Prefer the URL we ended up using for evidence (could be the stored
        # website, a discovered alternative, or both).
        for url_candidate in (
            website_ev.get("proposed_value"),
            website_ev.get("current_value"),
        ):
            if not url_candidate:
                continue
            key = _canonical_url(url_candidate)
            if key and key in ctx.page_text_cache:
                page_text = ctx.page_text_cache[key]
                _website_url_for_crawl = url_candidate
                break

    # --- Subpage crawl: discover /contact, /about pages and merge text ---
    # This gives phone/email extractors access to data that many sites
    # only publish on dedicated subpages, not the homepage.
    if page_text and _website_url_for_crawl and web_ok:
        subpage_urls = _discover_contact_pages(page_text, _website_url_for_crawl)
        if subpage_urls:
            subpage_texts = _fetch_subpage_texts(
                subpage_urls, site_label=site_label, ctx=ctx,
            )
            if subpage_texts:
                # Append subpage content after the homepage text so
                # extractors see a combined corpus.  We use a clear
                # separator so position-aware heuristics (e.g. "in_footer")
                # don't get confused by page boundaries.
                page_text = page_text + "\n<!-- subpage -->\n" + "\n<!-- subpage -->\n".join(subpage_texts)
                logger.info(
                    f"[{site_label}] subpage crawl: fetched {len(subpage_texts)} "
                    f"contact/about page(s) from {_website_url_for_crawl}"
                )

    phone_ev = _phone_evidence(
        site,
        page_text,
        site_label=site_label,
        web_ok=web_ok or website_ev["status"] == "proposed_update",
        ctx=ctx,
        search_results=search_results,
    )

    # Determine the accepted website domain for email domain alignment.
    # Use the confirmed/proposed website URL (not the stored one if it's
    # unreachable) so the email gate can verify domain consistency.
    _accepted_website_url = (
        website_ev.get("proposed_value") or website_ev.get("current_value")
    )
    _website_domain = _domain_of(_accepted_website_url) if _accepted_website_url else None

    email_ev = _email_evidence(
        site,
        page_text,
        site_label=site_label,
        web_ok=web_ok or website_ev["status"] == "proposed_update",
        website_domain=_website_domain,
        ctx=ctx,
        search_results=search_results,
    )

    # --- Source-tag classification (labelling only) ---
    site_name = site.get("name") or ""
    email_ev["source_tag"] = _classify_source_tag(
        "email", email_ev.get("proposed_value"), site_name,
    )
    website_ev["source_tag"] = _classify_source_tag(
        "website", website_ev.get("proposed_value"), site_name,
    )

    evidence = {
        "website": website_ev,
        "phone": phone_ev,
        "email": email_ev,
        "streetAddress": {
            "status": scrape_status,
            "current_value": site.get("streetAddress"),
            "proposed_value": site.get("streetAddress"),
            "confidence": scrape_conf,
            "reason": "Address found on contact page." if web_ok else "Website unreachable; address unverified.",
            "evidence_source_type": scrape_source,
        },
        "city": {
            "status": scrape_status,
            "current_value": site.get("city"),
            "proposed_value": site.get("city"),
            "confidence": scrape_conf,
            "reason": "Address found on contact page." if web_ok else "Website unreachable; city unverified.",
            "evidence_source_type": scrape_source,
        },
        "state": {
            "status": scrape_status,
            "current_value": site.get("state"),
            "proposed_value": site.get("state"),
            "confidence": scrape_conf,
            "reason": "Address found on contact page." if web_ok else "Website unreachable; state unverified.",
            "evidence_source_type": scrape_source,
        },
        "zip": {
            "status": scrape_status,
            "current_value": site.get("zip"),
            "proposed_value": site.get("zip"),
            "confidence": scrape_conf,
            "reason": "Address found on contact page." if web_ok else "Website unreachable; zip unverified.",
            "evidence_source_type": scrape_source,
        },
        "organization_name": {
            "status": scrape_status,
            "current_value": site.get("name"),
            "proposed_value": site.get("name"),
            "confidence": 0.98 if web_ok else 0.5,
            "reason": "Organization name matches website title." if web_ok else "Website unreachable; name unverified.",
            "evidence_source_type": scrape_source,
        },
        "status": {
            "status": "closure_detected" if closure_detected
                      else ("confirmed" if web_ok else "uncertain"),
            "current_value": "closed" if closure_detected
                             else ("open" if web_ok else "unreachable"),
            "proposed_value": "closed" if closure_detected
                              else ("open" if web_ok else "unreachable"),
            "confidence": website_ev.get("confidence", 0.7) if closure_detected
                          else (1.0 if web_ok else 0.3),
            "reason": website_ev.get("reason", "Possible closure detected.") if closure_detected
                      else ("Website is active." if web_ok else "Website did not respond."),
            "evidence_source_type": "web_request",
            **({"closure_signals": website_ev.get("closure_signals", [])} if closure_detected else {}),
        },
    }

    # --- Geocoding cross-validation (additive, does NOT alter scores) ---
    # Provides reviewers with an independent geographic consistency check.
    # The result is informational only — it never modifies confidence,
    # classifications, or proposed values.
    try:
        geo_result = geocode_validate(site, site_label=site_label, ctx=ctx)
        evidence["geo_validation"] = geo_result
    except Exception as e:
        logger.warning("[%s] geocode_validate error: %s", site_label, e)
        evidence["geo_validation"] = {
            "geocoded": False,
            "note": f"geocode error: {type(e).__name__}",
        }

    return evidence


def analyze_evidence(evidence):
    """
    Analyzes the gathered evidence to produce a summary.
    """
    overall_confidence = 0.0
    confidence_count = 0

    for _field, data in evidence.items():
        if data and isinstance(data, dict) and "confidence" in data:
            overall_confidence += data["confidence"]
            confidence_count += 1

    if confidence_count > 0:
        overall_confidence /= confidence_count

    if overall_confidence > 0.8:
        decision = "candidate_approved"
    elif overall_confidence > 0.5:
        decision = "needs_exception_review"
    else:
        decision = "deferred_low_confidence"

    return {
        "overall_confidence": round(overall_confidence, 2),
        "decision": decision,
    }


def _process_single_site(idx, total, site, ctx: Optional[BatchContext] = None):
    """
    Process one site end-to-end. Always returns a result dict; never raises.
    Designed to run safely inside a thread pool.
    """
    site_id = site.get("id") or "unknown"
    site_name = site.get("name") or "unknown"
    site_label = f"{idx}/{total} {site_id} - {site_name}"

    logger.info(f"[{site_label}] start processing")
    try:
        evidence = gather_evidence(site, site_label=site_label, ctx=ctx)
        summary = analyze_evidence(evidence)
        logger.info(f"[{site_label}] completed (overall_confidence={summary['overall_confidence']})")
        return {
            "site_id": site_id,
            "summary": summary,
            "fields": evidence,
        }
    except Exception as e:
        # Should never happen because gather_evidence is defensive,
        # but if it does, isolate the failure to this site.
        logger.warning(f"[{site_label}] processing error: {type(e).__name__}: {e}")
        logger.info(f"[{site_label}] completed with error (continuing batch)")
        return {
            "site_id": site_id,
            "summary": {"overall_confidence": 0.0, "decision": "deferred_low_confidence"},
            "fields": {},
            "error": f"{type(e).__name__}: {e}",
        }


def generate_evidence_report(sites, max_workers=MAX_WORKERS):
    """
    Generates a web evidence report for a list of sites, processing them
    concurrently with a bounded thread pool.

    - Concurrency is capped (default MAX_WORKERS) to avoid overwhelming hosts.
    - A single pooled HTTP session + per-batch URL cache reduce duplicate work.
    - Failures on one site never block the rest of the batch.
    - Output order matches the input site order for deterministic JSON diffs.
    - Run-level timing + cache stats are logged at the end.
    """
    total = len(sites)
    if total == 0:
        return []

    # Cap workers to the actual batch size; never go below 1.
    workers = max(1, min(max_workers, total))
    backend = "off"
    if ENABLE_WEB_SEARCH:
        if SERPER_API_KEY:
            backend = "serper"
        elif BING_SEARCH_API_KEY:
            backend = "bing-api"
        else:
            backend = "ddg-html"
    logger.info(
        f"Running web evidence collection with {workers} parallel workers "
        f"(web_search={'on' if ENABLE_WEB_SEARCH else 'off'}, backend={backend}, "
        f"max_results={WEB_SEARCH_MAX_RESULTS})"
    )

    ctx = BatchContext(session=_build_session())
    start = time.perf_counter()

    # Pre-allocate to preserve input order in the final report.
    results = [None] * total

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_index = {
                executor.submit(_process_single_site, idx + 1, total, site, ctx): idx
                for idx, site in enumerate(sites)
            }
            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    # Defensive: _process_single_site already swallows exceptions,
                    # but if anything slips through, keep the batch alive.
                    site = sites[idx]
                    site_id = site.get("id") or "unknown"
                    logger.warning(f"[{site_id}] worker error: {type(e).__name__}: {e}")
                    results[idx] = {
                        "site_id": site_id,
                        "summary": {"overall_confidence": 0.0, "decision": "deferred_low_confidence"},
                        "fields": {},
                        "error": f"worker:{type(e).__name__}: {e}",
                    }
    finally:
        elapsed = time.perf_counter() - start
        avg = elapsed / total if total else 0.0
        logger.info(
            f"Batch finished in {elapsed:.2f}s "
            f"(avg {avg:.2f}s/site, requests={ctx.requests_made}, "
            f"cache_hits={ctx.cache_hits}, unique_urls={len(ctx.url_cache)}, "
            f"discovery_attempts={ctx.discovery_attempts}, discovery_hits={ctx.discovery_hits}, "
            f"search_attempts={ctx.search_attempts}, search_hits={ctx.search_hits})"
        )
        if ctx.session is not None:
            try:
                ctx.session.close()
            except Exception:
                pass

    return results


def main():
    """
    Main function to generate the web evidence report.
    """
    parser = argparse.ArgumentParser(description="Generate a web evidence report for a batch of sites.")
    parser.add_argument("input_file", help="Path to the input sites_batch.json file.")
    parser.add_argument("output_file", help="Path to the output web_evidence_report.json file.")
    parser.add_argument(
        "--workers",
        type=int,
        default=MAX_WORKERS,
        help=f"Number of concurrent workers (default: {MAX_WORKERS}, max recommended: 10).",
    )
    args = parser.parse_args()

    # Clamp workers to a safe range so callers can't accidentally hammer hosts.
    workers = max(1, min(args.workers, 10))

    try:
        with open(args.input_file, "r", encoding="utf-8") as f:
            sites_batch = json.load(f)
    except FileNotFoundError:
        logger.error(f"Input file not found at {args.input_file}")
        return
    except json.JSONDecodeError:
        logger.error(f"Could not decode JSON from {args.input_file}")
        return

    if "sites" in sites_batch:
        sites = sites_batch["sites"]
    else:
        sites = sites_batch  # Assume the file is a list of sites

    logger.info(f"Processing {len(sites)} sites (timeout={REQUEST_TIMEOUT}s, max_retries={MAX_RETRIES}, workers={workers})")
    evidence_report = generate_evidence_report(sites, max_workers=workers)

    with open(args.output_file, "w", encoding="utf-8") as f:
        json.dump(evidence_report, f, indent=4)

    logger.info(f"Web evidence report generated at {args.output_file}")


if __name__ == "__main__":
    main()
