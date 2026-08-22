# dashboard/app

Block 3 (idea.md): frontend for the Roxy dashboard. Vite + React + TypeScript.

## Run

```bash
npm install
cp .env.example .env   # edit VITE_API_URL if the dashboard API isn't local
npm run dev
```

Requires the [dashboard API](../api) running and reachable at `VITE_API_URL`
(defaults to `http://localhost:8000`).

## Screens

- **Overview** — request counts, active alerts (denied requests, prioritized),
  and a recent-activity feed.
- **Logs** — full log list with status and MCP filters, showing every field
  from the `security` collection.

Clicking any log opens a detail drawer with the full record.
