# KisanSaarthi AI - application image (FastAPI + chat UI + WhatsApp webhook).
# Build:  docker build -t kisansaarthi-ai .
# With the crop disease model runtime (PyTorch CPU wheels, large image):
#         docker build --build-arg WITH_VISION=true -t kisansaarthi-ai .
FROM python:3.11-slim

ARG WITH_VISION=false
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends libexpat1 libgomp1 \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-vision.txt ./
RUN pip install -r requirements.txt \
 && if [ "$WITH_VISION" = "true" ]; then \
      pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision; \
    fi

COPY . .

RUN useradd --create-home app \
 && mkdir -p /app/db /app/logs /app/data/uploads \
 && chown -R app:app /app
USER app

ENV DATABASE_URL=sqlite:////app/db/kisansaarthi.db
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
