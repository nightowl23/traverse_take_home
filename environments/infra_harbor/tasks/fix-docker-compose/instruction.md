# Fix Docker Compose Configuration

## Overview

The infra project located at `/infra/` contains a Docker Compose setup for a multi-service web application. The `docker-compose.yml` file defines the infrastructure stack, which includes a web application, a background worker, an Nginx reverse proxy, and a PostgreSQL database.

Docker Compose is a tool for defining and running multi-container Docker applications. The `docker-compose.yml` file declaratively describes the services, networks, volumes, and their relationships. When properly configured, a single `docker-compose up` command brings the entire stack online with correct networking, dependency ordering, and persistent storage.

## Project Structure

```
/infra/
└── docker-compose.yml    # Main Docker Compose configuration file
```

The compose file currently defines the following services:
- **web** — The main Flask web application (port 5000 internally)
- **worker** — A background task worker
- **nginx** — Reverse proxy that routes traffic to the web service
- **postgres** — PostgreSQL database

## Issues to Fix

The `docker-compose.yml` file contains **7 issues** that need to be resolved:

### 1. Web Service Port Mapping (Incorrect Host Port)

The web service currently maps port `8081:5000`, but the correct host port should be `8080`. Change the port mapping to `8080:5000` so that the web application is accessible on the expected port.

### 2. PostgreSQL Image Version (Outdated)

The PostgreSQL service uses the `postgres:13` image, which is outdated. Upgrade the image to `postgres:16` to use the latest stable major version with improved performance and security features.

### 3. PostgreSQL Healthcheck (Missing)

The PostgreSQL service has no healthcheck defined. Add a healthcheck using the `pg_isready` command so that dependent services can wait until the database is truly ready to accept connections. Use the following parameters:

- **Command:** `pg_isready`
- **Interval:** 10 seconds
- **Timeout:** 5 seconds
- **Retries:** 5

### 4. Web Service depends_on (Missing Healthcheck Condition)

The web service currently uses a simple list form for `depends_on` (just listing `postgres`). Change it to the long-form (condition form) so that the web service waits until postgres is healthy before starting:

```yaml
depends_on:
  postgres:
    condition: service_healthy
```

### 5. Add Redis Service (Missing Entirely)

There is no Redis service in the compose file. Add a Redis service with the following configuration:

- **Service name:** `redis`
- **Image:** `redis:7-alpine`
- **Ports:** `6379:6379`
- **Healthcheck:** Use `redis-cli ping` command to verify the service is ready

### 6. Add REDIS_URL Environment Variable and Redis Dependency

Both the `web` and `worker` services need to connect to Redis. Add the following environment variable to both services:

```
REDIS_URL=redis://redis:6379/0
```

Also add `redis` to the `depends_on` section of both the `web` and `worker` services (using the condition form with `service_healthy`).

### 7. Add Named Volume for PostgreSQL Data Persistence

Currently, PostgreSQL data is not persisted across container restarts. Fix this by:

1. Declaring a top-level named volume called `postgres_data`
2. Mounting it to `/var/lib/postgresql/data` on the postgres service

This ensures that database data survives container recreation.

## Constraints

- **Do not delete any existing services.** All current services (web, worker, nginx, postgres) must remain in the file.
- **Preserve the nginx service as-is.** Do not modify the nginx service configuration.
- **Keep the `version` field.** The compose file's `version` field must remain in the output.
