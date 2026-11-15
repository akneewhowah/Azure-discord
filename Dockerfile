# Lightweight official Python runtime
FROM python:3.11-slim

# Prevent Python from writing .pyc files & buffer stdout/stderr for Azure logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first for Docker caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Expose HTTP health check port (used by Azure Container Apps / App Service)
EXPOSE 8080

# Launch the Discord Bot
CMD ["python", "bot.py"]
