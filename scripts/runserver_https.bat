@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0.."

rem Twisted endpoint strings use ":" as separators. Use forward slashes
rem in certificate paths so Windows backslashes are not parsed as escapes.
set "CERT_FILE=certs/server.pem"
set "KEY_FILE=certs/server-key.pem"
set "BIND_PORT=443"

if not exist "%CERT_FILE%" (
    echo [!] Cert not found: %CERT_FILE%
    echo     Run first:
    echo       mkcert -install
    echo       cd certs ^&^& mkcert -cert-file server.pem -key-file server-key.pem 192.168.1.6 localhost 127.0.0.1
    exit /b 1
)

python manage.py collectstatic --noinput >nul 2>&1

echo [*] Starting HTTPS ASGI (Daphne) server on 0.0.0.0:%BIND_PORT%
echo [*] Cert: %CERT_FILE%
echo [*] Open: https://192.168.1.6/ or https://localhost/   (443 is default, no port needed)
echo [*] WebSocket endpoint: wss://localhost/ws/messages/

rem Use one SSL endpoint only; do not add -b/-p or Daphne will also open
rem a plaintext 8000 listener.
daphne -e "ssl:%BIND_PORT%:privateKey=%KEY_FILE%:certKey=%CERT_FILE%:interface=0.0.0.0" Team_Project.asgi:application

endlocal
