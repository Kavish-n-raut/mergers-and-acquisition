FROM python:3.12-slim

WORKDIR /app

# Slim runtime (no torch/transformers/faiss) so the image fits free-tier build limits.
# FinBERT + semantic retrieval degrade to keyword mode; Groq LLM still works over HTTP.
COPY requirements-slim.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app
COPY runtime_artifacts /app/runtime_artifacts

EXPOSE 8000

# Bind the platform-provided $PORT (Render/Fly inject it); default 8000 for local Docker.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
