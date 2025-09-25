# Firewall Configuration for GitHub Copilot Development

## Required Network Access

To enable GitHub Copilot coding agents to work with the Tackle Hunger charity validation system, the following network endpoints must be accessible:

### Core API Endpoints

**Tackle Hunger GraphQL APIs:**
- `api.sboc.us/graphql` (Production API)
- `stagingapi.sboc.us/graphql` (Staging API)
- `devapi.sboc.us/graphql` (Dev API)
- Port: 443 (HTTPS)
- Protocol: HTTPS/GraphQL over POST

### GitHub and Development Services

**GitHub Services:**
- `github.com` (Repository access)
- `api.github.com` (GitHub API)
- `copilot-proxy.githubusercontent.com` (Copilot service)
- Port: 443 (HTTPS)

**Python Package Index:**
- `pypi.org` (Package downloads)
- `files.pythonhosted.org` (Package files)
- Port: 443 (HTTPS)

## Firewall Rules Configuration

### For Corporate/Enterprise Firewalls

**Allow Outbound HTTPS (port 443) to:**
```bash
# Tackle Hunger APIs
*.sboc.us

# GitHub Services
*.github.com
*.githubusercontent.com

# Python Package Index
*.pypi.org
*.pythonhosted.org
```

### For Application-Level Firewall (if applicable)

**Python requests library configuration:**
```python
# Add to your environment configuration if using proxy
import os

# If behind corporate proxy
os.environ['HTTPS_PROXY'] = 'https://your-proxy:port'
os.environ['HTTP_PROXY'] = 'http://your-proxy:port'

### Security Considerations

**Rate Limiting:**
- Implement rate limiting for API calls (default: 10 requests/second)
- Use exponential backoff for failed requests
- Monitor API usage to avoid quota exhaustion

**API Key Security:**
- Store API keys in GitHub environment secrets only
- Never commit API keys to source code
- Use environment-specific keys (dev vs. staging vs. production)
- Rotate keys regularly per security policy

**Data Privacy:**
- All charity data transmissions use HTTPS encryption
- API authentication uses Bearer token + secret
- No PII is logged in application logs
- Follow GDPR/privacy guidelines for charity contact information

## Testing Connectivity

Use the provided connectivity test script:

```bash
python scripts/test_connectivity.py
```

This will verify access to all required endpoints and report any connectivity issues.

## Troubleshooting

**Common Issues:**

1. **SSL Certificate Errors:**
   - Update certificate bundle: `pip install --upgrade certifi`
   - Check corporate certificate requirements

2. **Proxy Authentication:**
   - Verify proxy credentials and configuration
   - Test direct connection if proxy issues persist

3. **Rate Limiting:**
   - Implement exponential backoff in API calls
   - Monitor API usage and adjust request frequency

4. **DNS Resolution:**
   - Verify DNS can resolve all required domains
   - Check for internal DNS overrides or blocks

Contact your IT security team if you need help configuring these firewall rules.
