# Arco narrativo para el pitch

Esto es investigación de narrativa, **no el deck**: describe qué historia
contar, en qué orden, y qué hallazgo (con su fuente) respalda cada momento.
Armar las slides es un paso aparte.

## Por qué este orden

El arco va de **urgencia real** → **evidencia concreta** → **por qué lo
existente no alcanza** → **qué hace Roxy distinto** → **prueba en vivo**.
La demo con `demo-api` cierra el pitch, no lo abre: primero hay que
convencer de que el problema es real y caro, después mostrar que ni la
industria de seguridad ni los competidores lo tienen resuelto, y solo ahí
tiene sentido que el jurado vea a Roxy actuar sobre datos reales.

## Beat 1 — Gancho de apertura: "esto pasó esta semana"

A2A se movió de la Linux Foundation a la AAIF (Agentic AI Foundation) el
**17 de agosto de 2026** — quedando bajo el mismo techo que MCP por
primera vez. Es noticia de días, no de años. Abre con urgencia real, no
genérica.

Fuente: [industry-and-market.md](industry-and-market.md), sección "Panorama
de la industria".

## Beat 2 — El problema es joven pero ya es grande

Línea de tiempo real (corrige la fecha de nuestro propio `idea.md`, que
decía marzo 2026): A2A nació en **abril de 2025**, pasó a la Linux
Foundation en junio de 2025, llegó a v1.0 con adopción empresarial real en
**abril de 2026**. Poco más de un año de vida, y ya:

- Gartner proyecta **150,000+ agentes** por empresa Fortune 500 para 2028
  (vs. menos de 15 en 2025).
- La adopción de agentic AI **supera 8 a 1 a su gobernanza**; las empresas
  gastan **17x más en herramientas de IA que en asegurarlas**.

Fuente: [industry-and-market.md](industry-and-market.md).

## Beat 3 — La evidencia: no es hipotético

Tres hechos concretos, en orden de impacto narrativo:

1. **El propio servidor MCP de referencia de Anthropic era explotable por
   RCE** (3 CVEs encadenables, divulgado enero 2026) — ni siquiera el
   creador de MCP lo hizo bien a la primera.
2. **"Agents of Chaos"** (red-team académico, feb. 2026): un agente
   entregó un número de seguro social completo porque se lo pidieron
   "reenviando el correo", no directamente; otro obedeció a un atacante
   que solo cambió su nombre de usuario en Discord.
3. El gap de confianza más filoso de todos: **82% de los ejecutivos cree**
   que sus políticas los protegen, pero **solo 21% tiene visibilidad
   real** de qué hacen sus agentes.

Fuente: [a2a-incidents.md](a2a-incidents.md).

## Beat 4 — El costo de no resolverlo

- Brecha promedio global: **$4.99M**. Brecha **AI-enabled: $6M**. 1 de
  cada 4 brechas maliciosas ya es AI-enabled (+56% interanual) — [IBM
  2026](industry-and-market.md).
- Específico a agentes: **88% de empresas con agentes desplegados** tuvo
  al menos un incidente relacionado; brecha promedio ligada a agentes
  **$4.7M**; en pruebas controladas, agentes autónomos atravesaron
  sistemas completos en **menos de 2 horas**. Causas raíz: **61% exceso de
  permisos, 34% prompt injection** — [Darktrace 2026](industry-and-market.md).

Esas dos causas raíz (exceso de permisos + prompt injection) son
literalmente lo que Roxy ataca: es la línea que conecta "esto es lo que
rompe" con "esto es lo que Roxy previene".

## Beat 5 — Por qué lo que existe no alcanza

Recorrido rápido por 5 soluciones reales (Cedar/OPA/Cerbos/Permit.io,
mcp-firewall, PointGuard AI, LlamaFirewall, DOF-MESH) — ver
[existing-solutions.md](existing-solutions.md) para el detalle de cada
una. El patrón: todas exigen que **un desarrollador** traduzca la regla de
negocio a un lenguaje formal (Cedar, Rego, YAML, invariantes Z3) antes de
que el sistema pueda protegerla. Ninguna deja que el dueño del dato escriba
la regla en español/inglés llano y confíe en que el sistema la interprete
en el momento.

**Autocrítica honesta a incluir, no esconder:** ese es precisamente el
punto en el que Roxy usa un LLM como juez — y todos los competidores serios
evitan eso a propósito. Se recomienda decirlo en voz alta en el pitch,
encuadrado como roadmap ("el MVP prueba que el modelo de regla en lenguaje
natural funciona; el endurecimiento es la capa de decisión"), no como algo
a ocultar. Contexto completo de esta discusión ya la tuvimos como equipo
(ver el hilo sobre "IA vigila IA" e ideas de filtro determinista +
hash-chain de logs).

## Beat 6 — Entra Roxy, y la prueba en vivo

Aquí es donde el pitch pasa de investigación a producto, y `demo-api`
entra como el servicio "víctima" que hace la corrupción visible en tiempo
real frente al jurado:

1. **API funcionando normal** — `demo-api` corriendo (local o
   containerizado), `GET /health/consistency` → 200, 12 facturas
   consistentes.
2. **Flujo de agentes sin Roxy** — el orquestador multi-agente corrompe
   datos directo en Mongo (bypasea `demo-api` por completo, ataca la
   colección `demo_billing.invoices` directamente); `GET
   /health/consistency` → 409 con el detalle exacto de la violación;
   dashboard lo refleja.
3. **`POST /admin/reset`** — vuelve a datos limpios, sin reiniciar nada.
4. **Mismo flujo, con Roxy** — Roxy evalúa las peticiones del agente
   contra las reglas del MCP antes de que lleguen a Mongo; `/health/
   consistency` se mantiene en 200.

Esto convierte cada estadística abstracta de los beats 2–4 en algo que el
jurado ve pasar en 90 segundos: el mismo agente, el mismo dato, con y sin
Roxy — la diferencia es visible y verificable en vivo (no solo contada).

## Resumen de fuentes por beat

| Beat | Documento |
|------|-----------|
| 1–2  | [industry-and-market.md](industry-and-market.md) |
| 3–4  | [a2a-incidents.md](a2a-incidents.md), [industry-and-market.md](industry-and-market.md) |
| 5    | [existing-solutions.md](existing-solutions.md) |
| 6    | `demo-api/README.md` (Bloque 4), corrida en vivo |
