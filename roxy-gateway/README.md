# roxy-gateway

API **roxy**: capa de seguridad entre agentes y MCPs. V1 no evalúa rules: llama a un **evaluator API**, y según el veredicto pega al MCP o corta el acceso.

## Qué hace

`POST /v1/evaluate` → carga el MCP por `mcpName` → POST al evaluator (`EVALUATOR_URL`) con mcp + request + time, **sin credenciales** → log + dashboard →

- evaluator `allowed: false` → **403** sin body (no llama al MCP)
- evaluator `allowed: true` → **Sonnet 5** arma method/url/body del MCP (no hardcodeado) → Roxy ejecuta ese HTTP, inyecta credenciales de Mongo, y **devuelve la respuesta cruda del MCP**
- evaluator caído → **503**
- planner (Sonnet) caído → **503** `planner unavailable`
- MCP caído → **502**
- MCP no existe → **404**

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

### Response (hacia el agente)

| Evaluator | HTTP Roxy | Body |
|-----------|-----------|------|
| `allowed: true` | el status que devolvió el MCP (suele 200) | **crudo del MCP** (no el JSON de Roxy) |
| `allowed: false` | **403** | vacío |
| evaluator down | **503** | `{"error":"evaluator unavailable"}` |
| MCP down | **502** | `{"error":"mcp unavailable"}` |

Las credenciales **no** se devuelven al agente: Roxy las usa para pegarle al MCP. El dashboard sigue recibiendo status, mcp, agent, rule y description, sin secretos.

El evaluator responde `allowed`, `violatedPriority`, `reason` (lo que usa Roxy). `attributes` y `governingRule` son transparencia del evaluator; Roxy no los exige.

## Requisitos

- Go 1.22+
- Mongo en `mongodb://localhost:27017`, database `roxy` (el bloque `mongo-data` lo levanta con `./run.sh`)
- `EVALUATOR_URL` (API de veredicto)
- `ANTHROPIC_API_KEY` (planner Sonnet: arma el HTTP del MCP)

## Config

```bash
cd roxy-gateway
cp .env.example .env
# edita EVALUATOR_URL (y MONGO_URI)
set -a && source .env && set +a
```

| Variable | Default | Notas |
|----------|---------|--------|
| `HTTP_ADDR` | `:8080` | |
| `MONGO_URI` | required | |
| `MONGO_DB_NAME` | `roxy` | |
| `EVALUATOR_URL` | required | `POST` JSON del contrato evaluator |
| `ANTHROPIC_API_KEY` | required | planner: forma el HTTP del MCP |
| `ANTHROPIC_MODEL` | `claude-sonnet-5` | |
| `ANTHROPIC_BASE_URL` | `https://api.anthropic.com` | |
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

Si el evaluator corre en `:8080`, levanta Roxy en otro puerto (`HTTP_ADDR=:3000`).

Deny (403 vacío):

```bash
curl -i -X POST localhost:8080/v1/evaluate \
  -H 'Content-Type: application/json' \
  -d '{"mcpName":"mongo-catalog-mcp","accessedBy":"agent-subtask-07","action":"drop_table","payload":{"intent":"DROP TABLE orders"}}'
```

Allow (body = respuesta cruda del MCP):

```bash
curl -i -X POST localhost:8080/v1/evaluate \
  -H 'Content-Type: application/json' \
  -d '{"mcpName":"inventory-mcp","accessedBy":"agent-orchestrator-01","action":"read","payload":{"intent":"read stock levels"}}'
```

Allow y deny dejan un documento en `roxy.security` y un POST al dashboard.
