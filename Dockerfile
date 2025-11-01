
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# Install system dependencies in a single layer to reduce image size
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg unzip curl \
    libnss3 libnspr4 libx11-6 libx11-xcb1 libxcomposite1 libxdamage1 \
    libxrandr2 libxext6 libxfixes3 libxi6 libxrender1 libxss1 libglib2.0-0 \
    libdbus-1-3 libxtst6 libxshmfence1 xvfb fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Install only Chromium (not Firefox) to reduce build time and image size
RUN playwright install --with-deps chromium

# Copy application code (excluding files in .dockerignore)
COPY . .

# Clean up any temporary files and reduce image size
RUN find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true && \
    find . -type f -name "*.pyc" -delete && \
    find . -type f -name "*.pyo" -delete

EXPOSE 8000

# Railway will set PORT environment variable
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
