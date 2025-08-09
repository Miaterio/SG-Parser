# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Chrome and Selenium
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    xvfb \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p uploads temp logs

# Set environment variables for Chrome
ENV CHROME_BINARY=/usr/bin/google-chrome
ENV CHROME_ARGS=--no-sandbox,--headless,--disable-gpu,--disable-dev-shm-usage,--disable-extensions,--no-first-run,--disable-default-apps
ENV SELENIUM_HEADLESS=true
ENV FLASK_ENV=production

# Expose port (Render will set PORT env var)
EXPOSE $PORT

# Run the application
CMD gunicorn --bind 0.0.0.0:$PORT --timeout 300 --workers 1 app:app