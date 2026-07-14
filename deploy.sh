#!/usr/bin/env bash
# ============================================================================
#  Factory Operations Platform — ONE-STEP deployment script
#
#  USAGE (from the project root, i.e. the folder containing backend/ + frontend/):
#      sudo bash deploy.sh
#
#  WHAT IT DOES (in order, each stage logs its own success):
#      1/9  System packages        (nginx, curl, rsync, ...)
#      2/9  Python 3.11            (deadsnakes PPA if missing)
#      3/9  Node.js 20 + Yarn      (NodeSource if missing)
#      4/9  MongoDB                (7.0 on Ubuntu 22.04 / 8.0 on Ubuntu 24.04)
#      5/9  App files              -> /opt/factory-ops
#      6/9  Backend                (venv + deps + .env + systemd service :8001)
#      7/9  Frontend               (yarn install + production build)
#      8/9  Nginx                  (serves UI on :80, proxies /api + WebSocket)
#      9/9  Health checks          (backend answering, UI served)
#
#  PREREQUISITES
#      • Ubuntu Server 22.04 LTS (jammy) or 24.04 LTS (noble), x86_64/arm64
#      • Run as root (sudo). Internet access needed for apt/npm/pip downloads.
#      • ~2 GB RAM minimum (frontend build), ~10 GB free disk.
#      • Free ports: 80 (nginx), 8001 (backend, localhost), 27017 (MongoDB, localhost)
#      • LAN-only design: nothing is exposed beyond port 80 by default.
#
#  IDEMPOTENT: safe to re-run at any time — already-installed components are
#  skipped, the app code/build is refreshed, existing backend/.env and the
#  database are PRESERVED. The database seeds itself (hierarchy, machines,
#  default users, templates, spares) on the backend's FIRST start only.
#
#  AFTER DEPLOYMENT
#      Open  http://<server-ip>/  and sign in with the default admin account,
#      then CHANGE ALL DEFAULT PASSWORDS from Administration → Users.
# ============================================================================
set -euo pipefail

APP_NAME="factory-ops"
APP_DIR="/opt/${APP_NAME}"
DB_NAME="factory_ops"
BACKEND_PORT=8001
HTTP_PORT=80
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log()  { echo -e "\e[1;36m[deploy]\e[0m $*"; }
ok()   { echo -e "\e[1;32m[deploy] ✔\e[0m $*"; }
fail() { echo -e "\e[1;31m[deploy] ✖ ERROR:\e[0m $*" >&2; exit 1; }

# ---------------------------------------------------------------- preflight
[ "$(id -u)" -eq 0 ] || fail "run as root:  sudo bash deploy.sh"
[ -f "${SRC_DIR}/backend/server.py" ] || fail "run this script from the project root (backend/ and frontend/ must sit next to it)"

. /etc/os-release
UBUNTU_CODENAME="${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}"
case "${UBUNTU_CODENAME}" in
  jammy) MONGO_SERIES="7.0" ;;   # Ubuntu 22.04
  noble) MONGO_SERIES="8.0" ;;   # Ubuntu 24.04 (MongoDB 7.0 has no noble packages)
  *)     MONGO_SERIES="7.0"; UBUNTU_CODENAME="jammy"
         log "WARNING: untested Ubuntu release '${VERSION_ID:-?}' — using jammy/7.0 repos" ;;
esac
log "Target: Ubuntu ${VERSION_ID:-?} (${UBUNTU_CODENAME}) · MongoDB ${MONGO_SERIES} · app dir ${APP_DIR}"

export DEBIAN_FRONTEND=noninteractive

# ----------------------------------------------------------------------------
log "1/9  System packages"
# ----------------------------------------------------------------------------
apt-get update -y
apt-get install -y curl gnupg ca-certificates software-properties-common nginx rsync
ok "system packages installed"

# ----------------------------------------------------------------------------
log "2/9  Python 3.11"
# ----------------------------------------------------------------------------
if ! command -v python3.11 >/dev/null 2>&1; then
  add-apt-repository -y ppa:deadsnakes/ppa
  apt-get update -y
  apt-get install -y python3.11 python3.11-venv python3.11-dev
fi
ok "python: $(python3.11 --version)"

# ----------------------------------------------------------------------------
log "3/9  Node.js 20 + Yarn"
# ----------------------------------------------------------------------------
if ! command -v node >/dev/null 2>&1 || [ "$(node -v | cut -d. -f1 | tr -d v)" -lt 18 ]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi
corepack enable 2>/dev/null || npm install -g yarn
ok "node $(node -v) · yarn $(yarn -v)"

# ----------------------------------------------------------------------------
log "4/9  MongoDB ${MONGO_SERIES}"
# ----------------------------------------------------------------------------
if ! systemctl is-active --quiet mongod; then
  KEYRING="/usr/share/keyrings/mongodb-server-${MONGO_SERIES}.gpg"
  if [ ! -f "${KEYRING}" ]; then
    curl -fsSL "https://www.mongodb.org/static/pgp/server-${MONGO_SERIES}.asc" | gpg --dearmor -o "${KEYRING}"
    echo "deb [ arch=amd64,arm64 signed-by=${KEYRING} ] https://repo.mongodb.org/apt/ubuntu ${UBUNTU_CODENAME}/mongodb-org/${MONGO_SERIES} multiverse" \
      > "/etc/apt/sources.list.d/mongodb-org-${MONGO_SERIES}.list"
    apt-get update -y
  fi
  apt-get install -y mongodb-org
  systemctl enable --now mongod
fi
systemctl is-active --quiet mongod || fail "mongod failed to start (check: journalctl -u mongod)"
ok "mongod is running (localhost:27017)"

# ----------------------------------------------------------------------------
log "5/9  Application files -> ${APP_DIR}"
# ----------------------------------------------------------------------------
mkdir -p "${APP_DIR}"
rsync -a --delete \
  --exclude 'node_modules' --exclude 'venv' --exclude '__pycache__' \
  --exclude 'build' --exclude '.git' --exclude 'test_reports' \
  --filter='protect backend/.env' \
  "${SRC_DIR}/backend" "${SRC_DIR}/frontend" "${APP_DIR}/"
ok "app source synced (existing backend/.env preserved)"

# ----------------------------------------------------------------------------
log "6/9  Backend (venv + deps + env + systemd)"
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
else
  log "backend/.env already exists — kept as-is"
fi

cat > /etc/systemd/system/${APP_NAME}-backend.service <<EOF
[Unit]
Description=Factory Operations Platform - FastAPI backend
After=network.target mongod.service
Requires=mongod.service

[Service]
WorkingDirectory=${APP_DIR}/backend
ExecStart=${APP_DIR}/backend/venv/bin/uvicorn server:app --host 127.0.0.1 --port ${BACKEND_PORT}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ${APP_NAME}-backend >/dev/null 2>&1
systemctl restart ${APP_NAME}-backend
ok "backend service installed + (re)started (127.0.0.1:${BACKEND_PORT})"

# ----------------------------------------------------------------------------
log "7/9  Frontend production build"
# ----------------------------------------------------------------------------
cd "${APP_DIR}/frontend"
# same-origin deployment: nginx serves the UI and proxies /api on one origin
echo "REACT_APP_BACKEND_URL=" > .env
yarn install --frozen-lockfile --network-timeout 600000
yarn build
ok "frontend built -> ${APP_DIR}/frontend/build"

# ----------------------------------------------------------------------------
log "8/9  nginx"
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
systemctl enable --now nginx >/dev/null 2>&1
systemctl reload nginx
ok "nginx serving on :${HTTP_PORT}"

# ----------------------------------------------------------------------------
log "9/9  Health checks"
# ----------------------------------------------------------------------------
sleep 3
IP="$(hostname -I | awk '{print $1}')"
if curl -fsS "http://127.0.0.1:${BACKEND_PORT}/api/machines?limit=1" \
     -H "Authorization: Bearer invalid" -o /dev/null -w '%{http_code}' | grep -qE '401|403|200'; then
  ok "backend is answering on :${BACKEND_PORT}"
else
  fail "backend not responding (check: journalctl -u ${APP_NAME}-backend -n 50)"
fi
if curl -fsS "http://127.0.0.1:${HTTP_PORT}/" -o /dev/null; then
  ok "frontend is served by nginx on :${HTTP_PORT}"
else
  fail "nginx is not serving the UI (check: nginx -t && journalctl -u nginx -n 50)"
fi

cat <<EOF

============================================================
  ✔ Factory Operations Platform deployed successfully!

  Open:        http://${IP}/
  First login: default admin account (see project docs /
               Administration handover). CHANGE ALL DEFAULT
               PASSWORDS after first sign-in
               (Administration -> Users).

  The database seeds itself automatically on the backend's
  FIRST start (hierarchy, machines, users, templates, spares).
  Re-running this script never wipes existing data.

  Manage services:
    systemctl status ${APP_NAME}-backend
    systemctl status mongod
    systemctl status nginx
  Logs:
    journalctl -u ${APP_NAME}-backend -f

  Update procedure: copy the new source over this folder and
  re-run   sudo bash deploy.sh   (idempotent).
============================================================
EOF
