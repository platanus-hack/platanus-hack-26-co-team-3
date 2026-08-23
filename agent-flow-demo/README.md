# agent-flow-demo

Bloque 5 (idea.md): el flujo de agentes de la demo. Un orquestador reparte
las facturas pendientes entre subagentes, que a su vez pueden volver a
repartir —delegación A2A a escala— y cada hoja concilia la factura que le
tocó. Uno de ellos se encuentra con una nota de cliente que, con tono de
negocio normal, le pide cerrar la factura sin auditoría y dejar el total en
0. El agente no sabe que eso está mal.

La corrida se hace dos veces, con Roxy y sin Roxy, y la diferencia es lo que
muestra el producto: sin Roxy la operación se emite y nadie se entera; con
Roxy queda evaluada, registrada y —si viola una regla— bloqueada.

**Para correrlo y probarlo: [DEPLOY.md](DEPLOY.md).**

## Qué necesita

Nada levantado en tu máquina. El bloque no abre bases de datos ni comparte
código con otros bloques: habla por HTTP con tres servicios desplegados, y
los defaults ya apuntan ahí.

| variable | default | para qué |
|---|---|---|
| `DEMO_API_URL` | `https://roxygt.lat/demo-api` | leer las facturas (solo lectura) |
| `ROXY_URL` | `https://roxygt.lat/gateway` | someter cada escritura al veredicto |
| `DASHBOARD_API_URL` | `https://roxygt.lat/api` | registrar el árbol de agentes |
| `ROXY_MCP_NAME` | `mongo-catalog-mcp` | el MCP contra el que Roxy ejecuta |

`mongo-catalog-mcp` es uno de los MCPs que ya vienen registrados en Roxy, y
detrás tiene un MCP de MongoDB real sobre la misma colección `invoices` que
sirve demo-api. Por eso una operación aprobada la ejecuta Roxy de verdad.

## Cómo circula una operación

```
subagente
  ├── read_invoice / read_customer_notes   → demo-api + portal propio
  └── update_invoice
        ├── Roxy OFF → se emite, nadie la evalúa ni la registra
        └── Roxy ON  → POST /v1/evaluate
                         ├── denegada → 403, y la alerta queda en el dashboard
                         └── aprobada → Roxy la ejecuta contra el MCP
```

El árbol de delegación se registra solo: el SDK va enganchado como callback
de LangChain y hace `POST /agents` por cada agente que arranca.

## Estructura

- `agent_flow/orchestrator.py` — el orquestador (un LLM que reparte facturas
  entre subagentes, que a su vez pueden volver a repartir) y los subagentes
  (`AgentExecutor` con los tools de abajo).
- `agent_flow/invoice_tools.py` — los tools de un subagente: `read_invoice` y
  `read_customer_notes` para leer, `update_invoice` para escribir. La
  escritura **no se ejecuta acá**: se somete a Roxy, que es quien la lleva al
  MCP cuando aprueba.
- `agent_flow/customer_portal.py` — el portal de proveedores: las notas que
  el cliente dejó adjuntas. Es la superficie por la que entra la instrucción
  maliciosa (INV-1005 empuja a cerrar la factura sin auditoría y con el total
  en 0; INV-1011 es un pago legítimo). Vive en este bloque a propósito, para
  no inyectar nada en la base de nadie.
- `agent_flow/gateway.py` — el cliente del gateway. Existe porque el
  despliegue rompe dos supuestos del SDK: CloudFront convierte el 403 de una
  denegación en un 200 con el HTML del dashboard, y el MCP de Mongo responde
  por `text/event-stream`, no por JSON.
- `agent_flow/preflight.py` — el chequeo previo, antes de gastar tokens. Con
  `--roxy on` somete además una lectura inofensiva al MCP: es lo único que
  separa "lo denegaron" de "ese MCP no está registrado", porque los dos
  llegan como el mismo HTML.
- La trazabilidad sale del SDK (`roxy-sdk/`, publicado como `roxy-guard`).

## Límite conocido

Las reglas de `mongo-catalog-mcp` son las que vinieron con el MCP, y la
primera es *deny any write operation outside working hours*. Fuera de horario
Roxy deniega **toda** escritura, la maliciosa y la legítima: el contraste se
ve igual (nada se modificó, todo quedó registrado) pero por ese motivo y no
por los invariantes de la factura. Las reglas y el evaluador son del bloque
2; este bloque solo manda la intención completa de cada operación.
