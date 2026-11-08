FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH
WORKDIR $HOME/app

# Install depedencies pyproject.toml
COPY --chown=user:user pyproject.toml README.md ./
RUN pip install --no-cache-dir --user .

COPY --chown=user:user src/ ./src/

EXPOSE 7860

# Healthcheck container
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# Run 
CMD ["uvicorn", "kuking.main:app", "--host", "0.0.0.0", "--port", "7860"]