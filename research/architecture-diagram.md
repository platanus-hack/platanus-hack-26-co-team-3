# Diagrama de arquitectura general

Reconstruido del estado actual del código en `main` (no de `idea.md` a
secas — varias piezas ya avanzaron más de lo que el checklist refleja).
Se itera a medida que entre más información al `idea.md`.

## Componentes y flujo de datos

```mermaid
flowchart TB
    subgraph agents["Bloque 5 — agent-flow-demo (Andrés, no iniciado)"]
        orch["Orquestador"]
        subOk["Sub-agente legítimo"]
        subBad["Sub-agente con inyección nociva"]
        orch --> subOk
        orch --> subBad
    end

    subgraph interceptor["Bloque 9 — langchain-interceptor (Santiago, no iniciado)"]
        hook["Callbacks on_chain_start / on_tool_start / on_llm_start"]
    end
    orch -. "traza de nodos (planeado, sin contrato aún)" .-> hook

    subgraph gateway["Bloque 2 — roxy-gateway (Stiven)"]
        rg["POST /v1/evaluate"]
    end
    subOk -->|"mcpName, accessedBy, action, payload"| rg
    subBad -->|"mcpName, accessedBy, action, payload"| rg

    subgraph evaluator["Evaluator API (contrato HTTP: EVALUATOR_URL)"]
        ev["allowed / violatedPriority / reason"]
        z3["Bloque 10 — verifier (Sebastián)\nZ3 determinista — en construcción"]
        ev -. "hoy: pluggable / mañana" .-> z3
    end
    rg -->|"mcp (rules, server, auth) + request + time"| ev
    ev -->|veredicto| rg

    subgraph mongoRoxy["Mongo db `roxy` — Bloque 1 (Santiago)"]
        mcps[("mcps: nombre, server.url,\nauthorization, rules")]
        sec[("security: status, mcp,\ntime, accessedBy, description")]
    end
    rg -->|lee MCP| mcps
    rg -->|log allow/deny| sec

    subgraph dashboard["Bloque 3 — dashboard (Santiago)"]
        dapi["GET /security-logs"]
        front["Frontend React"]
        dapi --> front
    end
    rg -. "POST notify (opcional, DASHBOARD_URL)" .-> front
    sec -->|lee logs| dapi

    rg -->|"allowed:true → POST server.url\ncon credenciales del MCP"| target["MCP objetivo\n(mock: mongo-catalog / payments / inventory)"]
    rg -->|"allowed:false → 403 sin body"| subBad

    subgraph victim["Bloque 4 — demo-api (Freddy, hecho)"]
        api["FastAPI: /invoices,\n/health/consistency, /admin/reset"]
    end
    subgraph mongoBilling["Mongo db `demo_billing`"]
        inv[("invoices")]
    end
    api <--> inv
    subBad -. "ataque directo a Mongo\n(escenario 'sin Roxy', bypassea el gateway)" .-> inv
    target -. "en el escenario real de la demo,\neste MCP apunta a demo_billing" .-> inv

    subgraph runner["Bloque 7 — demo/ (Todos, no iniciado)"]
        run["Orquesta las 3 corridas:\nnormal / agentic sin Roxy / agentic con Roxy"]
    end
    run -.-> agents
    run -.-> api
    run -.-> front
```

## Flujo de una petición (con Roxy)

```mermaid
sequenceDiagram
    participant Agente as Sub-agente
    participant Roxy as roxy-gateway
    participant Eval as Evaluator API
    participant Mongo as Mongo (roxy)
    participant MCP as MCP objetivo

    Agente->>Roxy: POST /v1/evaluate {mcpName, accessedBy, action, payload}
    Roxy->>Mongo: lee mcps.{mcpName} (rules, server, auth)
    Roxy->>Eval: POST {mcp, request, time}
    Eval-->>Roxy: {allowed, violatedPriority, reason}
    Roxy->>Mongo: escribe security (status, mcp, time, accessedBy, description)
    Roxy-->>Dashboard: POST notify (opcional)
    alt allowed = true
        Roxy->>MCP: POST server.url (con credenciales del MCP)
        MCP-->>Roxy: respuesta cruda
        Roxy-->>Agente: respuesta cruda del MCP
    else allowed = false
        Roxy-->>Agente: 403 (sin body)
    end
```

## Los 3 escenarios del demo (Bloque 7)

```mermaid
flowchart LR
    r1["1. API normal\ndemo-api solo, sin agentes"] --> c1["/health/consistency → 200"]
    r2["2. Flujo agéntico\nSIN Roxy"] --> c2["ataque directo a Mongo\n/health/consistency → 409"]
    r3["3. Flujo agéntico\nCON Roxy"] --> c3["Roxy evalúa cada acción\n/health/consistency → 200"]
```

## Notas de estado (para no perder contexto al iterar)

- **Roxy Gateway ya no evalúa reglas él mismo.** Desde el merge más
  reciente, delega 100% la decisión a un **Evaluator API** externo vía
  `EVALUATOR_URL` (contrato HTTP: recibe `mcp + request + time`, responde
  `allowed/violatedPriority/reason`). El código LLM que tenía antes
  (OpenRouter, luego Claude Sonnet 5) se eliminó de `roxy-gateway/` — hoy
  el evaluator es un componente pluggable separado. **Este es exactamente
  el punto donde entra el Bloque 10 (`verifier/`, Sebastián, Z3
  determinista)** — aún no tiene código, solo la carpeta registrada en
  `CLAUDE.md`.
- **Roxy Gateway ahora sí llama al MCP real** (antes solo evaluaba y
  logueaba) — si el evaluator aprueba, hace el POST real a `server.url`
  con las credenciales del MCP, y devuelve la respuesta cruda al agente.
- Los 3 MCPs del mock (`mongo-catalog-mcp`, `payments-mcp`,
  `inventory-mcp`, en `mongo-data/population/mcps.mock.json`) apuntan a
  URLs ficticias (`https://mcp.internal/...`) — todavía no hay un MCP real
  registrado apuntando a `demo_billing`. Eso lo tiene que crear quien
  conecte el Bloque 5 (agent-flow-demo) al Bloque 2.
- **Bloques sin código aún:** `agent-flow-demo/` (5), `langchain-
  interceptor/` (9), `demo/` (7), `verifier/` (10), `landing-page/` (8).
  El diagrama de arriba ya anticipa su forma según lo que describe
  `idea.md`, pero se ajusta apenas suban algo real — por eso este doc
  vive en `research/`, para iterar rápido sin tocar código de ningún
  bloque.
- La notificación de Roxy al dashboard (`DASHBOARD_URL`) es opcional —
  si no está configurada, es no-op. El dashboard hoy solo expone `GET
  /security-logs` leyendo Mongo directo; no confirmé un endpoint que
  reciba ese POST de notificación.
