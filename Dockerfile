FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY harness ./harness
COPY harness.ini ./harness.ini

CMD ["python", "-m", "harness.runner"]
