# Deploy Roxy Gateway (Render + MongoDB Atlas)

## Mongo en la nube: Atlas M0 (gratis)

Render no ofrece Mongo. El servicio que encaja con este mock (pocos docs, demo) es **MongoDB Atlas Free (M0)**: 512 MB, no expira, `mongodb+srv`.

1. Crea cuenta/cluster: https://cloud.mongodb.com → **Create** → **M0 Free**.
2. Cloud: **AWS**, región cerca de Render (Oregon `us-west-2` si el API está en Oregon).
3. Database user:
   - user: `roxy_prod`
   - password: el de `.env.production` (generado local, no se commitea)
4. Network Access → **Allow Access from Anywhere** (`0.0.0.0/0`) para el hack/demo. En serio, para prod real usa las outbound IPs de Render.
5. Connect → Drivers → copia el URI y reemplaza password + database `roxy`:

```
mongodb+srv://roxy_prod:<PASSWORD>@<cluster>.mongodb.net/roxy?retryWrites=true&w=majority
```

6. Carga el mock (desde esta carpeta, con el URI de Atlas):

```bash
MONGO_URI='mongodb+srv://...' MONGO_DB_NAME=roxy go run ./cmd/seed
```

## Render (Docker)

Repo de deploy: `https://github.com/stvgo/roxy-gateway` (Dockerfile en la raíz).

Dashboard → **New Web Service** → ese repo → **Docker**.

Health check: `/health`. Render inyecta `PORT`; el API lo usa solo.

Environment (los `sync: false` del `render.yaml` hay que pegarlos):

| Key | Valor |
|-----|--------|
| `MONGO_URI` | URI `mongodb+srv` de Atlas (database `roxy`) |
| `MONGO_DB_NAME` | `roxy` |
| `EVALUATOR_URL` | URL del API evaluator (`.../evaluate`) |
| `ANTHROPIC_API_KEY` | Sonnet llama al MCP (tool HTTP) |
| `ANTHROPIC_MODEL` | `claude-sonnet-5` |
| `DASHBOARD_URL` | opcional |

O Blueprint: **New** → **Blueprint** → `render.yaml`.

## Docker local

```bash
docker build -t roxy-gateway .
docker run --rm -p 8080:8080 --env-file .env -e HTTP_ADDR=:8080 roxy-gateway
```
