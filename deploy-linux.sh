#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/deepresearchpro"
DOMAIN="_"
REPO_URL=""
BRANCH="main"

SERVICE_NAME="deepresearchpro-backend"
APP_USER="deepresearchpro"

ETC_DIR="/etc/deepresearchpro"
BACKEND_ENV_FILE="${ETC_DIR}/backend.env"
FRONTEND_ENV_FILE="${ETC_DIR}/frontend.env"

DATA_DIR="/var/lib/deepresearchpro"

usage() {
  cat <<'EOF'
Usage:
  sudo ./deploy-linux.sh [options]

Options:
  --repo <git_url>           Git 仓库地址（推荐）
  --branch <name>            分支名（默认 main）
  --app-dir <path>           安装目录（默认 /opt/deepresearchpro）
  --domain <domain>          Nginx server_name（默认 _）
  --backend-env <path>       后端环境变量文件路径（默认 /etc/deepresearchpro/backend.env）
  --frontend-env <path>      前端构建环境变量文件路径（默认 /etc/deepresearchpro/frontend.env）
  --no-nginx                 跳过 Nginx 配置
  -h, --help                 显示帮助

Notes:
  - 仅支持 Ubuntu/Debian（需要 apt-get 与 systemd）
  - 后端默认绑定 127.0.0.1:8000；Nginx 代理 /api 到后端
EOF
}

NO_NGINX=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      REPO_URL="${2:-}"; shift 2 ;;
    --branch)
      BRANCH="${2:-}"; shift 2 ;;
    --app-dir)
      APP_DIR="${2:-}"; shift 2 ;;
    --domain)
      DOMAIN="${2:-}"; shift 2 ;;
    --backend-env)
      BACKEND_ENV_FILE="${2:-}"; shift 2 ;;
    --frontend-env)
      FRONTEND_ENV_FILE="${2:-}"; shift 2 ;;
    --no-nginx)
      NO_NGINX=1; shift 1 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

SUDO=""
if [[ "$(id -u)" -ne 0 ]]; then
  if command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
  else
    echo "需要 root 权限运行（或安装 sudo）" >&2
    exit 1
  fi
fi

require_cmd() {
  command -v "$1" >/dev/null 2>&1
}

ensure_deps() {
  if ! require_cmd apt-get; then
    echo "未找到 apt-get，仅支持 Ubuntu/Debian" >&2
    exit 1
  fi
  if ! require_cmd systemctl; then
    echo "未找到 systemctl，仅支持 systemd 系统" >&2
    exit 1
  fi

  ${SUDO} apt-get update -y
  ${SUDO} apt-get install -y \
    ca-certificates \
    curl \
    git \
    nginx \
    python3 \
    python3-pip \
    python3-venv \
    rsync \
    sqlite3 \
    build-essential
}

ensure_node() {
  local have_node=0
  if require_cmd node; then
    have_node=1
  fi

  if [[ "$have_node" -eq 0 ]]; then
    ${SUDO} apt-get install -y nodejs npm
  fi

  local node_major
  node_major="$(node -p "process.versions.node.split('.')[0]")" || node_major="0"
  if [[ "$node_major" -lt 18 ]]; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | ${SUDO} -E bash -
    ${SUDO} apt-get install -y nodejs
  fi
}

ensure_user_and_dirs() {
  if ! id "$APP_USER" >/dev/null 2>&1; then
    ${SUDO} useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
  fi

  ${SUDO} mkdir -p "$APP_DIR" "$ETC_DIR" "$DATA_DIR"
  ${SUDO} chown -R "$APP_USER":"$APP_USER" "$DATA_DIR"
}

deploy_code() {
  if [[ -n "$REPO_URL" ]]; then
    if [[ -d "$APP_DIR/.git" ]]; then
      ${SUDO} -u "$APP_USER" git -C "$APP_DIR" fetch --all --prune
      ${SUDO} -u "$APP_USER" git -C "$APP_DIR" checkout "$BRANCH"
      ${SUDO} -u "$APP_USER" git -C "$APP_DIR" pull --ff-only origin "$BRANCH"
    else
      ${SUDO} rm -rf "$APP_DIR"
      ${SUDO} mkdir -p "$(dirname "$APP_DIR")"
      ${SUDO} -u "$APP_USER" git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$APP_DIR"
    fi
    return
  fi

  local src_dir
  src_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if [[ ! -f "$src_dir/package.json" ]] || [[ ! -d "$src_dir/backend" ]]; then
    echo "未提供 --repo，且脚本未在项目根目录下运行" >&2
    exit 1
  fi

  ${SUDO} mkdir -p "$APP_DIR"
  ${SUDO} rsync -a --delete \
    --exclude .git \
    --exclude node_modules \
    --exclude dist \
    --exclude backend/.venv \
    --exclude src-tauri/target \
    "$src_dir/" "$APP_DIR/"

  ${SUDO} chown -R "$APP_USER":"$APP_USER" "$APP_DIR"
}

write_env_files_if_missing() {
  ${SUDO} mkdir -p "$ETC_DIR"

  if [[ ! -f "$FRONTEND_ENV_FILE" ]]; then
    ${SUDO} bash -c "cat > '$FRONTEND_ENV_FILE' <<'EOF'
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
EOF"
    ${SUDO} chmod 600 "$FRONTEND_ENV_FILE"
  fi

  if [[ ! -f "$BACKEND_ENV_FILE" ]]; then
    ${SUDO} bash -c "cat > '$BACKEND_ENV_FILE' <<'EOF'
DEBUG=false
HOST=127.0.0.1
PORT=8000

LLM_PROVIDER=openai
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=

DATABASE_URL=sqlite+aiosqlite:////var/lib/deepresearchpro/research.db
CHROMA_PERSIST_DIR=/var/lib/deepresearchpro/chroma
EOF"
    ${SUDO} chmod 600 "$BACKEND_ENV_FILE"
  fi
}

build_frontend() {
  local env_dst
  env_dst="${APP_DIR}/.env.production.local"
  if [[ -s "$FRONTEND_ENV_FILE" ]] \
    && grep -qE '^VITE_SUPABASE_URL=.+$' "$FRONTEND_ENV_FILE" \
    && grep -qE '^VITE_SUPABASE_ANON_KEY=.+$' "$FRONTEND_ENV_FILE"; then
    ${SUDO} cp "$FRONTEND_ENV_FILE" "$env_dst"
  elif [[ -f "$APP_DIR/.env.local" ]]; then
    ${SUDO} cp "$APP_DIR/.env.local" "$env_dst"
  else
    ${SUDO} bash -c "cat > '$env_dst' <<'EOF'
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
EOF"
  fi
  ${SUDO} chown "$APP_USER":"$APP_USER" "$env_dst"

  pushd "$APP_DIR" >/dev/null
  if [[ -f package-lock.json ]]; then
    ${SUDO} -u "$APP_USER" npm ci
  else
    ${SUDO} -u "$APP_USER" npm install
  fi
  ${SUDO} -u "$APP_USER" npm run build
  popd >/dev/null
}

setup_backend_venv() {
  pushd "$APP_DIR/backend" >/dev/null
  ${SUDO} -u "$APP_USER" python3 -m venv .venv
  ${SUDO} -u "$APP_USER" ./.venv/bin/python -m pip install -U pip
  ${SUDO} -u "$APP_USER" ./.venv/bin/pip install -r requirements.txt
  popd >/dev/null
}

write_systemd_unit() {
  local unit_path
  unit_path="/etc/systemd/system/${SERVICE_NAME}.service"
  ${SUDO} bash -c "cat > '$unit_path' <<EOF
[Unit]
Description=DeepResearchPro Backend
After=network.target

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}/backend
EnvironmentFile=${BACKEND_ENV_FILE}
ExecStart=${APP_DIR}/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF"
}

write_nginx_site() {
  local site_avail
  local site_enabled
  site_avail="/etc/nginx/sites-available/deepresearchpro"
  site_enabled="/etc/nginx/sites-enabled/deepresearchpro"

  ${SUDO} bash -c "cat > '$site_avail' <<EOF
server {
  listen 80;
  server_name ${DOMAIN};

  root ${APP_DIR}/dist;
  index index.html;

  location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection \"upgrade\";
  }

  location / {
    try_files \$uri \$uri/ /index.html;
  }
}
EOF"

  ${SUDO} rm -f /etc/nginx/sites-enabled/default
  if [[ ! -L "$site_enabled" ]]; then
    ${SUDO} ln -s "$site_avail" "$site_enabled"
  fi
}

restart_services() {
  ${SUDO} systemctl daemon-reload
  ${SUDO} systemctl enable --now "$SERVICE_NAME"

  if [[ "$NO_NGINX" -eq 0 ]]; then
    ${SUDO} nginx -t
    ${SUDO} systemctl enable --now nginx
    ${SUDO} systemctl restart nginx
  fi
}

post_checks() {
  if require_cmd curl; then
    curl -fsS http://127.0.0.1:8000/health >/dev/null || true
    if [[ "$NO_NGINX" -eq 0 ]]; then
      curl -fsS http://127.0.0.1/ >/dev/null || true
    fi
  fi

  echo "部署完成："
  echo "- 后端服务: systemctl status ${SERVICE_NAME}"
  echo "- 前端静态: ${APP_DIR}/dist"
  if [[ "$NO_NGINX" -eq 0 ]]; then
    echo "- Nginx: systemctl status nginx"
    echo "- 访问: http://${DOMAIN}/"
  fi
  echo "- 配置文件: ${BACKEND_ENV_FILE} / ${FRONTEND_ENV_FILE}"
}

ensure_deps
ensure_node
ensure_user_and_dirs
deploy_code
write_env_files_if_missing
build_frontend
setup_backend_venv
write_systemd_unit
if [[ "$NO_NGINX" -eq 0 ]]; then
  write_nginx_site
fi
restart_services
post_checks
