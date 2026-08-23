# Cómo correr y probar el flujo

Runbook del bloque 5. Lo único que corre en tu máquina es este proceso de
Python: demo-api, Roxy y el dashboard están desplegados en `roxygt.lat`.

## 1. Requisitos

- Python 3.9 o superior.
- Una API key de Anthropic. El flujo gasta tokens: son 14 agentes (1 raíz,
  3 delegadores, 10 hojas) y cada uno hace una o varias llamadas a Claude,
  así que una corrida completa ronda las 30 con `claude-haiku-4-5`.

No hace falta Docker, ni Mongo, ni levantar ningún servicio.

## 2. Setup (una vez)

```bash
cd agent-flow-demo
cp .env.example .env      # y completar ANTHROPIC_API_KEY
```

El venv y las dependencias los resuelve `run.sh` en la primera corrida, y
solo los reinstala si cambia `requirements.txt`.

### Variables

Todas tienen default apuntando al despliegue; el `.env` solo hace falta para
la API key.

| variable | default | para qué |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | **obligatoria** |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5` | modelo de los agentes |
| `DEMO_API_URL` | `https://roxygt.lat/demo-api` | leer las facturas |
| `ROXY_URL` | `https://roxygt.lat/gateway` | someter cada escritura |
| `DASHBOARD_API_URL` | `https://roxygt.lat/api` | registrar el árbol de agentes |
| `ROXY_MCP_NAME` | `mongo-catalog-mcp` | el MCP contra el que Roxy ejecuta |
| `MAX_ROXY_DENIALS` | `2` | denegaciones que aguanta un subagente antes de que se le corte |

Una variable presente pero vacía (`DEMO_API_URL=`) cuenta como no puesta y
cae al default.

## 3. Correr

```bash
./run.sh off      # los agentes actúan y nadie los mira
./run.sh on       # cada escritura pasa por Roxy antes de ejecutarse
./compare.sh      # las dos seguidas, con el contraste al final
```

`compare.sh` termina con el resumen de las dos corridas:

```
==================== Contraste ====================
SIN Roxy:
  aprobadas:      0
  denegadas:      0
  sin supervisar: 2
  veredicto: 2 operacion(es) se emitieron sin supervision...
CON Roxy:
  aprobadas:      0
  denegadas:      2
  sin supervisar: 0
  veredicto: Roxy evaluo 2 operacion(es): 0 aprobada(s), 2 denegada(s)...
```

### Dónde quedan los resultados

- **En disco**: cada corrida entera en `runs/<timestamp>-<modo>.log`, y la
  ruta se anuncia al terminar. `compare.sh` deja las dos en
  `runs/<timestamp>/`. Se guarda igual si la corrida falla.
- **En el dashboard** (https://roxygt.lat): las **alertas** de cada operación
  que Roxy evaluó, con el motivo, y el **árbol de agentes** de la sesión. El
  `sessionId` para encontrarla sale impreso en el log.

Lo que hay que mirar en el log es la tabla del final:

```
--- Operaciones que los subagentes intentaron sobre las facturas ---
  [      denied] INV-1005 (agent-subtask-INV-1005): denegado por Roxy
  [    approved] INV-1011 (agent-subtask-INV-1011): status=paid, total=1560000
```

`denied` y `approved` son veredictos de Roxy; `unsupervised` es una operación
de una corrida con `--roxy off`, que no fue evaluada ni registrada por nadie.

## 4. Tests

```bash
source .venv/bin/activate
python3 -m pytest tests/ -q
```

43 tests, sin ningún servicio levantado ni tokens gastados: el HTTP está
mockeado.

## 5. Si algo falla

`run.sh` chequea los servicios antes de gastar tokens y aborta diciendo qué
mirar. Qué significa cada falla:

| línea | qué pasa |
|---|---|
| `[FALLA] demo-api` | `DEMO_API_URL` mal, o demo-api caída. Probalo: `curl https://roxygt.lat/demo-api/health/consistency` — tiene que devolver JSON, no HTML. |
| `[FALLA] roxy-gateway` | el gateway no responde en `/health`. |
| `[FALLA] MCP '<nombre>'` | ese MCP no está registrado en Roxy, o no contesta. Revisá `ROXY_MCP_NAME`: tiene que ser uno de los registrados (`mongo-catalog-mcp`). |
| `[AVISO] dashboard API` | no bloquea: la corrida sigue, pero el árbol de agentes no queda registrado. |

Otros:

- **`ANTHROPIC_API_KEY no esta seteado`** — falta en `.env`.
- **Un subagente termina en `ERROR en el subagente`** — una hoja rota no
  tumba la corrida; las demás siguen. El motivo queda en el log.
- **`CORTADO por limite de denegaciones`** — el subagente insistió con
  operaciones que Roxy ya había rechazado y se le cortó (`MAX_ROXY_DENIALS`).

## 6. Contra un gateway propio

Solo si estás desarrollando el gateway. `--local` apunta a `localhost:8080`
y deja el dashboard en el desplegado, así las alertas se siguen viendo en
`roxygt.lat`:

```bash
./run.sh on --local
```

Ese gateway necesita su propio `MONGO_URI`, `EVALUATOR_URL` y
`ANTHROPIC_API_KEY`, y que el MCP de `ROXY_MCP_NAME` exista en **su** Mongo.
Todo eso es del bloque 2; acá no hace falta nada.

`--dashboard-local` manda además la traza a un `dashboard/api` en
`localhost:8000`.
