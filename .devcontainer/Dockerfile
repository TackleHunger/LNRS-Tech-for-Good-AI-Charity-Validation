# GitHub Codespaces Dockerfile for Tackle Hunger Charity Validation
# 
# Extends the existing security-optimized Alpine Linux Dockerfile with 
# additional development tools for GitHub Codespaces environment.

# Use the existing project Dockerfile AS base
FROM alpine:3.18 AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies with additional development tools for Codespaces
RUN apk update && \
    apk upgrade && \
    apk add --no-cache \
    python3 \
    python3-dev \
    py3-pip \
    curl \
    git \
    ca-certificates \
    bash \
    nano \
    vim \
    less \
    tree \
    htop \
    build-base \
    libffi-dev \
    openssl-dev \
    wget \
    && rm -rf /var/cache/apk/*

# Create non-root user for security
RUN addgroup -g 1000 tacklehunger && \
    adduser -D -s /bin/bash -u 1000 -G tacklehunger tacklehunger && \
    mkdir -p /home/tacklehunger/.local/bin && \
    chown -R tacklehunger:tacklehunger /home/tacklehunger

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies with additional development packages for Codespaces
RUN python3 -m pip install --upgrade pip setuptools wheel && \
    python3 -m pip install -r requirements.txt && \
    python3 -m pip install pydantic-settings ipython jupyter && \
    python3 -m pip check

# Copy project files with proper ownership
COPY --chown=tacklehunger:tacklehunger src/ ./src/
COPY --chown=tacklehunger:tacklehunger tests/ ./tests/
COPY --chown=tacklehunger:tacklehunger scripts/ ./scripts/
COPY --chown=tacklehunger:tacklehunger docs/ ./docs/
COPY --chown=tacklehunger:tacklehunger .devcontainer/ ./.devcontainer/
COPY --chown=tacklehunger:tacklehunger .env.example .
COPY --chown=tacklehunger:tacklehunger pytest.ini .

# Create .env from example if it doesn't exist
RUN if [ ! -f .env ]; then cp .env.example .env && chown tacklehunger:tacklehunger .env; fi

# Switch to non-root user
USER tacklehunger

# Set Python path to include src directory
ENV PYTHONPATH="/app/src"
ENV PATH="/home/tacklehunger/.local/bin:$PATH"

# Expose port for any future web services
EXPOSE 8000

# Health check to ensure container is working
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import sys; print('Container healthy')" || exit 1

# Default command for interactive development
CMD ["/bin/bash"]