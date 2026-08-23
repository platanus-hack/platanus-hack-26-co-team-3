# roxy-gateway

API **roxy**: capa de seguridad entre agentes y MCPs. V1 no evalúa rules: llama a un **evaluator API**, y según el veredicto pega al MCP o corta el acceso.

## Qué hace

`POST /v1/evaluate` → carga el MCP por `mcpName` → POST al evaluator (`EVALUATOR_URL`) con `rules` (solo el texto) + `prompt` del agente, **sin credenciales** → log + dashboard →

- evaluator `allowed: false` → **403** sin body (no llama al MCP)
- evaluator `allowed: true` → **Sonnet 5** decide endpoint/método/body y llama al MCP vía tool `http_request` (Roxy solo ejecuta el HTTP e inyecta credenciales). Devuelve la **respuesta cruda del MCP**
- evaluator caído → **503**
- el modelo no llega a llamar al MCP → **503** `planner unavailable`
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

Las credenciales **no** se devuelven al agente: Roxy las usa para pegarle al MCP.

`authorization.type=oauth2`: Roxy hace `POST https://cloud.mongodb.com/api/oauth/token` (`grant_type=client_credentials`) y usa el `access_token` como Bearer. `credentials` es `clientId:clientSecret` (o JSON `{clientId,clientSecret,tokenURL}`). MCP hospedado: `server.url=https://roxygt.lat/mcp`, protocol `mcp` (ese MCP le pega a Atlas).

### Contrato hacia el dashboard

Si `DASHBOARD_URL` está set (base, p.ej. `https://roxygt.lat/api`), Roxy hace `POST {base}/log` en allow y deny. Fail-open: si el dashboard falla, el evaluate sigue.

Deny:

```json
{
  "status": "denied",
  "mcpName": "mongo-catalog-mcp",
  "mcpId": "6a89974fe413c1e675df5b82",
  "accessedBy": "agent-subtask-07",
  "action": "drop_table",
  "violatedRule": {
    "priority": 1,
    "instruction": "deny any write operation outside working hours"
  },
  "description": "Dropping a table is a write/destructive operation, denied by priority 1 rule.",
  "time": "2026-08-22T12:00:00Z"
}
```

Allow: mismo shape, `status` = `"approved"`, **sin** `violatedRule` (`omitempty`). Sin secretos.

### Contrato hacia el evaluator

Roxy hace `POST` a `EVALUATOR_URL` con este JSON (nada más):

```json
{
  "rules": [
    "deny any write operation outside working hours",
    "allow read-only queries on the 'orders' collection"
  ],
  "prompt": "drop_table: DROP TABLE orders"
}
```

| Campo | Qué es |
|--------|--------|
| `rules` | Array de strings: las `instruction` del MCP, en el orden de Mongo. **Sin `priority`.** |
| `prompt` | Lo que pidió el agente. Si `payload.prompt` existe, se usa tal cual. Si no, `action` + `payload.intent` (o el payload crudo). |

No se envían `id`, `name`, `description`, `accessedBy`, `time` ni credenciales.

El evaluator responde `allowed`, `violatedPriority`, `reason` (lo que usa Roxy). `violatedPriority` se interpreta como prioridad Mongo o, si no hay match, como índice 1-based del array enviado. `attributes` y `governingRule` son transparencia del evaluator; Roxy no los exige.

## Requisitos

- Go 1.22+
- Mongo en `mongodb://localhost:27017`, database `roxy` (el bloque `mongo-data` lo levanta con `./run.sh`)
- `EVALUATOR_URL` (API de veredicto)
- `ANTHROPIC_API_KEY` (Sonnet llama al MCP con tool HTTP)

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
| `MONGO_URI` | required | Local: `mongodb://localhost:27017`. Prod: host interno de la misma red, **sin token** (`mongodb://mongo:27017`) |
| `MONGO_DB_NAME` | `roxy` | |
| `EVALUATOR_URL` | required | `POST` JSON del contrato evaluator |
| `ANTHROPIC_API_KEY` | required | Sonnet llama al MCP (tool HTTP) |
| `ANTHROPIC_MODEL` | `claude-sonnet-5` | |
| `ANTHROPIC_BASE_URL` | `https://api.anthropic.com` | |
| `DASHBOARD_URL` | vacío = no-op | Base del dashboard (`https://roxygt.lat/api`). Roxy hace `POST {base}/log` en allow y deny |

## Tests

```bash
go test ./...
```

## Docker

```bash
docker build -t roxy-gateway .
docker run --rm -p 8080:8080 --env-file .env -e HTTP_ADDR=:8080 roxy-gateway
```

Producción (Docker, Mongo en la misma red): ver [DEPLOY.md](DEPLOY.md).

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
