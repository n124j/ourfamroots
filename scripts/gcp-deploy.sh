#!/usr/bin/env bash
# ============================================================
#  OurFamRoots — GCP Free-Tier VM Deployment
#
#  This script is run ON THE GCP VM after you SSH in.
#  It installs Docker, clones the repo, and brings up the stack.
#
#  Prerequisites:
#    1. A GCP e2-micro VM (free tier) running Debian 12 / Ubuntu 22.04+
#    2. A domain with an A record pointing to the VM's external IP
#    3. Firewall rules allowing TCP 80 and 443
#
#  Usage:
#    # SSH into your GCP VM, then:
#    curl -sL https://raw.githubusercontent.com/YOUR_ORG/ourfamroots/main/scripts/gcp-deploy.sh | bash
#
#    # Or clone manually and run:
#    git clone https://github.com/YOUR_ORG/ourfamroots.git
#    cd ourfamroots
#    bash scripts/gcp-deploy.sh
# ============================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Step 1: Install Docker ──────────────────────────────────────────────────
install_docker() {
  if command -v docker &>/dev/null; then
    info "Docker already installed: $(docker --version)"
    return
  fi

  info "Installing Docker..."
  sudo apt-get update -qq
  sudo apt-get install -y -qq ca-certificates curl gnupg lsb-release

  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg

  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

  sudo apt-get update -qq
  sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

  sudo usermod -aG docker "$USER"
  info "Docker installed.  You may need to log out and back in for group changes."
}

# ── Step 2: Configure swap (e2-micro has only 1 GB RAM) ─────────────────────
configure_swap() {
  if swapon --show | grep -q '/swapfile'; then
    info "Swap already configured."
    return
  fi

  info "Creating 2 GB swap file (essential for 1 GB RAM VM)..."
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile

  # Persist across reboots
  if ! grep -q '/swapfile' /etc/fstab; then
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
  fi

  # Tune swappiness — prefer RAM but use swap when needed
  sudo sysctl vm.swappiness=10
  echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-swappiness.conf

  info "Swap configured: $(swapon --show)"
}

# ── Step 3: Check .env.prod exists ──────────────────────────────────────────
check_env() {
  if [ ! -f .env.prod ]; then
    error ".env.prod not found!"
    echo ""
    echo "  Copy the example and fill in your values:"
    echo "    cp .env.prod.example .env.prod"
    echo "    nano .env.prod"
    echo ""
    exit 1
  fi

  # Validate required vars
  local required_vars=(DOMAIN POSTGRES_PASSWORD REDIS_PASSWORD MINIO_ROOT_PASSWORD JWT_SECRET_KEY SMTP_USER SMTP_PASSWORD EMAIL_FROM CERTBOT_EMAIL)
  local missing=()
  for var in "${required_vars[@]}"; do
    val=$(grep "^${var}=" .env.prod | cut -d= -f2-)
    if [ -z "$val" ] || [[ "$val" == CHANGE_ME* ]]; then
      missing+=("$var")
    fi
  done

  if [ ${#missing[@]} -gt 0 ]; then
    error "The following variables in .env.prod are missing or still have placeholder values:"
    for v in "${missing[@]}"; do
      echo "  - $v"
    done
    exit 1
  fi

  info ".env.prod validated."
}

# ── Step 4: Generate self-signed placeholder certs ──────────────────────────
init_certs() {
  local cert_dir="./certbot/conf/live/cert"
  if [ -f "$cert_dir/fullchain.pem" ]; then
    info "TLS certificates already exist."
    return
  fi

  info "Generating self-signed placeholder certificate..."
  mkdir -p "$cert_dir"
  openssl req -x509 -nodes -days 1 \
    -newkey rsa:2048 \
    -keyout "$cert_dir/privkey.pem" \
    -out "$cert_dir/fullchain.pem" \
    -subj "/CN=localhost" 2>/dev/null

  info "Placeholder cert created. Will be replaced by Let's Encrypt."
}

# ── Step 5: Build and start the stack ───────────────────────────────────────
start_stack() {
  info "Building and starting services..."
  docker compose -f docker-compose.prod.yml --env-file .env.prod build
  docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

  info "Waiting for services to become healthy..."
  sleep 15

  docker compose -f docker-compose.prod.yml --env-file .env.prod ps
}

# ── Step 6: Obtain Let's Encrypt certificate ────────────────────────────────
obtain_cert() {
  local domain
  domain=$(grep "^DOMAIN=" .env.prod | cut -d= -f2-)

  info "Obtaining Let's Encrypt certificate for $domain..."
  docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm certbot

  # Copy certs to the expected path
  local le_dir="./certbot/conf/live/$domain"
  local cert_dir="./certbot/conf/live/cert"
  if [ -d "$le_dir" ] && [ "$le_dir" != "$cert_dir" ]; then
    rm -rf "$cert_dir"
    ln -sf "$domain" "$cert_dir"
  fi

  info "Reloading Nginx with real certificate..."
  docker compose -f docker-compose.prod.yml --env-file .env.prod exec proxy nginx -s reload

  info "TLS certificate installed for $domain"
}

# ── Step 7: Setup auto-renewal cron ─────────────────────────────────────────
setup_renewal() {
  info "Certificate auto-renewal is handled by the renew-certs service."
  info "It runs certbot renew every 12 hours automatically."
}

# ── Step 8: Setup daily DB backup ────────────────────────────────────────────
setup_backup() {
  local backup_script="/opt/ourfamroots/backup.sh"
  sudo mkdir -p /opt/ourfamroots/backups

  sudo tee "$backup_script" > /dev/null << 'BACKUP_EOF'
#!/bin/bash
# Daily PostgreSQL backup — keeps 7 days of backups
BACKUP_DIR="/opt/ourfamroots/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
COMPOSE_FILE="$(dirname "$(readlink -f "$0")")/../ourfamroots/docker-compose.prod.yml"

cd /home/*/ourfamroots 2>/dev/null || cd /root/ourfamroots 2>/dev/null || exit 1

docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T db \
  pg_dump -U postgres ourfamroots | gzip > "$BACKUP_DIR/ourfamroots_${TIMESTAMP}.sql.gz"

# Remove backups older than 7 days
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +7 -delete

echo "[$(date)] Backup completed: ourfamroots_${TIMESTAMP}.sql.gz"
BACKUP_EOF

  sudo chmod +x "$backup_script"

  # Add daily cron job if not already present
  if ! sudo crontab -l 2>/dev/null | grep -q "ourfamroots.*backup"; then
    (sudo crontab -l 2>/dev/null; echo "0 3 * * * $backup_script >> /var/log/ourfamroots-backup.log 2>&1") | sudo crontab -
    info "Daily backup cron job added (runs at 3 AM)."
  else
    info "Backup cron job already exists."
  fi
}

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
  echo ""
  echo "  ======================================"
  echo "   OurFamRoots — GCP Production Deploy"
  echo "  ======================================"
  echo ""

  install_docker
  configure_swap
  check_env
  init_certs
  start_stack
  obtain_cert
  setup_renewal
  setup_backup

  local domain
  domain=$(grep "^DOMAIN=" .env.prod | cut -d= -f2-)

  echo ""
  info "========================================="
  info "  Deployment complete!"
  info ""
  info "  App:    https://$domain"
  info "  API:    https://$domain/api/v1"
  info "  Health: https://$domain/health"
  info ""
  info "  Useful commands:"
  info "    Logs:     docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f"
  info "    Status:   docker compose -f docker-compose.prod.yml --env-file .env.prod ps"
  info "    Restart:  docker compose -f docker-compose.prod.yml --env-file .env.prod restart"
  info "    Update:   git pull && docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build"
  info "========================================="
}

main "$@"
