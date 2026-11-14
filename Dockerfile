# ClaraMed backend image (API, Celery worker and beat all run from this image).

FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/home/app

# tesseract + poppler: OCR and PDF rendering. libgl1/libglib2.0: image libraries. curl: dev-compose healthchecks.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        poppler-utils \
        libgl1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Unprivileged user: nothing in the container needs root.
RUN useradd --create-home --uid 10001 app
WORKDIR /app

# CPU-only PyTorch first (the default PyPI wheel pulls multi-GB CUDA libraries this deployment cannot use),
# then everything else; requirements.txt's torch>=2.0.0 is already satisfied.
COPY requirements.txt .
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app . .
RUN mkdir -p /app/storage && chown app:app /app/storage

USER app

# Bake the X-ray model weights into the image so the first job needs no download and the worker needs no
# outbound access to GitHub at runtime.
RUN python -c "import torchxrayvision as xrv; xrv.models.DenseNet(weights='densenet121-res224-all')"

EXPOSE 8000

# Exits non-zero on any non-2xx response or connection failure.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health', timeout=5)"

# Migrations are NOT run here: with several containers from this image they would race. The compose
# files run `alembic upgrade head` once, in a separate step, before the API and worker start.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
