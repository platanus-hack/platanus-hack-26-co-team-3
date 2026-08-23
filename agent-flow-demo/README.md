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
./run.sh on --local       # contra un gateway propio en localhost:8080
```

`compare.sh` corre las dos y contrasta:

```bash
./compare.sh
```

Deja los logs en `runs/<timestamp>/` y termina con el resumen: cuántas
operaciones se aprobaron, cuántas se denegaron y cuántas pasaron sin que
nadie las viera.

## Tests

```bash
python3 -m pytest tests/ -q
```

31 tests, sin ningún servicio levantado (HTTP mockeado). Cubren la traducción
de la respuesta de Roxy a permiso/negación, el corte por denegaciones, el
registro de operaciones, el reparto recursivo de facturas y la reconstrucción
del árbol de delegación.

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
- `agent_flow/preflight.py` — el chequeo previo de los tres servicios.
- La trazabilidad y el control de acceso salen del SDK (`roxy-sdk/`,
  publicado como `roxy-guard`): una instancia de `Roxy` se pasa como callback
  y registra el árbol en `/agents` sola.

## Límite conocido

Para que una operación aprobada llegue a modificar datos de verdad, el MCP
que Roxy tiene registrado (`invoices-mcp`) tiene que exponer esa escritura y
ser alcanzable desde el gateway. Mientras el MCP apunte a una API de solo
lectura, Roxy aprueba y la llamada que ejecuta no cambia nada: lo que la
corrida demuestra es la delegación, el veredicto y la traza, no la corrupción
del dato. Registrar ese MCP es del bloque 2, no de acá.
