FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Ingest KB at build time (embeddings are CPU-only via ONNX)
RUN python -m kb.ingest

# Expose port (HF Spaces uses 7860)
EXPOSE 7860

# Run the API
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860"]
