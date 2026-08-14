# Container image for deploying to Google Cloud Run (see GOOGLE_CLOUD_RUN_DEPLOYMENT.md).
# Also works on Hugging Face Spaces' Docker SDK if you're on a paid plan (see
# HUGGINGFACE_DEPLOYMENT.md) since it follows the Spaces port-7860 convention.
FROM python:3.11-slim

WORKDIR /app

# build-essential is needed to compile a couple of crewai's transitive
# dependencies that don't ship prebuilt wheels for every platform.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app.py start_web.py ./
COPY src ./src
COPY static ./static
COPY knowledge ./knowledge

RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -e .

# Spaces run containers as a non-root user by convention.
RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/output \
    && chown -R appuser:appuser /app
USER appuser
ENV HOME=/home/appuser

EXPOSE 7860

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
