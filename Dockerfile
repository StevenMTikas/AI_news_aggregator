# Optional container image for running ContentForge on a personal server / VPS.
# Mount a volume at /app/data so the SQLite database and generated output survive restarts.
# The primary supported way to run ContentForge is still locally (see DEPLOYMENT.md).
FROM python:3.11-slim

WORKDIR /app

# build-essential compiles a few transitive dependencies that don't ship prebuilt wheels
# for every platform.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app.py start_web.py ./
COPY src ./src
COPY static ./static

RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -e .

RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/data /app/output \
    && chown -R appuser:appuser /app
USER appuser
ENV HOME=/home/appuser

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
