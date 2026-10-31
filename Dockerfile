# Builds the web app, then runs it from the API server, so the desk and the API share
# one origin. The desk cookie is SameSite=Lax and depends on that.

FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
ENV VITE_API_MODE=live
RUN npm run build

FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md requirements.lock ./
COPY src ./src
RUN pip install --no-cache-dir --constraint requirements.lock ".[postgres]"
COPY knowledge ./knowledge
COPY --from=web /web/dist ./web/dist

RUN useradd --create-home --uid 10001 jalboot && mkdir /data && chown jalboot /data
USER jalboot

# Paths are set here because an installed package has no repo around it.
ENV KNOWLEDGE_DIR=/app/knowledge \
    WEB_DIST=/app/web/dist \
    INDEX_DIR=/data/index \
    DATABASE_URL=sqlite:////data/jalboot.sqlite3
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2)"
CMD ["jalboot", "serve", "--host", "0.0.0.0", "--port", "8000"]
