#!/usr/bin/env bash
# ============================================================================
# Factory Operations Platform — one-shot deployment for Ubuntu 22.04 LTS
#
#   sudo bash deploy.sh
#
# Installs and configures everything on a fresh server:
#   Python 3.11 (deadsnakes) + venv        -> FastAPI backend (systemd, :8001)
#   Node.js 20 + Yarn (corepack)           -> React production build
#   MongoDB 7.0                            -> database (localhost only)
#   nginx                                  -> serves the UI and proxies /api
#
# Idempotent: safe to re-run to update the app after pulling new code.
# ============================================================================
set -euo pipefail

APP_NAME="factory-ops"
APP_DIR="/opt/${APP_NAME}"
DB_NAME="factory_ops"
BACKEND_PORT=8001
HTTP_PORT=80
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log()  { echo -e "\e[1;36m[deploy]\e[0m $*"; }
fail() { echo -e "\e[1;31m[deploy] ERROR:\e[0m $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || fail "run as root:  sudo bash deploy.sh"
grep -q "22.04" /etc/os-release || log "WARNING: script is tested on Ubuntu 22.04 LTS"
[ -f "${SRC_DIR}/backend/server.py" ] || fail "run this script from the project root (backend/ and frontend/ must sit next to it)"

export DEBIAN_FRONTEND=noninteractive

# ----------------------------------------------------------------------------
log "1/8  System packages"
# ----------------------------------------------------------------------------
apt-get update -y
apt-get install -y curl gnupg ca-certificates software-properties-common nginx rsync

# ----------------------------------------------------------------------------
log "2/8  Python 3.11"
# ----------------------------------------------------------------------------
if ! command -v python3.11 >/dev/null 2>&1; then
  add-apt-repository -y ppa:deadsnakes/ppa
  apt-get update -y
  apt-get install -y python3.11 python3.11-venv python3.11-dev
fi
python3.11 --version

# ----------------------------------------------------------------------------
log "3/8  Node.js 20 + Yarn"
# ----------------------------------------------------------------------------
if ! command -v node >/dev/null 2>&1 || [ "$(node -v | cut -d. -f1 | tr -d v)" -lt 18 ]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi
corepack enable || npm install -g yarn
node -v && yarn -v

# ----------------------------------------------------------------------------
log "4/8  MongoDB 7.0"
# ----------------------------------------------------------------------------
if ! systemctl is-active --quiet mongod; then
  if [ ! -f /usr/share/keyrings/mongodb-server-7.0.gpg ]; then
    curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-server-7.0.gpg
    echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" \
      > /etc/apt/sources.list.d/mongodb-org-7.0.list
    apt-get update -y
  fi
  apt-get install -y mongodb-org
  systemctl enable --now mongod
fi
systemctl is-active --quiet mongod || fail "mongod failed to start (check: journalctl -u mongod)"

# ----------------------------------------------------------------------------
log "5/8  Application files -> ${APP_DIR}"
# ----------------------------------------------------------------------------
mkdir -p "${APP_DIR}"
rsync -a --delete \
  --exclude 'node_modules' --exclude 'venv' --exclude '__pycache__' \
  --exclude 'build' --exclude '.git' --exclude 'test_reports' \
  "${SRC_DIR}/backend" "${SRC_DIR}/frontend" "${APP_DIR}/"

# ----------------------------------------------------------------------------
log "6/8  Backend (venv + deps + env + systemd)"
# ----------------------------------------------------------------------------
cd "${APP_DIR}/backend"
[ -d venv ] || python3.11 -m venv venv
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt -q

if [ ! -f .env ]; then
  JWT_SECRET="$(head -c 32 /dev/urandom | base64 | tr -d '=+/')"
  cat > .env <<EOF
MONGO_URL=mongodb://localhost:27017
DB_NAME=${DB_NAME}
JWT_SECRET=${JWT_SECRET}
CORS_ORIGINS=*
EOF
  log "backend/.env created (random JWT secret)"
fi

cat > /etc/systemd/system/${APP_NAME}-backend.service <<EOF
[Unit]
Description=Factory Operations Platform - FastAPI backend
After=network.target mongod.service
Requires=mongod.service

[Service]
WorkingDirectory=${APP_DIR}/backend
ExecStart=${APP_DIR}/backend/venv/bin/uvicorn server:app --host 0.0.0.0 --port ${BACKEND_PORT}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now ${APP_NAME}-backend
systemctl restart ${APP_NAME}-backend

# ----------------------------------------------------------------------------
log "7/8  Frontend production build"
# ----------------------------------------------------------------------------
cd "${APP_DIR}/frontend"
# same-origin deployment: nginx serves the UI and proxies /api on one origin
echo "REACT_APP_BACKEND_URL=" > .env
yarn install --frozen-lockfile --network-timeout 600000
yarn build

# ----------------------------------------------------------------------------
log "8/8  nginx"
# ----------------------------------------------------------------------------
cat > /etc/nginx/sites-available/${APP_NAME} <<EOF
server {
    listen ${HTTP_PORT} default_server;
    server_name _;

    root ${APP_DIR}/frontend/build;
    index index.html;
    client_max_body_size 10m;

    # React SPA
    location / {
        try_files \$uri /index.html;
    }

    # API + WebSocket -> FastAPI backend
    location /api {
        proxy_pass http://127.0.0.1:${BACKEND_PORT};
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
EOF

ln -sf /etc/nginx/sites-available/${APP_NAME} /etc/nginx/sites-enabled/${APP_NAME}
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable --now nginx
systemctl reload nginx

# ----------------------------------------------------------------------------
# Health check
# ----------------------------------------------------------------------------
sleep 3
IP="$(hostname -I | awk '{print $1}')"
if curl -fsS "http://127.0.0.1:${BACKEND_PORT}/api/machines?limit=1" \
     -H "Authorization: Bearer invalid" -o /dev/null -w '%{http_code}' | grep -qE '401|403|200'; then
  log "backend is answering on :${BACKEND_PORT}"
else
  fail "backend not responding (check: journalctl -u ${APP_NAME}-backend -n 50)"
fi

cat <<EOF

============================================================
  Factory Operations Platform deployed successfully!

  Open:            http://${IP}/
  Default logins:  admin / admin123
                   tech / tech123
                   operator / operator123

  Database seeds itself automatically on first backend start
  (hierarchy, 194 machines, users, templates, spares).

  Services:
    systemctl status ${APP_NAME}-backend
    systemctl status mongod
    systemctl status nginx

  Optional Weibull demo data:
    cd ${APP_DIR}/backend && ./venv/bin/python seed_weibull_demo.py
============================================================
EOF
