# Use Python 3.13 slim with Debian 12 (bookworm) for reproducible builds
FROM python:3.13-slim-bookworm

# Add security labels
LABEL security.capabilities.drop="ALL" \
      security.capabilities.add="NET_BIND_SERVICE SYS_CHROOT"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget=1.21.3-1+deb12u1 \
    gnupg=2.2.40-1.1+deb12u2 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers as root (needed for system dependencies)
RUN python -m playwright install chromium --with-deps

# Create non-root user
RUN useradd -m -u 1000 appuser

# Copy Playwright browsers to appuser's home directory (preserve ms-playwright structure)
RUN mkdir -p /home/appuser/.cache/ms-playwright && \
    cp -r /root/.cache/ms-playwright/* /home/appuser/.cache/ms-playwright/ && \
    chown -R appuser:appuser /home/appuser/.cache

# Switch back to root to copy files (owned by root)
USER root

# Copy application code (owned by root)
COPY src/ ./src/
COPY templates/ ./templates/
COPY main.py .
COPY locations_cache.json .
COPY visitors.json .
COPY calendars/ ./calendars/

# Ensure appuser can read the files
RUN chown -R appuser:appuser /app && \
    chmod -R 755 /app/src /app/templates /app/main.py

# Switch to non-root user for running
USER appuser

# Set Playwright browsers path
ENV PLAYWRIGHT_BROWSERS_PATH=/home/appuser/.cache/ms-playwright

# Expose port
EXPOSE 8080

# Add healthcheck using Python urllib
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health', timeout=5)" || exit 1

# Run the Flask web app with gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:8080", "--timeout", "120", "--workers", "2", "src.app:app"]
