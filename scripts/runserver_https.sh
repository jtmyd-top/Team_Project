#!/usr/bin/env bash
# ============================================================
#  本地 HTTPS 开发服务器（bash）
#  依赖：django-extensions + Werkzeug + pyOpenSSL
#        mkcert 生成的证书放在 certs/ 目录
#  Web Crypto API 需要 Secure Context（HTTPS 或 localhost），
#  LAN IP 走 HTTP 会导致 crypto.subtle 为 undefined
# ============================================================
set -euo pipefail

cd "$(dirname "$0")/.."

CERT_FILE="certs/server.pem"
KEY_FILE="certs/server-key.pem"
BIND="${BIND:-0.0.0.0:443}"

if [[ ! -f "$CERT_FILE" ]]; then
    cat >&2 <<EOF
[!] 找不到证书 $CERT_FILE
    请先执行：
      mkcert -install
      (cd certs && mkcert -cert-file server.pem -key-file server-key.pem 192.168.1.6 localhost 127.0.0.1)
EOF
    exit 1
fi

echo "[*] Starting HTTPS dev server on $BIND"
echo "[*] Cert: $CERT_FILE"
echo "[*] Open: https://192.168.1.6:443/ 或 https://localhost:443/"
echo "[*] 注意：HTTPS 协议默认端口为 443，用 443 时 URL 里必须显式写 :443"
python manage.py runserver_plus "$BIND" --cert-file="$CERT_FILE" --key-file="$KEY_FILE"
