<img src="./project-logo.png" alt="Roxy" width="130" />

**Platanus Hack 26: Bogotá — Track: AI Security — team-3**

- Santiago Melo ([@santiagoMeloMedina](https://github.com/santiagoMeloMedina))
- Andres Esteban Rodriguez Avila ([@andss-ye](https://github.com/andss-ye))
- Freddy Johan Bautista Baquero ([@freddyb200](https://github.com/freddyb200))
- John Stiven Valeriano ([@stvgo](https://github.com/stvgo))
- Sebastian ([verifier](verifier/))

Dashboard: **<https://roxygt.lat>**

---

# Roxy

**Gateway de seguridad para MCPs.**

Un agente delega en otro, y ese en otro. El que termina escribiendo en la base
está a varios saltos de quien pidió la tarea — y ejecuta con los mismos
permisos que se autorizaron al entrar. Roxy se pone en el medio: carga las
reglas del MCP, somete cada acción sensible a un verificador antes de que se
ejecute, inyecta las credenciales solo si aprueba, y deja registrado cada
intento.

```python
pip install roxy-guard
```

```python
from roxy import Roxy

roxy = Roxy(api_url="https://roxygt.lat/api")
executor.invoke(entrada, config={"callbacks": [roxy]})   # el árbol se registra solo
```

## El recorrido de una petición

```
agente ──▶ roxy-gateway ──▶ verificador ──▶ veredicto
                │                              │
                │◀─────────────────────────────┘
                ├── aprobado → llama al MCP con las credenciales
                └── denegado → 403, la acción nunca ocurre
                        │
                        └──▶ queda en el log, visible en el dashboard
```

La decisión **no la toma un LLM**. Un LLM traduce las reglas escritas en
lenguaje natural a una política formal *una sola vez*; a partir de ahí el
motor decide de forma determinista sobre esa política congelada, y **Z3** la
audita buscando huecos: ¿hay alguna acción destructiva que se cuele por las
reglas escritas? Si la hay, devuelve el contraejemplo concreto. Cada veredicto
se ancla además en Solana (devnet).

## Bloques

| # | Bloque | Carpeta | Qué es |
|---|---|---|---|
| 1 | Datos | [`mongo-data/`](mongo-data/) | Esquema y datos de MCPs, reglas y logs de seguridad |
| 2 | Gateway | [`roxy-gateway/`](roxy-gateway/) | Go. Intercepta agente→MCP, consulta al verificador, ejecuta o corta |
| 3 | Dashboard | [`dashboard/`](dashboard/) | FastAPI + React. Logs, árbol de agentes y la vista en vivo |
| 4 | API víctima | [`demo-api/`](demo-api/) | La API de facturación que se corrompe si nadie vigila |
| 5 | Flujo de agentes | [`agent-flow-demo/`](agent-flow-demo/) | LangChain. Orquestador y subagentes, con y sin Roxy |
| 6 | Investigación | [`research/`](research/) | Incidentes reales, mercado, competencia, arquitectura |
| 8 | Landing | [`landing-page/`](landing-page/) | Página pública del producto |
| 9 | SDK | [`roxy-sdk/`](roxy-sdk/) | `roxy-guard`: registra el árbol de delegación y somete acciones |
| 10 | Verificador | [`verifier/`](verifier/) | Rust + Z3 + atestación en Solana |
| — | Infra | [`infra/`](infra/) | Terraform: todo detrás de un CloudFront |

Cada bloque es autónomo y se comunica con los demás por HTTP o por la base,
nunca importando código de otro. Las reglas están en [CLAUDE.md](CLAUDE.md).

## En producción

Todo corre en **AWS**, detrás de un solo CloudFront — un dominio, sin CORS
entre piezas. Infraestructura como código en [`infra/`](infra/) (Terraform).

| ruta | servicio |
|---|---|
| `/` | Dashboard (S3 + CloudFront) |
| `/api/*` | API del dashboard — logs y árbol de agentes |
| `/gateway/*` | Roxy Gateway |
| `/demo-api/*` | La API víctima |
| `/mcp*` | Servidor MCP |

```bash
cd infra && ./scripts/deploy.sh
```

## Verlo funcionando

```bash
curl https://roxygt.lat/demo-api/health/consistency   # el estado del dato
curl https://roxygt.lat/api/log?limit=20              # cada decisión de Roxy
curl https://roxygt.lat/gateway/health                # el gateway
```

El contraste completo, desde local contra el despliegue:

```bash
cd agent-flow-demo && ./compare.sh
```

Corre el mismo flujo dos veces, sin Roxy y con Roxy, y contrasta qué quedó
escrito en cada caso.

## Estado

Lo que corre en producción y lo que no está en
[`research/ISSUES.md`](research/ISSUES.md), con la evidencia de cada
afirmación. Lo escribimos para nosotros, pero sirve igual para cualquiera que
quiera verificar en vez de creernos.
