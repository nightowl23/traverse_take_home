#!/bin/bash
set -euo pipefail

# Overwrite nginx.conf with the corrected configuration
cat > /infra/nginx/nginx.conf << 'EOF'
worker_processes auto;

events {
    worker_connections 1024;
}

http {
    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
    gzip_min_length 1000;

    # Rate limiting zone
    limit_req_zone $binary_remote_addr zone=one:10m rate=10r/s;

    # Upstream backend
    upstream webapp {
        server web:5000;
    }

    include /etc/nginx/conf.d/*.conf;
}
EOF

# Ensure conf.d directory exists
mkdir -p /infra/nginx/conf.d

# Overwrite default.conf with the corrected site configuration
cat > /infra/nginx/conf.d/default.conf << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://webapp;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        limit_req zone=one burst=20 nodelay;
    }

    location /api/ {
        proxy_pass http://webapp;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        expires 30d;
        add_header Cache-Control "public";
    }

    location /health {
        return 200 "ok";
    }
}
EOF

echo "Nginx configuration files updated successfully."
