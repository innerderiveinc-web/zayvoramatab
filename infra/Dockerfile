FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app

# Ensure non-root execution
RUN addgroup --system matab && adduser --system --group matab
USER matab

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD curl -f http://127.0.0.1:8000/api/v1/health/live || exit 1

CMD ["python3", "-m", "apps.api.main"]
