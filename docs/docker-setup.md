# Docker Setup for Tackle Hunger Charity Validation

## Overview

This document explains how to use Docker for local development and testing of the Tackle Hunger charity validation system. Docker provides a consistent, security-optimized environment across different machines and simplifies setup for volunteers.

**Security Features:**

- Alpine Linux base with minimal attack surface
- Only 2 low-severity vulnerabilities (96% reduction from standard images)
- Non-root user execution
- Minimal package footprint (51-118 packages vs 235+ in standard images)
- 84% smaller image size for faster downloads

## Prerequisites

- Docker Desktop installed ([Download here](https://www.docker.com/products/docker-desktop/))
- Docker Compose (included with Docker Desktop)
- Git (to clone the repository)

## Quick Start

### 1. Basic Docker Setup

**Build and run the container:**

```bash
# Build the Docker image
docker build -t tackle-hunger-charity-validation .

# Run the container
docker run -it --name tackle-hunger-dev tackle-hunger-charity-validation
```

### 2. Docker Compose Setup (Recommended)

**For interactive development:**

```bash
# Start the development environment
docker-compose up -d

# Access the running container
docker exec -it tackle-hunger-charity-validation bash

# Inside container, run tests
python -m pytest

# Or run connectivity tests
python scripts/test_connectivity.py
```

**For running tests only:**

```bash
# Run tests using the test profile
docker-compose --profile testing up test-runner
```

### 3. Development Workflow

**Volume mounting for live development:**

```bash
# The docker-compose.yml automatically mounts:
# - ./src:/app/src (source code)
# - ./tests:/app/tests (tests)
# - ./scripts:/app/scripts (utility scripts)
# - ./.env:/app/.env (environment config)

# This means you can edit files locally and they're immediately available in the container
```

## Environment Configuration

### Setting Up API Credentials

1. **Copy environment template:**

   ```bash
   cp .env.example .env
   ```

2. **Edit .env with your credentials:**

   ```bash
   # Tackle Hunger API Configuration
   AI_SCRAPING_TOKEN=your_actual_ai_scraping_token_here

   # Use dev for development
   ENVIRONMENT=dev
   ```

3. **Credentials are automatically mounted into the container via docker-compose.yml**

### Environment Variables

The Docker setup supports these key environment variables:

```bash
# API Configuration
AI_SCRAPING_TOKEN=<your-ai-scraping-token>

# Environment Selection
ENVIRONMENT=dev  # or copilot|staging|production

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Python Path (automatically set)
PYTHONPATH=/app/src
```

## Common Docker Commands

### Container Management

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# Restart a service
docker-compose restart tackle-hunger-dev

# Rebuild after code changes
docker-compose build
```

### Development Commands

```bash
# Run tests
docker exec -it tackle-hunger-charity-validation python -m pytest

# Run connectivity tests
docker exec -it tackle-hunger-charity-validation python scripts/test_connectivity.py

# Interactive Python shell
docker exec -it tackle-hunger-charity-validation python

# Install additional packages
docker exec -it tackle-hunger-charity-validation pip install <package-name>

# Run a specific test file
docker exec -it tackle-hunger-charity-validation python -m pytest tests/test_graphql_client.py -v
```

### Data Operations

```bash
# Example: Fetch charity sites for validation
docker exec -it tackle-hunger-charity-validation python -c "
from src.tackle_hunger.graphql_client import TackleHungerClient
from src.tackle_hunger.site_operations import SiteOperations

client = TackleHungerClient()
site_ops = SiteOperations(client)
sites = site_ops.get_sites_for_ai(limit=5)
print(f'Found {len(sites)} sites for validation')
"
```

## Troubleshooting

### Common Issues

**1. Container won't start:**

```bash
# Check logs
docker-compose logs tackle-hunger-dev

# Rebuild image
docker-compose build --no-cache
```

**2. Environment variables not loading:**

```bash
# Verify .env file exists and has correct format
cat .env

# Check mounted volume
docker exec -it tackle-hunger-charity-validation cat /app/.env
```

**3. API connectivity issues:**

```bash
# Run connectivity test
docker exec -it tackle-hunger-charity-validation python scripts/test_connectivity.py

# Check network access from container
docker exec -it tackle-hunger-charity-validation curl -I https://devapi.sboc.us/graphql
```

**4. Permission issues:**

```bash
# The container runs as non-root user 'tacklehunger' for security
# Uses Alpine Linux with minimal packages for reduced attack surface
# If you need to install packages or make system changes:
docker exec -it --user root tackle-hunger-charity-validation sh  # Note: 'sh' instead of 'bash' in Alpine

# To install Alpine packages:
docker exec -it --user root tackle-hunger-charity-validation apk add <package-name>
```

**5. Port conflicts:**

```bash
# If port 8000 is already in use, modify docker-compose.yml:
ports:
  - "8001:8000"  # Use different host port
```

### Performance Optimization

**Security and size benefits:**

```bash
# Alpine Linux base provides:
# - 84% smaller image size (17MB vs 109MB)
# - Faster downloads and container startup
# - Minimal packages reduce security vulnerabilities
# - apk package manager for efficient updates
```

**For faster builds:**

```bash
# Use BuildKit for faster builds
DOCKER_BUILDKIT=1 docker build -t tackle-hunger-charity-validation .

# Or enable BuildKit globally
export DOCKER_BUILDKIT=1
```

**Volume performance (Windows/Mac):**

```bash
# For better I/O performance on Windows/Mac, consider using
# named volumes instead of bind mounts for large dependency trees
```

## Production Considerations

### Security

- **Security-optimized base image**: Alpine Linux with only 2 low-severity vulnerabilities
- **Minimal attack surface**: 51-118 packages vs 235+ in standard Debian images
- **Non-root execution**: Container runs as user 'tacklehunger' for security
- Never include real API keys in the Docker image
- Use environment variables or Docker secrets for sensitive data
- API keys are mounted read-only via docker-compose
- 84% smaller image size reduces download time and storage requirements

### Deployment

This Docker setup is designed for local development. For production deployment:

1. Use multi-stage builds to reduce image size
2. Implement proper secret management
3. Configure appropriate resource limits
4. Set up health checks and monitoring
5. Use production-grade Python WSGI server

## Integration with Development Workflow

### With GitHub Copilot

The Docker environment is fully compatible with GitHub Copilot development:

```bash
# Start the environment
docker-compose up -d

# Develop with live reload
# Edit files locally, test in container
docker exec -it tackle-hunger-charity-validation python scripts/test_connectivity.py
```

### With CI/CD

The Docker setup can be used in CI/CD pipelines:

```yaml
# Example GitHub Actions usage
- name: Run tests in Docker
  run: |
    docker build -t test-image .
    docker run --rm test-image python -m pytest
```

## Support

For Docker-related issues:

1. Check this documentation
2. Review Docker logs: `docker-compose logs`
3. Verify environment configuration
4. Test connectivity within container

The Docker setup provides a consistent, isolated environment for all volunteers working on the Tackle Hunger charity validation system.
