#!/usr/bin/env bash
# ============================================================
#  本地 HTTPS 开发服务器（bash） - Daphne (ASGI)
#  依赖：daphne + channels + channels_redis（在 .venv 中）
#        mkcert 生成的证书放在 certs/ 目录
#  Web Crypto API 需要 Secure Context（HTTPS 或 localhost），
#  LAN IP 走 HTTP 会导致 crypto.subtle 为 undefined
#
#  使用 Daphne 而非 runserver_plus，因为后者基于 Werkzeug 是纯 WSGI，
#  不支持 WebSocket，会导致 /ws/messages/ 连不上、typing/实时消息失效。
# ============================================================
set -euo pipefail

cd "$(dirname "$0")/.."

CERT_FILE="certs/server.pem"
KEY_FILE="certs/server-key.pem"
BIND_HOST="${BIND_HOST:-0.0.0.0}"
BIND_PORT="${BIND_PORT:-443}"

if [[ ! -f "$CERT_FILE" ]]; then
    cat >&2 <<EOF
[!] 找不到证书 $CERT_FILE
    请先执行：
      mkcert -install
      (cd certs && mkcert -cert-file server.pem -key-file server-key.pem 192.168.1.6 localhost 127.0.0.1)
EOF
    exit 1
fi

# 收集静态文件（首次或前端构建后需要执行；--noinput 避免交互）
python manage.py collectstatic --noinput >/dev/null 2>&1 || true

echo "[*] Starting HTTPS ASGI (Daphne) server on $BIND_HOST:$BIND_PORT"
echo "[*] Cert: $CERT_FILE"
echo "[*] Open: https://192.168.1.6:443/ 或 https://localhost:443/"
echo "[*] WebSocket endpoint: wss://localhost/ws/messages/"

# Daphne 的 SSL 端点格式：ssl:443:privateKey=...:certKey=...
exec daphne \
    -e "ssl:${BIND_PORT}:privateKey=${KEY_FILE}:certKey=${CERT_FILE}" \
    -b "$BIND_HOST" \
    Team_Project.asgi:application
