@echo off
chcp 65001 > nul
REM ============================================================
REM  Local HTTPS dev server (Windows)
REM  Deps: django-extensions + Werkzeug + pyOpenSSL
REM  Certs (mkcert-signed) live under certs\
REM  Web Crypto API needs Secure Context (HTTPS or localhost);
REM  plain HTTP over a LAN IP leaves crypto.subtle undefined.
REM ============================================================

setlocal
cd /d %~dp0..

set CERT_FILE=certs\server.pem
set KEY_FILE=certs\server-key.pem
set BIND=0.0.0.0:443

if not exist %CERT_FILE% (
    echo [!] Cert not found: %CERT_FILE%
    echo     Run first:
    echo       mkcert -install
    echo       cd certs ^&^& mkcert -cert-file server.pem -key-file server-key.pem 192.168.1.6 localhost 127.0.0.1
    exit /b 1
)

echo [*] Starting HTTPS dev server on %BIND%
echo [*] Cert: %CERT_FILE%
echo [*] Open: https://192.168.1.6/ or https://localhost/   (443 is default, no port needed)
python manage.py runserver_plus %BIND% --cert-file=%CERT_FILE% --key-file=%KEY_FILE%

endlocal
