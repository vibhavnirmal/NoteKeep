# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy application code
COPY . .

# Create directory for database
RUN mkdir -p /app/data

# Create entrypoint script
RUN echo '#!/bin/sh\n\
set -e\n\
\n\
echo "🔄 Running database migrations..."\n\
python migrate.py\n\
\n\
echo "🚀 Starting application..."\n\
exec "$@"\n\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

EXPOSE 8696

# Use entrypoint to run migrations before starting the app
ENTRYPOINT ["/app/entrypoint.sh"]

# Run both web app and telegram poller
CMD ["sh", "-c", "python -m app.run_telegram_poller & uvicorn app.main:app --host 0.0.0.0 --port 8696"]
