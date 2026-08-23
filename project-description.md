# Roxy — el agente de seguridad entre tus agentes y tus MCPs

**Track:** AI Security · **Equipo:** team-3 (Bogotá)

[Dashboard](https://roxygt.lat)

---

## El problema

A2A empuja workflows enteramente agénticos: un orquestador delega, un subagente ejecuta, y el MCP del otro lado no pregunta *por qué*.

La seguridad de esa cadena cuelga de un único punto de confianza inicial. Si conectas datos sensibles (órdenes, pagos, inventario) a MCPs, un agente delegado puede correr acciones que nadie autorizó: un `DROP` sobre `orders`, un ajuste masivo de stock, un refund fuera de rol. El orquestador no se entera hasta que el daño ya está en la base.

---

## La solución

**Roxy se pone delante del MCP.** Carga las reglas, evalúa la intención con un LLM y decide. El agente que llama no tiene que conocer la capa de seguridad.

- **Allow:** inyecta credenciales, pega al MCP y devuelve la respuesta cruda.
- **Deny:** corta el acceso (403) y explica la regla violada.
- **Audit trail:** cada decisión escribe quién, qué MCP, cuándo y por qué. El dashboard muestra logs y alertas.

Las credenciales nunca vuelven al agente.

---

## Cómo funciona

1. El agente llama a Roxy con `mcpName`, `accessedBy`, `action` y `payload`.
2. El gateway carga el MCP y sus `rules` desde Mongo.
3. Un evaluador LLM compara la acción con las instrucciones — **sin credenciales**.
4. Si niega, no hay llamada al MCP. Si aprueba, un planner (Sonnet) arma el HTTP y Roxy inyecta el auth.
5. Se escribe el log de seguridad y se notifica al dashboard (fail-open).

```
Agente  →  Roxy Gateway  →  Evaluator (rules + prompt)
                 │                │
                 │         allow / deny
                 │
            allow → MCP (credenciales inyectadas)
            deny  → 403 + log
                 │
                 └──► Mongo (security logs) → Dashboard
```

---

## La demo: la misma API, tres momentos

1. **API normal** — catálogo, pagos e inventario responden como se espera.
2. **Agentes sin Roxy** — el orquestador lanza subagentes; operaciones indebidas (DROP, bulk stock, refunds fuera de rol) pasan.
3. **Agentes con Roxy** — las mismas acciones se evalúan. Lo destructivo se niega. Queda el log y la alerta.

---

## Stack

- **Gateway:** Go (`POST /v1/evaluate`)
- **Datos:** Mongo (`mcps` + `security`)
- **Evaluador:** API LLM (intención vs reglas)
- **Planner:** Sonnet 5 (solo si hay allow)
- **Dashboard:** alertas y logs en [roxygt.lat](https://roxygt.lat)
- **Demo:** API funcional + flujo LangChain de orquestador y subagentes

---

## Equipo

- Santiago Melo ([@santiagoMeloMedina](https://github.com/santiagoMeloMedina)) — datos Mongo, dashboard, interceptor
- Andres Esteban Rodriguez Avila ([@andss-ye](https://github.com/andss-ye)) — flujo de agentes
- Freddy Johan Bautista Baquero ([@freddyb200](https://github.com/freddyb200)) — demo API, research, landing
- John Stiven Valeriano ([@stvgo](https://github.com/stvgo)) — Roxy Gateway
