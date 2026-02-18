# Create GitHub Actions CI/CD Pipeline

## Overview

The `/infra/` directory contains a containerized infrastructure project with the following key files:

- **Dockerfile.web** — Dockerfile for building the web application image
- **Dockerfile.worker** — Dockerfile for building the background worker image
- **docker-compose.yml** — Compose file that orchestrates the multi-container setup
- **app/** — Application source code directory (includes `requirements.txt` for Python dependencies)

The `.github/workflows/` directory already exists at `/infra/.github/workflows/` but is currently empty. Your task is to create a complete CI/CD pipeline configuration.

## Task

Create the file `/infra/.github/workflows/ci.yml` that defines a GitHub Actions CI/CD pipeline with the following specifications.

### Triggers

The pipeline must trigger on:
- **push** to the `main` branch
- **pull_request** targeting the `main` branch

### Jobs

The pipeline must contain exactly **3 jobs** that run in sequence:

---

#### Job 1: `lint`

- **Runs on:** `ubuntu-latest`
- **Steps:**
  1. **Checkout** the repository using `actions/checkout@v4`
  2. **Lint Dockerfile.web** using `hadolint/hadolint-action@v3.0.0` with the `dockerfile` input set to `Dockerfile.web`
  3. **Lint Dockerfile.worker** using `hadolint/hadolint-action@v3.0.0` with the `dockerfile` input set to `Dockerfile.worker`
  4. **Lint docker-compose.yml** by installing `yamllint` via pip and then running `yamllint docker-compose.yml`

---

#### Job 2: `test`

- **Runs on:** `ubuntu-latest`
- **Depends on:** `lint`
- **Steps:**
  1. **Checkout** the repository using `actions/checkout@v4`
  2. **Set up Python 3.11** using `actions/setup-python@v5` with `python-version` set to `"3.11"`
  3. **Install dependencies** by running `pip install -r app/requirements.txt`
  4. **Run tests** using `pytest --version` as a placeholder (the test infrastructure should be in place even if no tests exist yet)

---

#### Job 3: `build-and-push`

- **Runs on:** `ubuntu-latest`
- **Depends on:** `test`
- **Conditional:** Only runs on pushes to `main` — use the condition:
  ```
  if: github.ref == 'refs/heads/main' && github.event_name == 'push'
  ```
- **Steps:**
  1. **Checkout** the repository using `actions/checkout@v4`
  2. **Login to GitHub Container Registry** using `docker/login-action@v3` with:
     - `registry`: `ghcr.io`
     - `username`: `${{ github.actor }}`
     - `password`: `${{ secrets.GITHUB_TOKEN }}`
  3. **Set up Docker Buildx** using `docker/setup-buildx-action@v3`
  4. **Build and push web image** using `docker/build-push-action@v5` with:
     - `context`: `.`
     - `file`: `Dockerfile.web`
     - `push`: `true`
     - `tags`: `ghcr.io/${{ github.repository }}/web:latest` and `ghcr.io/${{ github.repository }}/web:${{ github.sha }}`
     - `cache-from`: `type=gha`
     - `cache-to`: `type=gha,mode=max`
  5. **Build and push worker image** using `docker/build-push-action@v5` with:
     - `context`: `.`
     - `file`: `Dockerfile.worker`
     - `push`: `true`
     - `tags`: `ghcr.io/${{ github.repository }}/worker:latest` and `ghcr.io/${{ github.repository }}/worker:${{ github.sha }}`
     - `cache-from`: `type=gha`
     - `cache-to`: `type=gha,mode=max`

## Constraints

- Use the **exact action versions** specified above (e.g., `actions/checkout@v4`, `hadolint/hadolint-action@v3.0.0`, `docker/build-push-action@v5`, etc.)
- Use proper YAML indentation (2 spaces)
- Ensure the conditional on the `build-and-push` job is syntactically correct
- The job dependency chain must be: `lint` → `test` → `build-and-push`
