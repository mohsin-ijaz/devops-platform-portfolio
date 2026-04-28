# Cloud SQL Backup Validator - Phase 2
FROM gcr.io/google.com/cloudsdktool/google-cloud-cli:slim

WORKDIR /app

# Install Python DB driver for Phase 2 deep validation
COPY requirements.txt .
RUN pip3 install --break-system-packages --no-cache-dir -r requirements.txt

# Install Cloud SQL Auth Proxy for direct MySQL connectivity (bypasses PSA VPC routing)
RUN curl -sSL https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.14.2/cloud-sql-proxy.linux.amd64 \
    -o /usr/local/bin/cloud-sql-proxy && \
    chmod +x /usr/local/bin/cloud-sql-proxy

COPY main.py .

ENTRYPOINT ["python3", "main.py"]
