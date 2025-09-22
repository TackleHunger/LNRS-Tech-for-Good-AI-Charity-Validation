# Security-optimized Dockerfile for GitHub Codespaces - Tackle Hunger Charity Validation
# 
# This Dockerfile provides maximum security with minimal vulnerabilities
# using Alpine Linux base image, customized for Codespaces development.

# Use Python 3.13 Alpine for minimal attack surface and better security
FROM python:3.13-alpine

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /workspace

# Install minimal system dependencies with Alpine package manager
# Add bash and git for better development experience in Codespaces
RUN apk update && \
    apk upgrade && \
    apk add --no-cache \
    bash \
    curl \
    git \
    ca-certificates \
    sudo \
    openssh-client \
    && rm -rf /var/cache/apk/*

# Create non-root user for security early
RUN addgroup -g 1000 tacklehunger && \
    adduser -D -s /bin/bash -u 1000 -G tacklehunger tacklehunger && \
    echo 'tacklehunger ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

# Copy requirements from the repo root (build context is repo root)
COPY requirements.txt /tmp/requirements.txt

# Install Python dependencies with security updates
RUN python -m pip install --upgrade pip && \
    python -m pip install --upgrade setuptools wheel && \
    python -m pip install -r /tmp/requirements.txt && \
    python -m pip check && \
    rm /tmp/requirements.txt

# Create workspace directories with proper ownership
RUN mkdir -p /workspace && \
    chown -R tacklehunger:tacklehunger /workspace

# Switch to non-root user
USER tacklehunger

# Set Python path to include src directory
ENV PYTHONPATH="/workspace/src"

# Default command for Codespaces (keeps container running)
CMD ["sleep", "infinity"]