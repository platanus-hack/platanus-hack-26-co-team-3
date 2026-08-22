# roxy-gateway

API **roxy**: capa de seguridad entre agentes y MCPs. V1 evalúa cada llamado contra las rules del MCP en Mongo, usando Anthropic (o OpenRouter como fallback). No reenvía al MCP.

## Qué hace

`POST /v1/evaluate` → carga el MCP por `mcpName` → el LLM compara `action` + `payload` con las rules → escribe un documento en `security` (approved o denied) → notifica al dashboard (siempre, fail-open) → responde la decisión.

Si el evaluador (Anthropic/OpenRouter) no responde: `503`, sin log ni notify. Si el MCP no existe: `404`.

## API

`POST /v1/evaluate`

```json
{
  "mcpName": "mongo-catalog-mcp",
  "accessedBy": "agent-subtask-07",
  "action": "drop_table",
  "payload": { "intent": "DROP TABLE orders" }
}
```

### Request body

| Campo | Obligatorio | Tipo | Qué es |
|--------|-------------|------|--------|
| `mcpName` | sí | string | Nombre del MCP en Mongo (`roxy.mcps.name`). Roxy carga ese documento (rules, server, authorization). |
| `accessedBy` | sí | string | Quién pide el acceso (id del agente). Va al log y al dashboard. No hay JWT: es texto libre. |
| `action` | sí | string | Qué quiere hacer el agente. **No hay enum.** El LLM lo compara con las rules del MCP. |
| `payload` | no | JSON (objeto, array, string…) | Detalle extra: intent, collection, units, etc. Si no va, se evalúa solo con `action`. |

Si falta `mcpName`, `accessedBy` o `action` → **400** `{"error":"invalid request"}`.  
Si `mcpName` no existe en Mongo → **404** `{"error":"mcp not found"}`.

#### `mcpName`

Valores del mock:

| Valor | Para qué |
|--------|----------|
| `mongo-catalog-mcp` | catálogo / orders |
| `payments-mcp` | pagos / transactions / refunds |
| `inventory-mcp` | stock |

Cualquier otro string es válido a nivel JSON; si no está en Mongo es 404.

#### `accessedBy`

Texto libre. En el mock/demo se usa:

- `agent-orchestrator-01` — orquestador (en payments, las writes a `transactions` suelen ir allowed)
- `agent-subtask-07`, `agent-subtask-12`, `agent-subtask-03` — subagentes (más fácil que rompan rules)

No hay lista cerrada; lo que pongas queda en `security.accessedBy`.

#### `action`

La API no restringe el valor. El modelo lo interpreta. Convenientes para el mock:

| `action` | Uso típico |
|----------|------------|
| `read` | lecturas (orders, stock) → suele **approved** |
| `write` | writes (p.ej. transactions) |
| `drop_table` | DROP / destructivo → **denied** en catalog |
| `bulk_stock_adjust` | ajuste masivo de inventario |
| `refund` | reembolsos en payments |

También sirve `query`, `delete`, `update`, etc. Cuanto más claro, mejor decide el LLM.

#### `payload`

Libre. Lo que más usa el evaluador:

| Clave (sugerida) | Ejemplo | Para qué |
|------------------|---------|----------|
| `intent` | `"DROP TABLE orders"` | frase en lenguaje natural (la más útil) |
| `units` | `5000` | inventario (rule: deny > 1000) |
| `amount` | `250` | refunds |
| `collection` | `"orders"` / `"transactions"` | sobre qué colección |

```json
"payload": { "intent": "read-only query on the orders collection" }
```

```json
"payload": { "intent": "decrease stock by 5000 units", "units": 5000 }
```

```json
"payload": { "intent": "issue a refund", "amount": 250 }
```

### Response body

| Campo | Cuándo |
|--------|--------|
| `decision` | `"approved"` o `"denied"` |
| `mcpName` | eco del MCP evaluado |
| `accessedBy` | eco del agente |
| `violatedRule` | rule rota (`priority` + `instruction`), o `null` si approved |
| `reason` | texto del modelo |
| `logId` | id del documento en `security` |
| `connection` | **solo si approved**: `url`, `protocol`, `authorization` (`type`, `credentialsRef`, `credentials`). Si denied → `null` |

El dashboard recibe el mismo outcome (status, mcp, agent, rule, description) **sin** `connection` ni credenciales.

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

## Docker

```bash
docker build -t roxy-gateway .
docker run --rm -p 8080:8080 --env-file .env -e HTTP_ADDR=:8080 roxy-gateway
```

Producción (Render + Atlas): ver [DEPLOY.md](DEPLOY.md).

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
