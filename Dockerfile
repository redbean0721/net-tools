FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y iputils-ping traceroute curl && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir websockets

WORKDIR /app

RUN curl -fsSL https://raw.githubusercontent.com/redbean0721/net-tools/refs/heads/main/worker.py -o /app/worker.py

CMD ["python", "/app/worker.py"]
