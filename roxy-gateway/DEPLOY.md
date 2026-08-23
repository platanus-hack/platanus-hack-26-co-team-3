# Deploy Roxy Gateway

Imagen Docker. El runtime no está atado a un proveedor: el mismo `Dockerfile` corre en cualquier host con Docker.

## Mongo (misma red)

Mongo comparte red con Roxy. **No hay user, password ni token.**

```
MONGO_URI=mongodb://mongo:27017
MONGO_DB_NAME=roxy
```

`mongo` es el hostname del servicio en esa red; cámbialo por el DNS real si es otro.

Seed contra ese host:

```bash
MONGO_URI='mongodb://mongo:27017' MONGO_DB_NAME=roxy go run ./cmd/seed
```

## Docker

```bash
docker build -t roxy-gateway .
docker run --rm --network <red-interna> -p 8080:8080 --env-file .env.production roxy-gateway
```

Health: `GET /health`.

Escucha `HTTP_ADDR` (default `:8080`). Si el orquestador inyecta `PORT`, esa gana.

## Environment

| Key | Valor |
|-----|--------|
| `MONGO_URI` | `mongodb://mongo:27017` (hostname interno, sin credenciales) |
| `MONGO_DB_NAME` | `roxy` |
| `EVALUATOR_URL` | URL del API evaluator (`.../evaluate`) |
| `ANTHROPIC_API_KEY` | Sonnet llama al MCP (tool HTTP) |
| `ANTHROPIC_MODEL` | `claude-sonnet-5` |
| `DASHBOARD_URL` | opcional, base del API (`https://roxygt.lat/api` → POST `/log`) |
