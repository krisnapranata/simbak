# syntax=docker/dockerfile:1
# Image SIMBAK untuk produksi: Django + Gunicorn. Dijalankan lewat docker-compose.yml.

# --- tahap 1: kompilasi wheel (mysqlclient butuh compiler & header MySQL) ---
FROM python:3.12-slim-bookworm AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential pkg-config default-libmysqlclient-dev \
 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip wheel --wheel-dir /wheels -r requirements.txt

# --- tahap 2: image runtime (tanpa compiler) ---
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    TZ=Asia/Makassar
# libmariadb3: mysqlclient · libmagic1: cek MIME upload · pango/harfbuzz/fonts: PDF WeasyPrint
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libmariadb3 libmagic1 libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
      fonts-dejavu-core tzdata \
 && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 1000 simbak
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install /wheels/* && rm -rf /wheels
COPY --chown=simbak:simbak . .
RUN mkdir -p /app/staticfiles /app/media_private \
 && chown simbak:simbak /app/staticfiles /app/media_private
USER simbak
EXPOSE 8000
ENTRYPOINT ["sh", "/app/deploy/entrypoint.sh"]
CMD ["web"]
