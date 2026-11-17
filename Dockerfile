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

# Install depedencies pyproject.toml and source code
COPY --chown=user:user pyproject.toml README.md ./
COPY --chown=user:user src/ ./src/

RUN pip install --no-cache-dir --user .

# Run 
CMD ["sh", "-c", "uvicorn kuking.main:app --host 0.0.0.0 --port ${PORT:-7860}"]