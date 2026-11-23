# Hugging Face Space wrapper: builds straight from the GitHub repo,
# so GitHub stays the only copy of the code.

FROM alpine/git AS src
# re-downloads on every build; the layer only changes when main gets a new commit,
# which is what forces a fresh clone instead of a cached one
ADD https://api.github.com/repos/Aayush-Jhawar/matchpoint/git/refs/heads/main /tmp/version.json
RUN git clone --depth 1 https://github.com/Aayush-Jhawar/matchpoint.git /src

FROM node:20-slim AS ui
WORKDIR /ui
COPY --from=src /src/frontend/ ./
RUN npm install && npm run build

FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=src /src/backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY --from=src /src/backend/ backend/
COPY --from=src /src/samples/ samples/
COPY --from=ui /ui/dist frontend/dist
# Spaces run as a non-root user; /tmp is writable
ENV MATCHPOINT_DATA=/tmp/matchpoint STAGE_DELAY_MS=450
WORKDIR /app/backend
EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
