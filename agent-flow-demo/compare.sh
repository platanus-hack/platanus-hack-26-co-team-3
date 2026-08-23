#!/usr/bin/env bash
# Corre el mismo flujo dos veces -sin Roxy y con Roxy- y contrasta el estado
# en que quedaron las facturas. Cada corrida resetea demo-api, asi que las
# dos parten de los mismos datos limpios.
#
#   ./compare.sh              contra la Roxy desplegada
#   ./compare.sh --local      contra la Roxy de localhost:8080
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

SELLO="$(date +%Y%m%d-%H%M%S)"
DIR="runs/$SELLO"
mkdir -p "$DIR"

for modo in off on; do
  echo "==================== Roxy $modo ===================="
  if ! ./run.sh "$modo" "$@" 2>&1 | tee "$DIR/$modo.log"; then
    echo "La corrida con Roxy $modo fallo; log en $DIR/$modo.log" >&2
    exit 1
  fi
  echo
done

resumen() {
  local log="$1"
  echo "  aprobadas:      $(grep -c 'approved]' "$log" || true)"
  echo "  denegadas:      $(grep -c 'denied]' "$log" || true)"
  echo "  sin supervisar: $(grep -c 'unsupervised]' "$log" || true)"
  echo "  veredicto: $(grep -m1 '^RESULTADO:' "$log" | cut -d: -f2- | xargs)"
}

echo "==================== Contraste ===================="
echo "SIN Roxy:"; resumen "$DIR/off.log"
echo "CON Roxy:"; resumen "$DIR/on.log"
echo
echo "Logs completos en $DIR/"
