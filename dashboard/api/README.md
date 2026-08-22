# dashboard

Block 3 (idea.md): FastAPI API backing the dashboard.

## Run

From within this directory:

```bash
pip install -r requirements.txt
cp .env.example .env   # edit if your Mongo isn't local
uvicorn main:app --reload
```

Requires a MongoDB instance with database `roxy` and collection `security`
reachable at `MONGO_URI` (see `mongo-data/` for a local instance and mock
data — not a dependency of this block, just how to get sample data).

### With Docker

```bash
docker build -t roxy-dashboard-api .
docker run --rm -p 8000:8000 -e MONGO_URI=mongodb://host.docker.internal:27017 roxy-dashboard-api
```

`MONGO_URI` must point somewhere the container can reach — `localhost` inside
the container is the container itself, not your host. On Docker Desktop
(Mac/Windows), `host.docker.internal` reaches a Mongo running on your host
(e.g. via `mongo-data/`'s `docker-compose.yml`); on Linux, use the host's
LAN/bridge IP or put both containers on the same Docker network.

## Endpoints

### `GET /security-logs`

Queries the `security` collection and returns matching logs, each validated
against a Pydantic model.

Query params (all optional):

- `status` — `approved` or `denied`
- `mcpId` — filter by referenced MCP's ObjectId
- `accessedBy` — filter by accessing agent identifier
- `limit` — max results (default 50, max 500)
- `skip` — pagination offset (default 0)

Results are sorted by `time` descending.
