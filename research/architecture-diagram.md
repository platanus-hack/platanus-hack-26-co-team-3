# Diagrama de arquitectura general

Reconstruido leyendo el código real en `main` y **probando los servicios
desplegados en vivo** (2026-08-23, 01:00). No es lo que dice `idea.md` ni
lo que dicen los README — es lo que efectivamente corre.

---

## 1. Diagrama para el tablero / deck (el que se muestra hablando)

Este es el que hay que dibujar. Todo lo demás es detalle técnico que no
va en la slide principal.

```mermaid
flowchart LR
    A["Agente<br/>(delegado, no confiable)"]
    R{"ROXY<br/>Gateway"}
    V["Verificador<br/>decide"]
    M[("El dato<br/>facturación")]
    D["Dashboard<br/>lo ve todo"]

    A -->|"quiere escribir"| R
    R -->|"¿esta acción viola<br/>alguna regla?"| V
    V -->|"veredicto"| R
    R -->|"aprobado"| M
    R -.->|"denegado ✕"| A
    R ==>|"queda registrado"| D

    style R fill:#aa3bff,stroke:#aa3bff,color:#fff
    style V fill:#1c1d24,stroke:#aa3bff,color:#fff
    style D fill:#1c1d24,stroke:#16a34a,color:#fff
```

**El mensaje, sin decir una palabra técnica:** hay un punto único, en el
medio, que ve *todo* antes de que le llegue al dato — y nada pasa por ahí
sin quedar registrado.

---

## 2. Diagrama técnico — Z3 / Solana (la slide de ~8 segundos)

```mermaid
flowchart TD
    NL["Regla escrita en español<br/>'no cerrar como pagada sin registro'"]
    C["El LLM la traduce<br/>UNA sola vez"]
    P["Política formal<br/>congelada + hasheada"]
    E["Motor determinista<br/>0 LLM en la decisión"]
    Z["Z3: prueba matemática<br/>de la invariante"]
    S["Solana<br/>veredicto anclado on-chain"]

    NL --> C --> P --> E
    E -.->|"opcional"| Z
    E --> S

    style P fill:#1c1d24,stroke:#aa3bff,color:#fff
    style E fill:#aa3bff,stroke:#aa3bff,color:#fff
    style S fill:#1c1d24,stroke:#16a34a,color:#fff
```

**La frase:** el LLM traduce la regla una vez; la decisión corre siempre
determinista sobre esa política ya congelada — mismo input, mismo
resultado, siempre. Y cada veredicto queda anclado en Solana: nadie,
ni nosotros, puede reescribir después lo que pasó.

---

## 3. Los 3 escenarios de la demo

```mermaid
flowchart LR
    subgraph s1["1 · Estado normal"]
        a1["demo-api"] --> b1["✓ consistente"]
    end
    subgraph s2["2 · Agentes SIN Roxy"]
        a2["nota maliciosa<br/>en el portal"] --> b2["el agente obedece"] --> c2["✕ dato corrompido"]
    end
    subgraph s3["3 · Agentes CON Roxy"]
        a3["misma nota maliciosa"] --> b3["Roxy evalúa"] --> c3["✓ bloqueado, dato intacto"]
    end

    style b1 fill:#16a34a,color:#fff
    style c2 fill:#dc2626,color:#fff
    style c3 fill:#16a34a,color:#fff
```

---

## 4. Flujo real completo (referencia técnica, NO para slide)

```mermaid
flowchart TB
    subgraph flow["agent-flow-demo · Bloque 5 (Andrés)"]
        orch["Orquestador LangChain"]
        sub["Subagentes<br/>uno por factura"]
        portal["customer_portal.py<br/>portal de proveedores falso<br/>← entra la nota maliciosa"]
        orch --> sub
        portal -.->|"read_customer_notes"| sub
    end

    subgraph sdkbox["roxy-sdk (Python)"]
        cb["Roxy(BaseCallbackHandler)<br/>registra el árbol solo"]
        guard["guard() — somete la escritura"]
    end
    orch -.->|"callback"| cb
    sub --> guard

    subgraph gw["roxy-gateway · Bloque 2 (Stiven) — Go"]
        ev["POST /v1/evaluate"]
        planner["Claude Sonnet 5<br/>planea la llamada al MCP"]
    end
    guard -->|"mcpName, accessedBy,<br/>action, payload"| ev

    subgraph verif["Verificador · Bloque 10"]
        rust["engine/ (Rust, Sebastián)<br/>habla {rules, prompt} ✓"]
        py["evaluator.py (Python, Andrés)<br/>habla {mcp, request, time} ✗"]
    end
    ev -->|"{rules, prompt}"| rust
    ev -.->|"INCOMPATIBLE hoy"| py

    subgraph mongo["Mongo roxy · Bloque 1"]
        mcps[("mcps<br/>reglas en lenguaje natural")]
        sec[("security<br/>cada decisión")]
        ag[("agents<br/>árbol de delegación")]
    end
    ev --> mcps
    ev -->|"escribe directo"| sec
    cb -->|"POST /agents"| ag

    subgraph dash["dashboard · Bloque 3 (Freddy)"]
        dapi["/log · /agents · /sessions"]
        ui["Overview · Logs · Agents"]
        dapi --> ui
    end
    ev -.->|"POST /log — ⚠ segunda escritura"| dapi
    sec --> dapi
    ag --> dapi

    subgraph victim["demo-api · Bloque 4 (Freddy)"]
        api["/invoices · /health/consistency<br/>/admin/reset"]
    end
    planner -->|"aprobado → HTTP real"| api
    ev --> planner
    sub -->|"lee facturas (solo lectura)"| api

    style rust fill:#16a34a,color:#fff
    style py fill:#dc2626,color:#fff
```

---

## Estado verificado en vivo (2026-08-23, 01:00)

Probado con `curl` contra el despliegue real, no asumido:

| servicio | endpoint | estado |
|---|---|---|
| roxy-gateway | `https://roxygt.lat/gateway/health` | ✅ `{"service":"roxy","status":"ok"}` |
| dashboard API | `https://roxygt.lat/api/log` | ✅ devuelve logs reales |
| demo-api | `https://roxygt.lat/demo-api/health/consistency` | ✅ `consistent: true, checked: 30` |
| MCP server | `https://roxygt.lat/mcp` | ✅ responde (pide sesión) |

**La corrida con Roxy ya funcionó de verdad en prod**: hay denegaciones
reales en `security` de las 06:06 UTC de hoy, sobre
`agent-subtask-INV-1005` y `agent-subtask-INV-1011`, con el motivo
`"operation 1 (write on 'invoices') is denied by rule priority 1"`.

## ⚠ Dos problemas encontrados (ver `research/ISSUES.md`)

1. **Contrato del evaluador incompatible** entre `roxy-gateway` y
   `verifier/evaluator.py` — confirmado con una prueba real (422).
2. **Cada decisión se escribe dos veces** en `security` → el dashboard
   muestra todo duplicado.
