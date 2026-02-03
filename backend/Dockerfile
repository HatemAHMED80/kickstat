FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install production requirements
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p data/models

# Expose port (Render uses PORT env variable)
EXPOSE 10000

# Run the application with PORT from environment
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
