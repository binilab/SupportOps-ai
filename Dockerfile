FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    HF_HOME=/home/supportops/.cache/huggingface

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
RUN python -m pip install --no-cache-dir 'torch==2.14.1+cpu' --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install --no-cache-dir .

COPY data/raw/policies ./data/raw/policies
COPY data/raw/structured ./data/raw/structured
COPY scripts/init_database.py ./scripts/init_database.py

RUN useradd --create-home --uid 10001 supportops \
    && mkdir -p "$HF_HOME" \
    && chown -R supportops:supportops /home/supportops
USER supportops

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "supportops.api:app", "--host", "0.0.0.0", "--port", "8000"]
