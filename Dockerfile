# Single-service production image: React frontend + FastAPI backend.
FROM node:22-bookworm-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata \
    WHISPER_MODEL=small \
    WHISPER_DEVICE=cpu \
    WHISPER_COMPUTE=int8

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-ara tesseract-ocr-fas ffmpeg curl ca-certificates \
    libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Kurdish Sorani Tesseract language data. The image remains self-contained after build.
RUN curl -fsSL -o /usr/share/tesseract-ocr/5/tessdata/ckb.traineddata \
    https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/main/ckb.traineddata

WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ ./backend/
COPY --from=frontend /app/frontend/dist ./frontend/dist/
RUN mkdir -p uploads

EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
