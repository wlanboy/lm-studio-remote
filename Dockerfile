# Build stage
FROM python:3.14-slim AS builder

# Verhindert, dass Python .pyc Dateien schreibt und sorgt für sofortige Log-Ausgabe
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies in a virtual environment
COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.14-slim

# Umgebungsvariablen übernehmen
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Create non-root user and a writable dir for the server cache (mount as volume)
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser && \
    mkdir -p /app/data && chown appuser:appuser /app/data

# Copy application files
COPY --chown=appuser:appuser main.py /app/
COPY --chown=appuser:appuser lm_remote/ /app/lm_remote/

VOLUME ["/app/data"]

# Use non-root user
USER appuser

# Textual TUI: needs an interactive terminal, run with `docker run -it`
CMD ["python", "main.py"]
