# Soluciones existentes y hueco de posicionamiento

## DOF-MESH (Cyber Paisa, Medellín)

Framework de gobernanza que intercepta y valida acciones de agentes
autónomos antes de ejecutarlas. Tagline: "Matemáticas, no promesas". Usa
**Z3 (SMT solver)** para probar formalmente 4 invariantes (score de
gobernanza, fórmulas de scoring, monotonicidad) — **0 LLMs** en el camino
de decisión, 100% determinista. Cada decisión queda anclada como hash
keccak256 inmutable en 9 blockchains vía un "DOFProofRegistry". Implementa
A2A Protocol v0.3.0 y un MCP Server (10 tools). Apunta a agentes autónomos
en general (arbitraje DeFi, risk scoring), no a agentes que programan ni a
reglas de negocio de un MCP específico.

Fuente: sitio del producto (dofmesh.com).

## Familia Cedar/OPA (ToolHive, Cedar for Agents, Cerbos, Permit.io, OPA)

Motores de autorización que evalúan cada tool-call de un agente contra
políticas escritas en un **lenguaje formal declarativo**: Cedar (ToolHive,
Cedar for Agents, Permit.io), Rego (OPA, también soportado por Permit.io),
o YAML estructurado (Cerbos). Cero LLM en el camino de decisión — es
matching determinista. Cedar for Agents incluso auto-genera un schema de
Cedar a partir de las descripciones de tools de un servidor MCP. Quien
escribe la política es un desarrollador o administrador que conoce ese
lenguaje formal, **no el dueño de negocio del MCP**.

Fuente: [ChatForest — Authorization & Policy Engine MCP Servers](https://chatforest.com/reviews/authorization-policy-engine-mcp-servers/)

## mcp-firewall (open source, ressl/mcp-firewall)

Gateway MCP open source con 7 etapas de seguridad inbound (kill switch,
rate limiter, detector de inyección basado en patrones, motor de
políticas). Las reglas se escriben en **YAML** (`match: { arguments: {
path: "**/.ssh/**" } }` → `action: deny`), evaluadas de forma determinista
— no hay LLM. Cuando hace falta aprobación humana, en sesión no
interactiva falla cerrado (deny).

Fuente: [github.com/ressl/mcp-firewall](https://github.com/ressl/mcp-firewall)

## PointGuard AI — MCP Security Gateway

Gateway comercial anunciado en marzo 2026: "zero-trust authorization,
tool-level controls, runtime guardrails", evalúa "risk across multiple
dimensions including the agent's role, real-time situational context,
behavioral history, and the trust relationship between agents". El
press release **no especifica el mecanismo real** de la decisión (¿reglas?
¿ML? ¿scoring?) — solo describe el resultado deseado, no cómo se calcula.
Vale la pena notar esa opacidad como dato en sí mismo.

Fuente: [National Law Review — press release](https://natlawreview.com/press-releases/pointguard-ai-unveils-mcp-security-gateway-secure-autonomous-ai-agents)

## LlamaFirewall (Meta, open source)

Framework de guardrails con tres componentes: PromptGuard 2 (detector de
jailbreak), CodeShield (análisis estático de código inseguro), y **Agent
Alignment Checks** — "a chain-of-thought auditor that inspects agent
reasoning for prompt injection and goal misalignment", marcado como
experimental. Es el más parecido a Roxy en el sentido de que audita el
razonamiento del agente (no solo reglas estáticas), pero su objetivo es
detectar inyección de prompts y desalineación de objetivo — no evaluar una
acción contra reglas de negocio en lenguaje natural definidas por el dueño
de un MCP.

Fuentes: [Meta AI Research — LlamaFirewall](https://ai.meta.com/research/publications/llamafirewall-an-open-source-guardrail-system-for-building-secure-ai-agents/) ·
[arXiv:2505.03574](https://arxiv.org/pdf/2505.03574)

## Workday Agent Passport — capa distinta, no un competidor directo

Anunciado el 2 de junio de 2026: prueba y verifica cada agente de IA
(propio o de terceros) **antes** de ponerlo en producción, con
atestación firmada por un partner externo (lanzamiento con Cisco AI
Defense, validando contra OWASP LLM Top 10 / NIST AI RMF / MITRE
ATLAS). En runtime, monitorea y puede *allow/block/route* la acción de
un agente, con revocación centralizada si aparece un problema.

**Es una capa distinta a la de Roxy, no un competidor directo:** opera
a nivel de *gobernanza de identidad del agente en la empresa*
(¿este agente puede existir/actuar en absoluto, quién lo certificó?),
no en la frontera de confianza A2A→MCP (¿esta acción puntual, contra
esta regla puntual, se permite ahora mismo?). El press release **no
menciona A2A ni MCP en ningún momento** — es ortogonal a los protocolos
que le dan forma al problema que ataca Roxy. Ambas capas podrían
convivir sin pisarse: Agent Passport decide qué agentes existen,
Roxy decide qué pueden hacer en cada request.

**Dato de validación de mercado, no de competencia:** Workday (11,500+
organizaciones, 65%+ del Fortune 500) recién está en **acceso
anticipado para el segundo semestre de 2026, con disponibilidad
general proyectada para fin de año** — es un anuncio de roadmap, no un
producto en producción. Un jugador de ese tamaño moviéndose *ahora* en
gobernanza de agentes, y todavía sin embarcar nada, es evidencia a
favor del timing del problema — no una razón para no construir Roxy.

Fuente: [Workday Newsroom — Agent Passport launch](https://newsroom.workday.com/2026-06-02-Workday-Launches-Agent-Passport-to-Test,-Verify,-and-Continuously-Monitor-Every-AI-Agent-in-the-Enterprise)

## Hueco de posicionamiento

Ningún actor encontrado hace exactamente lo que hace Roxy: tomar una regla
escrita en **lenguaje natural por el dueño del MCP** ("no borrar documentos
de la colección ropa") y usar un LLM para responder, por regla, "¿esta
petición cae bajo lo que rige esta regla?" en tiempo de request. Cedar/OPA/
Cerbos/Permit.io exigen que alguien traduzca esa intención a un lenguaje
formal (Cedar, Rego, YAML con schema) — eso es trabajo de desarrollador, no
del dueño de negocio del dato. DOF-MESH exige ir un paso más allá:
formalizar la regla como invariante demostrable en Z3. mcp-firewall es
determinista pero igual de rígido (YAML con matches literales).
LlamaFirewall es lo más cercano en espíritu (un LLM auditando
comportamiento) pero apunta a inyección/desalineación, no a cumplimiento de
reglas de MCP.

El hueco real: **autoría de política en lenguaje natural + interpretación
por LLM en el momento**, específicamente en la frontera de confianza
A2A→MCP. Workday Agent Passport confirma que ni siquiera los jugadores
más grandes están tocando esa frontera todavía — están un nivel arriba,
en gobernanza de identidad del agente, y ni siquiera ahí han llegado a
producción.

**Contracara honesta (no esconder esto en el pitch):** ese es exactamente
el mismo punto que ya identificamos como debilidad de Roxy ("IA vigila
IA") — todos los demás enfoques serios (Cedar, OPA, DOF-MESH) evitan
deliberadamente confiar en un LLM para la decisión final, por esa razón
exacta. Vale la pena decirlo así en el pitch: el MVP de hoy prueba que el
modelo de "regla en lenguaje natural" funciona y es accesible para el dueño
del dato (nadie más lo tiene); el roadmap honesto es endurecer la capa de
decisión (filtro determinista para reglas duras + LLM solo para las
ambiguas — ver conversación previa del equipo sobre esto).
