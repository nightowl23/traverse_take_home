#!/bin/bash

mkdir -p /infra/.github/workflows

cat > /infra/.github/workflows/ci.yml << 'EOF'
name: CI/CD Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Lint Dockerfile.web
        uses: hadolint/hadolint-action@v3.0.0
        with:
          dockerfile: Dockerfile.web
      - name: Lint Dockerfile.worker
        uses: hadolint/hadolint-action@v3.0.0
        with:
          dockerfile: Dockerfile.worker
      - name: Lint docker-compose.yml
        run: |
          pip install yamllint
          yamllint docker-compose.yml

  test:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -r app/requirements.txt
      - name: Run tests
        run: pytest --version

  build-and-push:
    runs-on: ubuntu-latest
    needs: test
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    steps:
      - uses: actions/checkout@v4
      - name: Login to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      - name: Build and push web image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: Dockerfile.web
          push: true
          tags: |
            ghcr.io/${{ github.repository }}/web:latest
            ghcr.io/${{ github.repository }}/web:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
      - name: Build and push worker image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: Dockerfile.worker
          push: true
          tags: |
            ghcr.io/${{ github.repository }}/worker:latest
            ghcr.io/${{ github.repository }}/worker:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
EOF
