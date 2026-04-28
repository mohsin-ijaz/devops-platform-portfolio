FROM python:3.11-slim

WORKDIR /app

# Install system dependencies, kubectl, and gcloud SDK
RUN apt-get update && apt-get install -y \
    curl \
    apt-transport-https \
    ca-certificates \
    gnupg \
    && mkdir -p /usr/share/keyrings \
    && curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee /etc/apt/sources.list.d/google-cloud-sdk.list \
    && apt-get update && apt-get install -y google-cloud-cli google-cloud-cli-gke-gcloud-auth-plugin kubectl \
    && rm -rf /var/lib/apt/lists/*

# Set environment variable for gke-gcloud-auth-plugin
ENV USE_GKE_GCLOUD_AUTH_PLUGIN=True

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY controllers/ ./controllers/
COPY app.py scheduler.py mgmt_manual_stop_start.py ./
COPY .env* ./

# Expose Streamlit port
EXPOSE 8501

# Default command (can be overridden in docker-compose)
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
