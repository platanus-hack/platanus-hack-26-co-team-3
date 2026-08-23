# agent-flow-demo

Block 5 (idea.md): orquestador + subagentes de LangChain que concilian
facturas de `demo-api` (bloque 4), con o sin `roxy-gateway` (bloque 2) en el
camino.

## Requisitos corriendo en paralelo

1. `mongo-data/run.sh` — Mongo local en `:27017` (bases `roxy` y, una vez
   que corra `demo-api`, `demo_billing`).
2. `demo-api` (`./run.sh` en esa carpeta) — API víctima en `:8001`.
3. Solo para `--roxy on --local`, dos procesos más:
   - un evaluador en `:9000` — mientras el bloque 10 no exista,
     `uvicorn scripts.stub_evaluator:app --port 9000` desde esta carpeta;
   - `roxy-gateway` en `:8080`, que no arranca sin las tres variables:

     ```bash
     cd ../roxy-gateway
     MONGO_URI=mongodb://localhost:27017 \
     EVALUATOR_URL=http://localhost:9000/evaluate \
     ANTHROPIC_API_KEY=... \
     go run ./cmd/roxy
     ```

   Con `--roxy on` a secas se usa la Roxy desplegada y nada de esto hace falta.

## Setup

```bash
cd agent-flow-demo
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # completar ANTHROPIC_API_KEY
python3 scripts/register_invoices_mcp.py   # una vez, mientras Mongo esté arriba
```

## Tests

```bash
python3 -m pytest tests/ -q
```

22 tests, sin servicios levantados (HTTP y Mongo mockeados). Cubren la
traducción de la respuesta de Roxy a permiso/negación, el corte por
denegaciones, el reparto recursivo de facturas y la reconstrucción del
árbol de delegación.

## Chequeo previo

`run_demo.py` verifica Mongo, `demo-api` y (con `--roxy on`) el gateway y
el MCP registrado antes de gastar tokens, y aborta con el comando exacto
que falta en vez de un traceback.

## Correr

`run.sh` resuelve el venv, las dependencias y a qué Roxy se le pregunta; la
flag `--roxy` de `run_demo.py` sigue siendo la que manda sobre `.env`.

```bash
./run.sh off              # sin Roxy: los subagentes escriben directo
./run.sh on               # con la Roxy desplegada (roxygt.lat/gateway)
./run.sh on --local       # con un gateway en localhost:8080
./run.sh on --dashboard-local   # además, traza contra dashboard/api local
```

`compare.sh` corre las dos y contrasta en qué estado quedaron las facturas:

```bash
./compare.sh              # contra la Roxy desplegada
./compare.sh --local      # contra la Roxy local
```

Deja los logs de ambas corridas en `runs/<timestamp>/` y termina con el
resumen: consistencia antes/después de cada una y cuántas operaciones negó
Roxy.

Sin los wrappers es lo mismo de siempre:

```bash
python3 run_demo.py --roxy off
python3 run_demo.py --roxy on
```

Cada corrida resetea `demo-api` a datos limpios y vuelve a inyectar las
notas de cliente antes de lanzar el flujo — se puede correr las veces que
haga falta sin arrastrar corrupción de la corrida anterior.

## Estructura

- `agent_flow/mongo_tools.py` — el "MCP de Mongo": `read_invoice` /
  `update_invoice` sobre `demo_billing.invoices`. `update_invoice` es quien
  llama a Roxy (si `ROXY_ENABLED`) antes de escribir — Roxy solo evalúa, no
  reenvía la petición al MCP real. Si aprueba, la respuesta trae
  `connection` (url + credenciales del MCP, el "exchange de token" de
  idea.md) y es esa conexión, no una fija del proceso, la que se usa para
  el write.
- `agent_flow/orchestrator.py` — el orquestador (un LLM que decide a qué
  factura delega qué subagente) y los subagentes (`AgentExecutor` con las
  tools de arriba).
- `agent_flow/seed_injection.py` — agrega `notes` a dos facturas del seed de
  Freddy (una nota legítima, una que empuja a saltarse auditoría).
- La trazabilidad y el control de acceso salen del SDK (`roxy-sdk/`, publicado como `roxy`): una
  instancia de `Roxy` se pasa como callback y registra el árbol en
  `/agents` sola.
- `scripts/register_invoices_mcp.py` — upsert de `invoices-mcp` en
  `roxy.mcps` (no toca `mongo-data/population/mcps.mock.json`). El
  `server.url` apunta a demo-api por HTTP: cuando Roxy aprueba, le pega al
  MCP, y una URL que no sea HTTP alcanzable desde el gateway deja al planner
  sin nada que llamar y devuelve 503 en toda operación permitida.
- `scripts/stub_evaluator.py` — evaluador de mentira para probar en local
  mientras el bloque 10 no exista (`uvicorn scripts.stub_evaluator:app
  --port 9000`). No va a la demo.
