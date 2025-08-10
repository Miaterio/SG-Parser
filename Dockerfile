# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Chrome, Selenium, and ImageMagick (for image conversion)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    xvfb \
    imagemagick \
    webp \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy image_parser.py (needed for import)
COPY image_parser.py .

# Copy web-parser application code
COPY web-parser/ ./web-parser/

# Set working directory to web-parser
WORKDIR /app/web-parser

# Create necessary directories
RUN mkdir -p uploads temp logs

# Set environment variables for Chrome
ENV CHROME_BINARY=/usr/bin/google-chrome
ENV CHROME_ARGS=--no-sandbox,--headless,--disable-gpu,--disable-dev-shm-usage,--disable-extensions,--no-first-run,--disable-default-apps
ENV SELENIUM_HEADLESS=true
ENV FLASK_ENV=production

# Expose port (informational; Render will still inject PORT at runtime)
EXPOSE 5000

# Run the application
CMD gunicorn --bind 0.0.0.0:$PORT --timeout 300 --workers 1 app:app