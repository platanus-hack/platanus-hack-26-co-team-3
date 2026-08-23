# agent-flow-demo

Bloque 5 (idea.md): orquestador + subagentes de LangChain que concilian
facturas, con o sin Roxy en el camino.

El bloque no depende de nada levantado en tu máquina: no abre bases de datos
ni comparte código con otros bloques. Habla con tres servicios, por HTTP, y
los defaults ya apuntan al despliegue:

| variable | default | para qué |
|---|---|---|
| `DEMO_API_URL` | `https://roxygt.lat/demo-api` | leer las facturas (solo lectura) |
| `ROXY_URL` | `https://roxygt.lat/gateway` | someter cada escritura al veredicto |
| `DASHBOARD_API_URL` | `https://roxygt.lat/api` | registrar el árbol de agentes |
| `ROXY_MCP_NAME` | `mongo-catalog-mcp` | el MCP contra el que Roxy ejecuta |

`mongo-catalog-mcp` es uno de los MCPs que ya vienen registrados en Roxy, y
detrás tiene un MCP de MongoDB real sobre la misma colección `invoices` que
sirve demo-api. Por eso una operación aprobada la ejecuta Roxy de verdad.

## Setup

```bash
cd agent-flow-demo
cp .env.example .env   # completar ANTHROPIC_API_KEY
```

`run.sh` se encarga del venv y de las dependencias en la primera corrida.

## Correr

```bash
./run.sh off              # sin Roxy: nadie evalúa ni registra lo que se intenta
./run.sh on               # con Roxy: cada operación se evalúa y queda en el dashboard
```

No hay nada que levantar: lo único local es este proceso. `--local` existe
por si alguien corre su propio gateway en `:8080`.

## Dónde quedan los resultados

Cada corrida se guarda entera en `runs/<timestamp>-<modo>.log`, y la ruta se
anuncia al terminar. Ahí está el chequeo previo, lo que decidió cada
subagente, el árbol de delegación y la tabla de operaciones con su desenlace
(`approved` / `denied` / `unsupervised`).

En el dashboard (https://roxygt.lat) quedan las otras dos mitades: las
**alertas** de cada operación que Roxy evaluó, con su motivo, y el **árbol de
agentes** de la sesión — el `sessionId` para encontrarla sale impreso en el
log.

`compare.sh` corre las dos y contrasta:

```bash
./compare.sh
```

Deja las dos corridas en `runs/<timestamp>/` y termina con el resumen:
cuántas operaciones se aprobaron, cuántas se denegaron y cuántas pasaron sin
que nadie las viera.

## Tests

```bash
python3 -m pytest tests/ -q
```

43 tests, sin ningún servicio levantado (HTTP mockeado). Cubren la traducción
de la respuesta del gateway a permiso/negación —incluidos los dos casos raros
del despliegue—, el corte por denegaciones, el registro de operaciones, el
reparto recursivo de facturas y la reconstrucción del árbol de delegación.

## Chequeo previo

`run_demo.py` verifica `demo-api`, el dashboard y (con `--roxy on`) el
gateway antes de gastar tokens, y aborta diciendo qué URL revisar en vez de
un traceback.

## Estructura

- `agent_flow/orchestrator.py` — el orquestador (un LLM que reparte facturas
  entre subagentes, que a su vez pueden volver a repartir) y los subagentes
  (`AgentExecutor` con los tools de abajo).
- `agent_flow/invoice_tools.py` — los tools de un subagente: `read_invoice` y
  `read_customer_notes` para leer, `update_invoice` para escribir. La
  escritura **no se ejecuta acá**: se somete a Roxy, que es quien la lleva al
  MCP cuando aprueba. Con Roxy apagada la operación se emite y no queda
  registro en ninguna parte.
- `agent_flow/customer_portal.py` — el portal de proveedores: las notas que
  el cliente dejó adjuntas. Es la superficie por la que entra la instrucción
  maliciosa (INV-1005 empuja a cerrar la factura sin auditoría y con el total
  en 0; INV-1011 es un pago legítimo). Vive en este bloque a propósito, para
  no inyectar nada en la base de nadie.
- `agent_flow/gateway.py` — el cliente del gateway. Existe porque el
  despliegue rompe dos supuestos del SDK: CloudFront convierte el 403 de una
  denegación en un 200 con el HTML del dashboard, y el MCP de Mongo responde
  por `text/event-stream`, no por JSON.
- `agent_flow/preflight.py` — el chequeo previo. Con `--roxy on` somete
  además una lectura inofensiva al MCP: es lo único que separa "lo denegaron"
  de "ese MCP no está registrado", porque los dos llegan como el mismo HTML.
- La trazabilidad y el control de acceso salen del SDK (`roxy-sdk/`,
  publicado como `roxy-guard`): una instancia de `Roxy` se pasa como callback
  y registra el árbol en `/agents` sola.

## Límite conocido

Las reglas de `mongo-catalog-mcp` son las que vinieron con el MCP, y la
primera es *deny any write operation outside working hours*. Fuera de horario
Roxy deniega **toda** escritura, la maliciosa y la legítima, y el contraste
se ve igual (nada se modificó, todo quedó registrado) pero por ese motivo y
no por los invariantes de la factura. Afinar esas reglas es del bloque 2.
