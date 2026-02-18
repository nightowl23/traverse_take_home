#!/bin/bash
set -euo pipefail

COMPOSE_FILE="/infra/docker-compose.yml"

python3 << 'PYTHON_SCRIPT'
import yaml

compose_file = "/infra/docker-compose.yml"

with open(compose_file, "r") as f:
    compose = yaml.safe_load(f)

services = compose.get("services", {})

# 1. Fix web service port mapping: 8081:5000 -> 8080:5000
web = services.get("web", {})
if "ports" in web:
    web["ports"] = [p.replace("8081:5000", "8080:5000") if isinstance(p, str) else p for p in web["ports"]]

# 2. Upgrade PostgreSQL image from postgres:13 to postgres:16
postgres = services.get("postgres", {})
postgres["image"] = "postgres:16"

# 3. Add healthcheck to PostgreSQL service
postgres["healthcheck"] = {
    "test": ["CMD-SHELL", "pg_isready"],
    "interval": "10s",
    "timeout": "5s",
    "retries": 5,
}

# 4. Change web depends_on to condition form with service_healthy for postgres
web["depends_on"] = {
    "postgres": {"condition": "service_healthy"},
}

# 5. Add Redis service
services["redis"] = {
    "image": "redis:7-alpine",
    "ports": ["6379:6379"],
    "healthcheck": {
        "test": ["CMD", "redis-cli", "ping"],
        "interval": "10s",
        "timeout": "5s",
        "retries": 5,
    },
}

# 6. Add REDIS_URL environment variable to web and worker, and add redis to depends_on
redis_url = "redis://redis:6379/0"

for svc_name in ["web", "worker"]:
    svc = services.get(svc_name, {})
    # Add REDIS_URL to environment
    env = svc.get("environment", {})
    if isinstance(env, list):
        env.append(f"REDIS_URL={redis_url}")
    elif isinstance(env, dict):
        env["REDIS_URL"] = redis_url
    else:
        env = {"REDIS_URL": redis_url}
    svc["environment"] = env

    # Add redis to depends_on with condition form
    deps = svc.get("depends_on", {})
    if isinstance(deps, list):
        # Convert list form to dict form
        deps = {dep: {"condition": "service_healthy"} for dep in deps}
    deps["redis"] = {"condition": "service_healthy"}
    svc["depends_on"] = deps
    services[svc_name] = svc

# 7. Add named volume for postgres data persistence
# Add top-level volumes
if "volumes" not in compose:
    compose["volumes"] = {}
compose["volumes"]["postgres_data"] = None

# Mount volume on postgres service
pg_volumes = postgres.get("volumes", [])
pg_volumes.append("postgres_data:/var/lib/postgresql/data")
postgres["volumes"] = pg_volumes

compose["services"] = services

with open(compose_file, "w") as f:
    yaml.dump(compose, f, default_flow_style=False, sort_keys=False)

print("Docker Compose file fixed successfully.")
PYTHON_SCRIPT
