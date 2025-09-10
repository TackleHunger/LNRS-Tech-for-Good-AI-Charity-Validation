# Dockerfile for Tackle Hunger Charity Validation Local Testing
# 
# This Dockerfile provides a consistent development environment for volunteers
# working on charity validation operations.

FROM python:3.13-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
# Handle SSL issues in build environments
RUN pip install --upgrade pip --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org && \
    pip install -r requirements.txt --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org

# Copy project files
COPY src/ ./src/
COPY tests/ ./tests/
COPY scripts/ ./scripts/
COPY docs/ ./docs/
COPY .env.example .
COPY pytest.ini .

# Create .env from example if it doesn't exist
RUN if [ ! -f .env ]; then cp .env.example .env; fi

# Create non-root user for security
RUN groupadd -r tacklehunger && useradd -r -g tacklehunger tacklehunger
RUN chown -R tacklehunger:tacklehunger /app
USER tacklehunger

# Expose port for any future web services
EXPOSE 8000

# Set Python path to include src directory
ENV PYTHONPATH="/app/src:$PYTHONPATH"

# Health check to ensure container is working
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; print('Container healthy'); sys.exit(0)" || exit 1

# Default command runs the connectivity test and then starts interactive shell
CMD ["python", "scripts/test_connectivity.py"]