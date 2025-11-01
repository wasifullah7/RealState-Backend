
FROM python:3.11-slim


ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1


WORKDIR /app


RUN apt-get update && apt-get install -y \
    wget gnupg unzip curl \
    libnss3 libnspr4 libx11-6 libx11-xcb1 libxcomposite1 libxdamage1 \
    libxrandr2 libxext6 libxfixes3 libxi6 libxrender1 libxss1 libglib2.0-0 \
    libdbus-1-3 libxtst6 libxshmfence1 xvfb fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


RUN playwright install --with-deps chromium firefox


COPY . .

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
