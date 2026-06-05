# Use the official Python base image
FROM python:3.11-slim

# Install system dependencies (including Chromium dependencies for Playwright)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Set local working directory
WORKDIR /app

# Copy requirement files first to utilize Docker build cache
COPY requirements.txt /app/requirements.txt

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (if Playwright is used in browser automation steps)
RUN playwright install --with-deps chromium

# Copy the rest of the application files
COPY . /app

# Expose port (Cloud Run sets the PORT env variable automatically)
EXPOSE 8080

WORKDIR /app/backend
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
