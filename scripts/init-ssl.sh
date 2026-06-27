#!/usr/bin/env bash
# Generate self-signed placeholder certificates so Nginx can start
# before Certbot has run.  Safe to re-run — skips if certs already exist.
set -euo pipefail

CERT_DIR="./certbot/conf/live/cert"

if [ -f "$CERT_DIR/fullchain.pem" ]; then
  echo "Certificates already exist in $CERT_DIR — skipping."
  exit 0
fi

echo "Creating self-signed placeholder certificate..."
mkdir -p "$CERT_DIR"

openssl req -x509 -nodes -days 1 \
  -newkey rsa:2048 \
  -keyout "$CERT_DIR/privkey.pem" \
  -out "$CERT_DIR/fullchain.pem" \
  -subj "/CN=localhost"

echo "Placeholder certificate created.  Run certbot to get a real one."
