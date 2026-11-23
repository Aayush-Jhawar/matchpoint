# Build the UI, then run everything from one Python container.
# Works on Hugging Face Spaces (port 7860) and Railway/Render (they set $PORT).
FROM node:20-slim AS ui
WORKDIR /ui
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY samples/ samples/
COPY tools/ tools/
COPY --from=ui /ui/dist frontend/dist
ENV MATCHPOINT_DATA=/tmp/matchpoint STAGE_DELAY_MS=450
WORKDIR /app/backend
EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
