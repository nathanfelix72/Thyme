# Production Thyme API (BYOK + DynamoDB). No Ollama on the box.
FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential curl \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# CPU-only torch: default wheels pull multi-GB CUDA stacks that OOMs/stalls t3.small.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch \
  && pip install --no-cache-dir -r requirements.txt \
       --extra-index-url https://download.pytorch.org/whl/cpu

COPY app ./app

ENV PYTHONUNBUFFERED=1 \
  CHROMA_DIR=/data/chroma \
  THYME_ENV=aws

RUN mkdir -p /data/chroma

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8765/api/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765"]
