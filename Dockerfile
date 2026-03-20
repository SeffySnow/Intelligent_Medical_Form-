# Stage 1: builder
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build deps
RUN pip install --upgrade pip setuptools wheel

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir ".[dev]" --target /deps

# Stage 2: runtime
FROM python:3.11-slim AS runtime

# Non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy installed packages
COPY --from=builder /deps /usr/local/lib/python3.11/site-packages

# Copy source
COPY src/ src/
COPY pyproject.toml .

# Install package in editable mode (source only, deps already installed)
RUN pip install --no-cache-dir --no-deps -e .

# Create directory structure:
#   /data/inputs  — mount patient documents here (read-only recommended)
#   /data/outputs — generated files land here
#   /models       — LLM model cache
RUN mkdir -p /data/inputs /data/outputs /models \
    && chown -R appuser:appuser /data /models /app

USER appuser

# ── Input paths ───────────────────────────────────────────────────────────────
ENV FORM_PDF=/data/inputs/form_fillable.pdf
ENV DEMOGRAPHICS_JSON=/data/inputs/demographics.json
ENV SOAP_NOTES_TXT=/data/inputs/soap_notes.txt
ENV LAB_RESULT_PDF=/data/inputs/lab_result.pdf

# ── Output paths ──────────────────────────────────────────────────────────────
ENV SCHEMA_JSON=/data/outputs/schema.json
ENV ANSWERS_JSON=/data/outputs/answers.json
ENV OUTPUT_PDF=/data/outputs/populated.pdf

# ── Runtime settings ──────────────────────────────────────────────────────────
ENV MODEL_CACHE_DIR=/models/Qwen2.5-3B-Instruct
ENV LOG_FORMAT=json

VOLUME ["/data", "/models"]

ENTRYPOINT ["form-filler"]
CMD ["--help"]
