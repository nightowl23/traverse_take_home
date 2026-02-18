#!/bin/bash
set -e

echo "Waiting for database..."
while ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" 2>/dev/null; do
    sleep 1
done
echo "Database is ready."

exec "$@"
