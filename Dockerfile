# Security-optimized Dockerfile for Tackle Hunger Charity Validation
# 
# This Dockerfile provides maximum security with minimal vulnerabilities
# using Alpine Linux base image.

# Use Python 3.13 Alpine for minimal attack surface and better security
FROM python:3.13-alpine

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install minimal system dependencies with Alpine package manager
RUN apk update && \
    apk upgrade && \
    apk add --no-cache \
    curl \
    git \
    ca-certificates \
    && rm -rf /var/cache/apk/*

# Create non-root user for security early
RUN addgroup -g 1000 tacklehunger && \
    adduser -D -s /bin/sh -u 1000 -G tacklehunger tacklehunger

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies with security updates
RUN python -m pip install --upgrade pip && \
    python -m pip install --upgrade setuptools wheel && \
    python -m pip install -r requirements.txt && \
    python -m pip check

# Copy project files with proper ownership
COPY --chown=tacklehunger:tacklehunger src/ ./src/
COPY --chown=tacklehunger:tacklehunger tests/ ./tests/
COPY --chown=tacklehunger:tacklehunger scripts/ ./scripts/
COPY --chown=tacklehunger:tacklehunger docs/ ./docs/
COPY --chown=tacklehunger:tacklehunger .env.example .
COPY --chown=tacklehunger:tacklehunger pytest.ini .

# Create .env from example if it doesn't exist
RUN if [ ! -f .env ]; then cp .env.example .env && chown tacklehunger:tacklehunger .env; fi

# Create pytest cache directory with proper permissions
RUN mkdir -p /app/.pytest_cache && chown tacklehunger:tacklehunger /app/.pytest_cache

# Switch to non-root user
USER tacklehunger

# Expose port for any future web services
EXPOSE 8000

# Set Python path to include src directory
ENV PYTHONPATH="/app/src"

# Health check to ensure container is working
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import sys; print('Container healthy')" || exit 1

# Default command runs the connectivity test
CMD ["python", "scripts/test_connectivity.py"]