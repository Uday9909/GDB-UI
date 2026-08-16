FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gdb \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
CMD ["sleep", "infinity"]
