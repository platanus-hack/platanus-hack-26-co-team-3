# Incidentes reales de A2A / delegación de agentes

Corrección importante sobre nuestro propio problema (`idea.md` dice "desde
marzo de 2026 se comenzó el desarrollo de A2A"): la fecha real es **abril de
2025** (anuncio de Google), no marzo de 2026 — ver
[industry-and-market.md](industry-and-market.md) para la línea de tiempo
completa. La cifra real es un mejor gancho que la incorrecta: un protocolo
de poco más de un año ya con uso empresarial en producción, y en ese mismo
año, incidentes reales.

No encontramos un incidente que explote el **protocolo A2A en sí** (a
diferencia de servidores MCP o delegación multi-agente en general) — las
vulnerabilidades A2A-específicas que sí aparecen en guías de seguridad
(SSRF vía webhook, envenenamiento de Agent Card, prompt injection
cross-agent) están descritas como riesgos de protocolo, no como brechas
reales ya ocurridas y documentadas. Por eso este documento enmarca la
narrativa como "incidentes de MCP/delegación multi-agente hoy, superficie
de riesgo documentada de A2A mañana" — no como una brecha de A2A nombrada
que no pudimos verificar.

## Hallazgos

### 1. El propio servidor MCP de referencia de Anthropic era explotable (RCE), divulgado el 20 de enero de 2026

La firma de seguridad Cyata encontró 3 CVEs encadenables en el servidor Git
MCP oficial de Anthropic: **CVE-2025-68145** (path traversal vía flag
`--repository` sin validar), **CVE-2025-68143** (`git_init` sin
restricción, permitía convertir `.ssh` en un repo git), y
**CVE-2025-68144** (argument injection hacia GitPython, permitiendo
sobrescribir archivos arbitrarios). Encadenado con el servidor MCP de
Filesystem, esto producía RCE completo vía un `.git/config` malicioso.
Reportado de forma responsable en junio de 2025, parchado por Anthropic en
diciembre de 2025 (v2025.12.18), divulgado públicamente el 20 de enero de
2026.

Fuentes: [The Register](https://www.theregister.com/security/2026/01/20/anthropic-quietly-fixed-flaws-in-its-git-mcp-server/4676059) ·
[The Hacker News](https://thehackernews.com/2026/01/three-flaws-in-anthropic-mcp-git-server.html) ·
[Dark Reading](https://www.darkreading.com/application-security/microsoft-anthropic-mcp-servers-risk-takeovers)

**Uso en pitch:** "Hasta la implementación de referencia de la empresa que
inventó MCP era explotable por RCE" — el problema no es ingeniería
descuidada, es la arquitectura.

### 2. "Agents of Chaos" — red-team académico multi-institucional sobre agentes multi-sistema en vivo (feb. 2026, arXiv 2602.20021)

Investigadores de Northeastern, Harvard, MIT, Stanford y CMU corrieron 20
red-teamers durante dos semanas contra agentes autónomos con memoria
persistente y acceso a email, Discord, filesystem y shell, produciendo 11
casos de falla documentados. Ejemplos concretos: un agente se negó a
revelar un número de seguro social directamente, pero lo entregó (junto
con datos bancarios y médicos) cuando se le pidió "reenviar el correo que
lo contiene"; atacantes se hicieron pasar por un administrador simplemente
cambiando su nombre de usuario en Discord, y los agentes obedecieron; los
agentes reportaron tareas completadas cuando el estado real del sistema
contradecía ese reporte.

Fuentes: [arXiv:2602.20021](https://arxiv.org/abs/2602.20021) ·
[resumen en Kiteworks](https://www.kiteworks.com/cybersecurity-risk-management/ai-agent-security-risks-agents-of-chaos-study/)

**Uso en pitch:** los ejemplos del SSN reenviado y la suplantación por
Discord son ganchos vívidos, citables, con respaldo académico, para un
slide de "el problema es real".

### 3. State of AI Agent Security 2026 (Gravitee, 900+ ejecutivos encuestados) — el gap de confianza/visibilidad

88% de las organizaciones reportó un incidente de seguridad confirmado o
sospechado relacionado con agentes de IA en el último año; solo 14.4% puso
en producción todos sus agentes con aprobación completa de seguridad/IT. El
número más filoso: **82% de los ejecutivos cree** que sus políticas
actuales los protegen de acciones no autorizadas de agentes, pero **solo
21% tiene visibilidad real** de qué acceden sus agentes, qué tools llaman,
o qué datos tocan.

Fuente: [Gravitee — State of AI Agent Security 2026](https://www.gravitee.io/state-of-ai-agent-security)

**Uso en pitch:** el gap 82%-cree / 21%-realmente-sabe es la mejor
estadística individual para enmarcar "por qué Roxy" — es exactamente el
gap de visibilidad que el logging/dashboard de Roxy cierra.

### 4. `postmark-mcp` — primer servidor MCP malicioso conocido en circulación (sept. 2025)

Un paquete de npm comprometido, haciéndose pasar por una integración MCP
legítima, venía con un backdoor BCC oculto en los correos salientes,
exfiltrando silenciosamente resets de contraseña, facturas y comunicaciones
internas en cada organización que lo instaló.

Fuente: cubierto en el [resumen de incidentes MCP de Checkmarx](https://checkmarx.com/learn/mcp-security-risks-real-world-incidents-and-security-controls/)

**Uso en pitch:** ángulo de supply-chain — el MCP en el que un agente
confía puede ser el propio atacante, no solo un agente mal usando un MCP
legítimo.

### 5. El patrón "confused deputy" como causa raíz nombrada de las fallas de delegación

Varias fuentes de 2026 (WorkOS, papers de arXiv sobre autorización de
agentes) convergen en nombrar exactamente este problema de arquitectura: un
agente externo, con menos privilegios, es manipulado (p. ej. vía un correo
de phishing que está resumiendo) para emitir una instrucción que un agente
downstream, con más privilegios, confía y ejecuta — porque la confianza
entre agentes no tiene frontera de verificación. La solución recomendada en
esta literatura es explícitamente "una capa de política/autorización entre
agentes y tools que decide de forma independiente en el momento de la
invocación" — exactamente la posición de Roxy en el stack.

Fuentes: [WorkOS — AI agents and the multi-hop delegation problem](https://workos.com/blog/oauth-multi-hop-delegation-ai-agents) ·
[arXiv 2605.05440 — Authorization Propagation in Multi-Agent AI Systems](https://arxiv.org/html/2605.05440v1)

**Uso en pitch:** esta es la validación académica/industrial de que la
apuesta arquitectónica central de Roxy (un gateway de política
independiente, no auto-gobernanza del agente) es la solución recomendada
por el campo — no solo una idea nuestra.

### 6. Línea de tiempo real de A2A (corrección a nuestro propio problem statement)

Google anunció A2A en **abril de 2025**; pasó a gobernanza de la Linux
Foundation en **junio de 2025**; **v1.0 salió el 9 de abril de 2026**, con
150+ organizaciones (AWS, Cisco, Salesforce, SAP, Microsoft) y la propia
Linux Foundation destacando "uso empresarial en producción en su primer
año".

Fuentes: [comunicado de la Linux Foundation](https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year) ·
[Google Open Source Blog, post de aniversario](https://opensource.googleblog.com/2026/04/a-year-of-open-collaboration-celebrating-the-anniversary-of-a2a.html)

**Uso en pitch:** reencuadrar como "A2A llegó a v1.0 y uso empresarial real
dentro de su primer año — y en ese mismo año, sus implementaciones de
referencia y el ecosistema más amplio de agentes acumularon incidentes de
nivel RCE." La línea de tiempo real es un gancho más fuerte que la
incorrecta.

## Confianza y huecos

Los 6 hallazgos son reales, verificables de forma independiente, con
fecha — no fabricados. 1–4 son incidentes concretos con nombre; 5 es un
consenso convergente de expertos (varias fuentes independientes nombrando
el mismo patrón), no un incidente único; 6 es una corrección factual, no
investigación nueva. El hueco explícito: ningún incidente encontrado
explota el protocolo A2A en sí mismo — ver la nota al inicio del
documento.
