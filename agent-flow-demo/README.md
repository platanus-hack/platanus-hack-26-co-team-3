# agent-flow-demo

Block 5 (idea.md): orquestador + subagentes de LangChain que concilian
facturas de `demo-api` (bloque 4), con o sin `roxy-gateway` (bloque 2) en el
camino.

## Requisitos corriendo en paralelo

1. `mongo-data/run.sh` — Mongo local en `:27017` (bases `roxy` y, una vez
   que corra `demo-api`, `demo_billing`).
2. `demo-api` (`./run.sh` en esa carpeta) — API víctima en `:8001`.
3. `roxy-gateway` (`go run ./cmd/roxy` en esa carpeta) — gateway en `:8080`,
   solo si vas a correr con `--roxy on`.

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

36 tests, sin servicios levantados (HTTP y Mongo mockeados). Cubren la
traducción de la respuesta de Roxy a permiso/negación, el corte por
denegaciones, el reparto recursivo de facturas y la reconstrucción del
árbol de delegación.

## Chequeo previo

`run_demo.py` verifica Mongo, `demo-api` y (con `--roxy on`) el gateway y
el MCP registrado antes de gastar tokens, y aborta con el comando exacto
que falta en vez de un traceback.

## Correr

```bash
python3 run_demo.py --roxy off   # corrompe datos, no hay nada del lado de Roxy
python3 run_demo.py --roxy on    # Roxy evalúa cada update_invoice antes de escribir
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
- `agent_flow/tracing.py` — captura `on_chain_start`/`on_tool_start`/
  `on_llm_start` y escribe `traces/run.jsonl` con el shape propuesto en
  `demo/INTEGRATION-NOTES.md` para la futura colección `traces`.
- `scripts/register_invoices_mcp.py` — upsert de `invoices-mcp` en
  `roxy.mcps` (no toca `mongo-data/population/mcps.mock.json`).
