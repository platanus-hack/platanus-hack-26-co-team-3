# roxy-gateway

API **roxy**: capa de seguridad entre agentes y MCPs. V1 evalúa cada llamado contra las rules del MCP en Mongo, usando Anthropic (o OpenRouter como fallback). No reenvía al MCP.

## Qué hace

`POST /v1/evaluate` → carga el MCP por `mcpName` → el LLM compara `action` + `payload` con las rules → escribe un documento en `security` (approved o denied) → notifica al dashboard (siempre, fail-open) → responde la decisión.

Si el evaluador (Anthropic/OpenRouter) no responde: `503`, sin log ni notify. Si el MCP no existe: `404`.

## Requisitos

- Go 1.22+
- Mongo en `mongodb://localhost:27017`, database `roxy` (el bloque `mongo-data` lo levanta con `./run.sh`)
- `ANTHROPIC_API_KEY` (preferido) o `OPENROUTER_API_KEY`

## Config

```bash
cd roxy-gateway
cp .env.example .env
# edita ANTHROPIC_API_KEY
set -a && source .env && set +a
```

| Variable | Default | Notas |
|----------|---------|--------|
| `HTTP_ADDR` | `:8080` | |
| `MONGO_URI` | required | |
| `MONGO_DB_NAME` | `roxy` | |
| `ANTHROPIC_API_KEY` | una de las dos keys | preferida si está seteada |
| `ANTHROPIC_MODEL` | `claude-sonnet-5` | effort `low` para clasificar rules barato y rápido |
| `ANTHROPIC_BASE_URL` | `https://api.anthropic.com` | |
| `OPENROUTER_API_KEY` | una de las dos keys | fallback si no hay Anthropic |
| `OPENROUTER_MODEL` | `openai/gpt-4o-mini` | |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | |
| `DASHBOARD_URL` | vacío = no-op | POST JSON en allow y deny |

## Tests

```bash
go test ./...
```

## Run

```bash
go run ./cmd/roxy
```

Health:

```bash
curl -s localhost:8080/health
```

Deny (drop table contra `mongo-catalog-mcp`):

```bash
curl -s -X POST localhost:8080/v1/evaluate \
  -H 'Content-Type: application/json' \
  -d '{"mcpName":"mongo-catalog-mcp","accessedBy":"agent-subtask-07","action":"drop_table","payload":{"intent":"DROP TABLE orders"}}'
```

Allow (lectura de inventario):

```bash
curl -s -X POST localhost:8080/v1/evaluate \
  -H 'Content-Type: application/json' \
  -d '{"mcpName":"inventory-mcp","accessedBy":"agent-orchestrator-01","action":"read","payload":{"intent":"read stock levels"}}'
```

Cada respuesta 200 deja un documento en `roxy.security`.
