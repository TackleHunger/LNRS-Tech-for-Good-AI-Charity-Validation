# Dockerfile for Tackle Hunger Charity Validation
# 
# Simple, secure Docker environment for volunteers working on charity validation.
# Based on Alpine Linux for security and small size.

FROM python:3.13-alpine

# Set environment variables for better Python behavior
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apk update && \
    apk upgrade && \
    apk add --no-cache \
    curl \
    git \
    ca-certificates \
    && rm -rf /var/cache/apk/*

# Create non-root user for security
RUN addgroup -g 1000 tacklehunger && \
    adduser -D -s /bin/sh -u 1000 -G tacklehunger tacklehunger

# Install Python dependencies
COPY requirements.txt .
RUN python -m pip install --upgrade pip && \
    python -m pip install --upgrade setuptools wheel && \
    python -m pip install -r requirements.txt && \
    python -m pip check

# Copy project files
COPY --chown=tacklehunger:tacklehunger src/ ./src/
COPY --chown=tacklehunger:tacklehunger tests/ ./tests/
COPY --chown=tacklehunger:tacklehunger scripts/ ./scripts/
COPY --chown=tacklehunger:tacklehunger docs/ ./docs/
COPY --chown=tacklehunger:tacklehunger .env.example .
COPY --chown=tacklehunger:tacklehunger pytest.ini .

# Set up environment and pytest cache
RUN if [ ! -f .env ]; then cp .env.example .env && chown tacklehunger:tacklehunger .env; fi && \
    mkdir -p /app/.pytest_cache/v/cache && \
    chown -R tacklehunger:tacklehunger /app/.pytest_cache && \
    chmod -R 755 /app/.pytest_cache

# Switch to non-root user
USER tacklehunger

# Set Python path
ENV PYTHONPATH="/app/src"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import sys; print('Container healthy')" || exit 1

# Default: run connectivity test to verify everything works
CMD ["python", "scripts/test_connectivity.py"]