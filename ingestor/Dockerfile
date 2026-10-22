# RAG ingestor (FastAPI). Build from the ingestor folder:
#   docker build -t rag-ingestor .
# Config comes from environment variables at runtime (see .env.example); never baked into the image.
# On AWS, leave AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY unset and give the task an IAM role instead.

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

# Dependencies first (read from pyproject.toml), so code changes don't reinstall them
COPY pyproject.toml ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']))" > requirements.txt \
 && pip install -r requirements.txt \
 && rm requirements.txt

COPY app ./app

# Run as a non-root user
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8002
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8002/health', timeout=4)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002", "--proxy-headers", "--forwarded-allow-ips", "*"]
