#!/usr/bin/env bash
# Nainštaluje konektor ako systemd službu v sieťovom režime.
#
# Spustenie na serveri:
#     sudo bash deploy/install.sh
#
# Skript sám nájde ZeroTier adresu, vygeneruje prístupový token, vytvorí
# /etc/zoho-mail-mcp.env a spustí službu. Zoho údaje doplníš až potom –
# služba beží aj bez nich, len nástroje hlásia, že chýba konfigurácia.
#
# Nič neprepisuje: ak /etc/zoho-mail-mcp.env už existuje, nechá ho tak.

set -euo pipefail

SERVICE_NAME="zoho-mail-mcp"
ENV_FILE="/etc/${SERVICE_NAME}.env"
UNIT_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
SERVICE_USER="zoho-mcp"
PORT="${ZOHO_MCP_PORT:-8765}"
HOST="${ZOHO_MCP_HOST:-}"

PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_SRC="${PKG_DIR}/deploy/${SERVICE_NAME}.service"
ENV_SRC="${PKG_DIR}/deploy/${SERVICE_NAME}.env.example"

info()  { printf '\033[1m==>\033[0m %s\n' "$1"; }
warn()  { printf '\033[33mPozor:\033[0m %s\n' "$1" >&2; }
die()   { printf '\033[31mChyba:\033[0m %s\n' "$1" >&2; exit 1; }

usage() {
    cat <<'USAGE'
Použitie: sudo bash deploy/install.sh [--host ADRESA] [--port PORT]

  --host   adresa, na ktorú sa služba viaže (predvolene sa nájde ZeroTier adresa)
  --port   port služby (predvolene 8765)
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --host) HOST="${2:-}"; [[ -n "$HOST" ]] || die "--host potrebuje adresu"; shift 2 ;;
        --port) PORT="${2:-}"; [[ "$PORT" =~ ^[0-9]+$ ]] || die "--port potrebuje číslo"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; die "neznámy prepínač $1" ;;
    esac
done

[[ $EUID -eq 0 ]] || die "spusti to cez sudo."
[[ -f "$UNIT_SRC" ]] || die "nenašiel som $UNIT_SRC – spúšťaš to z klonu repozitára?"

# --- 1. adresa, na ktorej má služba počúvať --------------------------------

find_zerotier_address() {
    ip -4 -o addr show 2>/dev/null \
        | awk '$2 ~ /^zt/ { split($4, parts, "/"); print parts[1]; exit }'
}

if [[ -z "$HOST" ]]; then
    HOST="$(find_zerotier_address || true)"
fi

if [[ -z "$HOST" ]]; then
    die "ZeroTier rozhranie som nenašiel. Skontroluj 'sudo zerotier-cli listnetworks',
     alebo adresu zadaj ručne: sudo bash deploy/install.sh --host 10.147.17.5"
fi
info "Služba bude počúvať na ${HOST}:${PORT}"

# --- 2. závislosti ----------------------------------------------------------

PYTHON="$(command -v python3)" || die "python3 na tomto stroji nie je."

info "Inštalujem Python závislosti"
"$PYTHON" -m pip install --break-system-packages --quiet \
        "mcp>=2.0,<3.0" "starlette>=0.40" "uvicorn>=0.30" \
    || "$PYTHON" -m pip install --quiet "mcp>=2.0,<3.0" "starlette>=0.40" "uvicorn>=0.30" \
    || die "inštalácia závislostí zlyhala."

# --- 3. systémový používateľ ------------------------------------------------

if id "$SERVICE_USER" >/dev/null 2>&1; then
    info "Používateľ ${SERVICE_USER} už existuje"
else
    info "Vytváram používateľa ${SERVICE_USER}"
    useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi

# Kód musí byť čitateľný pre používateľa služby.
chmod -R a+rX "$PKG_DIR"

# --- 4. konfigurácia --------------------------------------------------------

if [[ -f "$ENV_FILE" ]]; then
    info "${ENV_FILE} už existuje, nechávam ho tak"
    AUTH_TOKEN="$(grep '^ZOHO_MCP_AUTH_TOKEN=' "$ENV_FILE" | cut -d= -f2- | tr -d "\"'")"
else
    info "Vytváram ${ENV_FILE}"
    AUTH_TOKEN="$("$PYTHON" -c 'import secrets; print(secrets.token_urlsafe(32))')"
    install -m 600 -o root -g root "$ENV_SRC" "$ENV_FILE"
    sed -i \
        -e "s|^ZOHO_MCP_AUTH_TOKEN=.*|ZOHO_MCP_AUTH_TOKEN=${AUTH_TOKEN}|" \
        -e "s|^ZOHO_MCP_HOST=.*|ZOHO_MCP_HOST=${HOST}|" \
        -e "s|^ZOHO_MCP_PORT=.*|ZOHO_MCP_PORT=${PORT}|" \
        "$ENV_FILE"
fi

# --- 5. systemd unit --------------------------------------------------------

info "Zapisujem ${UNIT_FILE}"
sed -e "s|/opt/common-task/zoho-mail-mcp|${PKG_DIR}|g" \
    -e "s|^ExecStart=.*|ExecStart=${PYTHON} -m zoho_mail_mcp --transport http|" \
    "$UNIT_SRC" > "$UNIT_FILE"
chmod 644 "$UNIT_FILE"

systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME"

# --- 6. kontrola ------------------------------------------------------------

sleep 2
if ! systemctl is-active --quiet "$SERVICE_NAME"; then
    warn "Služba nebeží. Pozri: journalctl -u ${SERVICE_NAME} -n 30 --no-pager"
    exit 1
fi

if command -v curl >/dev/null 2>&1; then
    if curl --silent --max-time 5 "http://${HOST}:${PORT}/health" | grep -q '"ok"'; then
        info "Služba odpovedá na http://${HOST}:${PORT}/health"
    else
        warn "Služba beží, ale /health neodpovedá podľa očakávania."
    fi
fi

cat <<EOF

--------------------------------------------------------------------
Hotovo. Služba beží na ${HOST}:${PORT}

Ešte doplň prístupy do Zoho (ZOHO_DC, ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET,
ZOHO_REFRESH_TOKEN) do ${ENV_FILE} a reštartuj:

    sudo nano ${ENV_FILE}
    sudo systemctl restart ${SERVICE_NAME}

Na firemných počítačoch potom spusti:

    claude mcp add --transport http zoho-mail http://${HOST}:${PORT}/mcp \\
      --scope user \\
      --header "Authorization: Bearer ${AUTH_TOKEN}"

Ten token je prístup do firemnej pošty – posielaj ho bezpečným kanálom.

Log služby:  journalctl -u ${SERVICE_NAME} -f
--------------------------------------------------------------------
EOF
