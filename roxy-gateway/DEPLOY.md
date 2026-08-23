# Deploy Roxy Gateway

## Mongo (misma red)

En prod Mongo comparte red con Roxy (Docker / red privada). **No hay user, password ni token.**

```
MONGO_URI=mongodb://mongo:27017
MONGO_DB_NAME=roxy
```

`mongo` es el hostname del servicio en esa red; cámbialo por el DNS real si es otro.

Seed contra ese host:

```bash
MONGO_URI='mongodb://mongo:27017' MONGO_DB_NAME=roxy go run ./cmd/seed
```

## Render (Docker)

Repo de deploy: `https://github.com/stvgo/roxy-gateway` (Dockerfile en la raíz).

Dashboard → **New Web Service** → ese repo → **Docker**.

Health check: `/health`. Render inyecta `PORT`; el API lo usa solo.

Environment (los `sync: false` del `render.yaml` hay que pegarlos):

| Key | Valor |
|-----|--------|
| `MONGO_URI` | `mongodb://mongo:27017` (hostname interno, sin credenciales) |
| `MONGO_DB_NAME` | `roxy` |
| `EVALUATOR_URL` | URL del API evaluator (`.../evaluate`) |
| `ANTHROPIC_API_KEY` | Sonnet llama al MCP (tool HTTP) |
| `ANTHROPIC_MODEL` | `claude-sonnet-5` |
| `DASHBOARD_URL` | opcional, base del API (`https://roxygt.lat/api` → POST `/log`) |

O Blueprint: **New** → **Blueprint** → `render.yaml`.

## Docker local

```bash
docker build -t roxy-gateway .
docker run --rm -p 8080:8080 --env-file .env -e HTTP_ADDR=:8080 roxy-gateway
```
