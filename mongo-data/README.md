# mongo-data

Block 1 (idea.md): Mongo schema and mock data for Roxy — database `roxy`,
collections `mcps` and `security`.

## Contents

- [schema.json](schema.json) — `$jsonSchema` validators and indexes for both
  collections, meant to be consumed by an init script (not imperative code).
- [docker-compose.yml](docker-compose.yml) — runs a local MongoDB 7 instance
  on `mongodb://localhost:27017`, no auth, data persisted in the
  `roxy-mongo-data` volume.
- [population/](population/) — mock documents (`mcps.mock.json`,
  `security.mock.json`) and `populate.py`, a pymongo script that inserts them.
- [run.sh](run.sh) — one command that starts Mongo and populates it.

## Quick start

```bash
./run.sh
```

This will:

1. Start the local MongoDB container (`docker compose up -d`) and wait until
   it responds to a ping.
2. Create `population/.env` from `population/.env-example` if it doesn't
   exist yet.
3. Create a Python virtualenv (`.venv`) and install
   `population/requirements.txt`.
4. Run `population/populate.py`, which clears and re-inserts the mock `mcps`
   and `security` documents.

Requires Docker (with Compose v2) and Python 3 available on `PATH`.

## Manual steps

If you'd rather run things yourself instead of `run.sh`:

```bash
docker compose up -d
cp population/.env-example population/.env   # edit if your Mongo isn't local
python3 -m venv .venv && source .venv/bin/activate
pip install -r population/requirements.txt
python3 population/populate.py
```

## Connecting

- Connection string: `mongodb://localhost:27017`
- Database: `roxy`
- Collections: `mcps`, `security`

## Stopping / resetting

```bash
docker compose down        # stop the container, keep data
docker compose down -v     # stop the container and wipe the volume
```
