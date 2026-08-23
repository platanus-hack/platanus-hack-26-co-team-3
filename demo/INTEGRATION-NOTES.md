# Notas de integración cross-block

Notas para el equipo sobre costuras entre bloques que hoy no están resueltas
en `mongo-data/schema.json`. No es código, no cambia ningún bloque: es la
lista de decisiones pendientes antes de que Bloques 2, 5 y 9 puedan
integrarse entre sí.

## 1. Falta una colección (Bloque 9 la necesita)

El schema actual (`mongo-data/schema.json`) solo define `mcps` y `security`.
El Bloque 9 (interceptor de LangChain) escribe nodos de agentes en cada
evento de callback, y eso no cabe en ninguna de las dos colecciones
existentes.

Propuesta de colección `traces`:

- `run_id`
- `parent_run_id`
- `root_run_id`
- `type` (`chain` | `tool` | `llm`)
- `name`
- `purpose`
- `context`
- `started_at`

Sin esta colección el Bloque 9 no tiene dónde escribir.

**Decisión de:** Santiago.

## 2. LangChain ya da el árbol de delegación

Los callbacks `on_chain_start` / `on_tool_start` reciben `run_id` y
`parent_run_id`. Eso ES la cadena de delegación. No hay que inventar un
esquema de IDs propio: el `parent_run_id` de un sub-agente es el `run_id`
del agente que lo lanzó.

**Decisión de:** Santiago.

## 3. Faltan campos en `security`

La colección tiene `accessedBy` (string), lo cual no permite responder
"cuál de los seis sub-agentes hizo esto y quién lo creó".

Agregar:

- `runId` (string) — `run_id` del nodo que hizo la llamada
- `parentRunId` (string) — de quién heredó
- `rootRunId` (string) — tarea raíz, para agrupar el árbol
- `attemptedAction` (string) — nombre de la tool que se intentó llamar

Sin `runId`, el dashboard no puede dibujar el árbol y el Bloque 5 (múltiples
sub-agentes, unos legítimos y otros no) no se puede renderizar.

**Decisión de:** Santiago.

## 4. Costura sin dueño — propagación de identidad

El interceptor (Bloque 9) escribe el nodo. Roxy (Bloque 2) necesita saber
qué nodo llama. Pero quien propaga el dato es el flujo de agentes
(Bloque 5). Tres bloques, una costura, ningún dueño.

Contrato propuesto:

- El agente envía su `run_id` a Roxy en cada llamada, en el header
  `X-Roxy-Agent-Run: <run_id>`.
- Roxy lo usa como clave para leer el nodo en `traces` y obtener
  `parent_run_id`, `purpose` y `context`.

**Decisión de:** Santiago, Stiven y Andrés (acuerdo de los tres antes de que
cada uno avance).

## 5. Límite conocido del MVP (para el pitch, no es un bug)

El interceptor corre dentro del runtime del agente, así que la identidad es
DECLARADA, no probada. Un agente comprometido podría mentir sobre su
`run_id`. Es aceptable para el MVP; el endurecimiento es que Roxy emita
tokens firmados de vida corta en vez de leer el trace. Misma lógica de
cadena, identidad criptográfica en vez de declarada. Hay que tenerlo listo
como respuesta si el jurado pregunta.

## 6. Nota de integración del Bloque 4

La API funcional vive en base `demo_billing`, colección `invoices`. El MCP
de Mongo del Bloque 5 debe apuntar ahí para que el daño sea visible en
`/health/consistency`.
