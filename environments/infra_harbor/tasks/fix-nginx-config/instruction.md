# Fix and Extend Nginx Reverse Proxy Configuration

## Background

You are working on an infrastructure project located at `/infra/`. The project uses Nginx as a reverse proxy to route traffic to a backend web application. The Nginx configuration lives under `/infra/nginx/` and consists of two files:

- **`/infra/nginx/nginx.conf`** — The main Nginx configuration file. It contains the `worker_processes` directive, an `events` block, and an `http` block with an `upstream` definition and an `include` for additional site configs.
- **`/infra/nginx/conf.d/default.conf`** — The default site configuration. It contains a `server` block with a single `location /` that proxies requests to the upstream backend.

## Current Problems

The configuration has several issues and is missing important features. You need to fix and extend both files to address **all seven** of the following items:

### 1. Fix Upstream Port (nginx.conf)

The `upstream webapp` block in `nginx.conf` currently points to `server web:8000`. The backend application actually listens on port **5000**. Change the upstream server directive to:

```
server web:5000;
```

### 2. Add Proxy Headers (conf.d/default.conf)

The `location /` block in `default.conf` currently only has a `proxy_pass` directive. It is missing essential proxy headers. Add the following four `proxy_set_header` directives inside `location /`:

```
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

### 3. Add Rate Limiting (nginx.conf + conf.d/default.conf)

Add a rate limiting zone in the `http` block of `nginx.conf` using the `limit_req_zone` directive:

```
limit_req_zone $binary_remote_addr zone=one:10m rate=10r/s;
```

Then, in `default.conf`, add a `limit_req` directive inside the `location /` block:

```
limit_req zone=one burst=20 nodelay;
```

### 4. Add /api/ Location (conf.d/default.conf)

Add a new `location /api/` block inside the `server` block in `default.conf`. It should proxy requests to the `webapp` upstream and include the same four `proxy_set_header` directives as `location /`:

```
location /api/ {
    proxy_pass http://webapp;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

### 5. Add /static/ Location (conf.d/default.conf)

Add a new `location /static/` block inside the `server` block in `default.conf`. It should serve static files with a 30-day expiry and a public Cache-Control header:

```
location /static/ {
    expires 30d;
    add_header Cache-Control "public";
}
```

### 6. Add Gzip Compression (nginx.conf)

Add gzip compression directives inside the `http` block of `nginx.conf`:

```
gzip on;
gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
gzip_min_length 1000;
```

### 7. Add /health Location (conf.d/default.conf)

Add a new `location /health` block inside the `server` block in `default.conf`. It should return a 200 status directly from Nginx with the body `"ok"`:

```
location /health {
    return 200 "ok";
}
```

## Constraints

- You **must** keep `worker_processes auto;` in `nginx.conf`.
- You **must** keep the `events` block in `nginx.conf`.
- You **must** keep the `include /etc/nginx/conf.d/*.conf;` directive (or equivalent) in the `http` block so that `default.conf` is loaded.
- You **must** keep the `upstream webapp` block in `nginx.conf`.
- The resulting configuration must pass `nginx -t` syntax validation.
