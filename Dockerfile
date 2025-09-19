# Use official Python runtime
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application files
COPY . .

# Expose Flask port
EXPOSE 10000

# Set environment variables
ENV FLASK_ENV=production \
    FLASK_APP=app.py \
    FLASK_RUN_HOST=0.0.0.0 \
    FLASK_RUN_PORT=10000

# Ensure migrations or setup scripts run if needed
# e.g., RUN python fix_database.py

# Start the Gunicorn server
CMD ["gunicorn", "--workers", "3", "--bind", "0.0.0.0:10000", "app:app"]
