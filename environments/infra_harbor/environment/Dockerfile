FROM python:3.11-slim

# Install nginx for config validation (nginx -t)
RUN apt-get update && \
    apt-get install -y --no-install-recommends nginx curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python tools for testing
RUN pip install --no-cache-dir pyyaml pytest yamllint

# Copy the infrastructure project
COPY infra/ /infra/

WORKDIR /infra
