#!/usr/bin/env bash
# Levanta y baja todo lo que la demo necesita corriendo en la maquina:
# Mongo, demo-api, un evaluador de prueba y roxy-gateway. No implementa nada
# de ningun bloque: solo los arranca en el orden en que dependen entre si.
#
#   ./local-stack.sh up      levanta lo que falte y espera a que responda
#   ./local-stack.sh status   dice quien esta arriba
#   ./local-stack.sh down     baja lo que levanto este script
#
# Con el stack arriba, el contraste se corre desde agent-flow-demo:
#   ./compare.sh --local
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIDS="$RAIZ/demo/.stack.pids"
LOGS="$RAIZ/demo/.stack-logs"

# El gateway le pega a Anthropic para armar la llamada al MCP y no arranca
# sin la key; la unica que hay en el repo es la del flujo de agentes.
KEY_ENV="$RAIZ/agent-flow-demo/.env"

esperar() {  # esperar <url> <nombre> [intentos]
  local url="$1" nombre="$2" intentos="${3:-45}"
  for _ in $(seq 1 "$intentos"); do
    if [ "$(curl -s -m 3 -o /dev/null -w '%{http_code}' "$url" || true)" = "200" ]; then
      echo "  $nombre arriba"
      return 0
    fi
    sleep 2
  done
  echo "  $nombre no respondio en $url" >&2
  return 1
}

lanzar() {  # lanzar <nombre> <archivo-log> <comando...>
  local nombre="$1" log="$2"; shift 2
  mkdir -p "$LOGS"
  ( "$@" > "$LOGS/$log" 2>&1 & echo $! >> "$PIDS" )
  echo "  $nombre lanzado (log: demo/.stack-logs/$log)"
}

up() {
  echo "Mongo (mongo-data)..."
  "$RAIZ/mongo-data/run.sh" > /dev/null
  echo "  Mongo listo en :27017"

  echo "demo-api..."
  if [ "$(curl -s -m 3 -o /dev/null -w '%{http_code}' http://localhost:8001/health/consistency || true)" = "200" ]; then
    echo "  ya estaba arriba"
  else
    lanzar demo-api demo-api.log "$RAIZ/demo-api/run.sh"
    esperar http://localhost:8001/health/consistency demo-api
  fi

  echo "MCP invoices-mcp en roxy.mcps..."
  "$RAIZ/agent-flow-demo/.venv/bin/python3" "$RAIZ/agent-flow-demo/scripts/register_invoices_mcp.py" \
    2>/dev/null || echo "  (corre agent-flow-demo/run.sh una vez para crear su venv)"

  echo "evaluador de prueba..."
  if [ "$(curl -s -m 3 -o /dev/null -w '%{http_code}' http://localhost:9000/health || true)" = "200" ]; then
    echo "  ya estaba arriba"
  else
    lanzar evaluador evaluador.log \
      "$RAIZ/agent-flow-demo/.venv/bin/uvicorn" scripts.stub_evaluator:app --port 9000 \
      --app-dir "$RAIZ/agent-flow-demo"
    esperar http://localhost:9000/health evaluador
  fi

  echo "roxy-gateway..."
  if [ "$(curl -s -m 3 -o /dev/null -w '%{http_code}' http://localhost:8080/health || true)" = "200" ]; then
    echo "  ya estaba arriba"
  else
    local key
    key="$(grep -m1 '^ANTHROPIC_API_KEY=' "$KEY_ENV" 2>/dev/null | cut -d= -f2- || true)"
    [ -n "$key" ] || { echo "  falta ANTHROPIC_API_KEY en agent-flow-demo/.env" >&2; return 1; }
    mkdir -p "$LOGS"
    (
      cd "$RAIZ/roxy-gateway"
      MONGO_URI=mongodb://localhost:27017 \
      MONGO_DB_NAME=roxy \
      EVALUATOR_URL=http://localhost:9000/evaluate \
      ANTHROPIC_API_KEY="$key" \
      DASHBOARD_URL="${DASHBOARD_URL:-https://roxygt.lat/api/log}" \
      HTTP_ADDR=:8080 \
      go run ./cmd/roxy > "$LOGS/roxy-gateway.log" 2>&1 &
      echo $! >> "$PIDS"
    )
    echo "  roxy-gateway lanzado (log: demo/.stack-logs/roxy-gateway.log)"
    esperar http://localhost:8080/health roxy-gateway 60
  fi

  echo
  echo "Listo. El contraste:  cd agent-flow-demo && ./compare.sh --local"
  echo "Las decisiones de Roxy salen en el dashboard desplegado (DASHBOARD_URL)."
}

status() {
  for par in "demo-api|http://localhost:8001/health/consistency" \
             "evaluador|http://localhost:9000/health" \
             "roxy-gateway|http://localhost:8080/health"; do
    local nombre="${par%%|*}" url="${par#*|}" codigo
    codigo="$(curl -s -m 3 -o /dev/null -w '%{http_code}' "$url" 2>/dev/null || true)"
    if [ -z "$codigo" ] || [ "$codigo" = "000" ]; then codigo="sin-respuesta"; fi
    printf '%-14s %s\n' "$nombre" "$codigo"
  done
  local mongo
  mongo="$(docker inspect -f '{{.State.Status}}' roxy-mongo 2>/dev/null || true)"
  printf '%-14s %s\n' mongo "${mongo:-sin-contenedor}"
}

down() {
  if [ -f "$PIDS" ]; then
    while read -r pid; do
      [ -n "$pid" ] || continue
      # Bajar el arbol: matar solo al padre deja vivos a uvicorn y al binario
      # que `go run` compila y lanza aparte.
      pkill -P "$pid" 2>/dev/null || true
      kill "$pid" 2>/dev/null || true
    done < "$PIDS"
    rm -f "$PIDS"
  fi
  # `go run` deja el binario compilado corriendo fuera de ese arbol.
  pkill -f 'exe/roxy$' 2>/dev/null || true
  docker compose -f "$RAIZ/mongo-data/docker-compose.yml" down 2>/dev/null || true
  echo "Stack abajo."
  status
}

case "${1:-up}" in
  up)     up ;;
  status) status ;;
  down)   down ;;
  *)      echo "uso: $0 [up|status|down]" >&2; exit 1 ;;
esac
