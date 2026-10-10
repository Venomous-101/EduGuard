#!/bin/bash
# EduGuard UAE - run the demo API
# Usage: ./run.sh
cd "$(dirname "$0")"
export no_proxy="localhost,127.0.0.1" NO_PROXY="localhost,127.0.0.1"
if [ ! -d ".venv" ]; then
  echo "Creating venv and installing dependencies..."
  python3 -m venv .venv
  .venv/bin/pip install --no-cache-dir -r requirements.txt
fi
if [ ! -d "kb/chroma_db" ]; then
  echo "Ingesting knowledge base..."
  .venv/bin/python -m kb.ingest
fi
echo "Starting EduGuard UAE on http://localhost:8000"
.venv/bin/uvicorn api.main:app --port 8000
