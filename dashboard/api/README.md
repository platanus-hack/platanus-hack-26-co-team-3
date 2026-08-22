# dashboard

Block 3 (idea.md): FastAPI API backing the dashboard.

## Run

```bash
pip install -r requirements.txt
cp .env.example .env   # edit if your Mongo isn't local
uvicorn api.main:app --reload
```

Requires a MongoDB instance with database `roxy` and collection `security`
reachable at `MONGO_URI` (see `mongo-data/` for a local instance and mock
data — not a dependency of this block, just how to get sample data).

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
