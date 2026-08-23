#!/usr/bin/env bash
# Corre el flujo agentico contra un gateway de Roxy, resolviendo el venv y
# las dependencias antes de arrancar.
#
#   ./run.sh off                  sin Roxy (nadie evalua ni registra nada)
#   ./run.sh on                   con Roxy desplegada (roxygt.lat/gateway)
#   ./run.sh on --local           con Roxy en localhost:8080
#   ./run.sh on --dashboard-local traza contra dashboard/api en localhost:8000
#
# El arbol de delegacion va al dashboard desplegado salvo que se pida local:
# es donde se mira durante la demo, corra el gateway donde corra.
#
# ROXY_URL / DASHBOARD_API_URL del entorno mandan sobre el destino elegido, y
# a su vez sobre lo que diga .env (load_dotenv no pisa el entorno).
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

CLOUD_ROXY="https://roxygt.lat/gateway"
CLOUD_DASHBOARD="https://roxygt.lat/api"
LOCAL_ROXY="http://localhost:8080"
LOCAL_DASHBOARD="http://localhost:8000"

MODE="off"
TARGET="cloud"
DASHBOARD="cloud"
EXTRA=()

for arg in "$@"; do
  case "$arg" in
    on|off)            MODE="$arg" ;;
    --local|--cloud)   TARGET="${arg#--}" ;;
    --dashboard-local) DASHBOARD="local" ;;
    *)                 EXTRA+=("$arg") ;;
  esac
done

if [ "$TARGET" = "local" ]; then
  export ROXY_URL="${ROXY_URL:-$LOCAL_ROXY}"
else
  export ROXY_URL="${ROXY_URL:-$CLOUD_ROXY}"
fi

if [ "$DASHBOARD" = "local" ]; then
  export DASHBOARD_API_URL="${DASHBOARD_API_URL:-$LOCAL_DASHBOARD}"
else
  export DASHBOARD_API_URL="${DASHBOARD_API_URL:-$CLOUD_DASHBOARD}"
fi

if [ ! -d .venv ]; then
  echo "Creando .venv..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# Reinstala solo cuando requirements.txt cambio: pip tarda mas que la corrida.
HUELLA=".venv/.requirements.sha"
ACTUAL="$(shasum requirements.txt | cut -d' ' -f1)"
if [ "$(cat "$HUELLA" 2>/dev/null || true)" != "$ACTUAL" ]; then
  echo "Instalando dependencias..."
  pip install -q -r requirements.txt
  echo "$ACTUAL" > "$HUELLA"
fi

# Toda corrida queda en disco: lo que se ve en pantalla se va con el scroll,
# y el detalle de que intento cada subagente es lo que hay que poder releer.
mkdir -p runs
LOG="${ROXY_RUN_LOG:-runs/$(date +%Y%m%d-%H%M%S)-$MODE.log}"

# La corrida puede fallar (chequeo previo, una hoja rota) y el log tiene que
# quedar igual, con el aviso de donde esta.
set +e
{
  echo "Roxy:      $ROXY_URL"
  echo "Dashboard: $DASHBOARD_API_URL"
  echo "demo-api:  ${DEMO_API_URL:-https://roxygt.lat/demo-api}"
  echo "MCP:       ${ROXY_MCP_NAME:-el de .env / config.py}"
  echo

  # -u: con la salida entubada a tee, Python la bufferea y la corrida se ve
  # muda hasta el final.
  python3 -u run_demo.py --roxy "$MODE" ${EXTRA+"${EXTRA[@]}"}
} 2>&1 | tee "$LOG"

estado=${PIPESTATUS[0]}
set -e
echo
echo "Corrida guardada en $LOG"
exit "$estado"
