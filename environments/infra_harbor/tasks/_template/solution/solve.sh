#!/bin/bash
# TODO: Write the reference solution.
# This script runs inside the container at /infra/ against the infrastructure project.
# It should produce the correct solution that passes all tests.
#
# Common patterns:
#   - Overwrite a file:       cat > /infra/file.yml << 'EOF' ... EOF
#   - Patch with Python:      python3 -c "..." (read YAML, modify, write)
#   - Validate nginx:         nginx -t -c /infra/nginx/nginx.conf
