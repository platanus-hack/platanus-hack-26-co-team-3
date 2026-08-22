# dashboard/app

Block 3 (idea.md): frontend for the Roxy dashboard. Vite + React + TypeScript.

## Run

```bash
npm install
cp .env.example .env   # defaults to the deployed API (roxygt.lat); point VITE_API_URL
                        # at http://localhost:8000 instead if running the API locally
npm run dev
```

Requires the [dashboard API](../api) reachable at `VITE_API_URL` (defaults to
`https://roxygt.lat/api`, the deployed API through CloudFront).

## Screens

- **Overview** — request counts, active alerts (denied requests, prioritized),
  and a recent-activity feed.
- **Logs** — full log list with status and MCP filters, showing every field
  from the `security` collection.

Clicking any log opens a detail drawer with the full record.
