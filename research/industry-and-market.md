# Panorama de industria e impacto de mercado

## Panorama de la industria

- **A2A nació en abril de 2025** en Google Cloud Next como protocolo
  abierto (Apache 2.0), con 50+ partners iniciales (Atlassian, Box,
  Cohere, LangChain, MongoDB, Salesforce, SAP, ServiceNow, Workday).
  [Announcing the Agent2Agent Protocol (A2A)](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/) ·
  [Agent2Agent — Wikipedia](https://en.wikipedia.org/wiki/Agent2Agent).
  *Uso en slide: fecha de nacimiento del problema, para anclar "esto es
  nuevo".*

- **Google donó A2A a la Linux Foundation el 23 de junio de 2025**
  (miembros fundadores: AWS, Cisco, Google, Microsoft, Salesforce, SAP,
  ServiceNow); **Anthropic donó MCP a la nueva Agentic AI Foundation
  (AAIF) el 9 de diciembre de 2025**. MCP es vertical (agente→herramienta),
  A2A es horizontal (agente→agente): son complementarios, no
  competidores — exactamente el par de piezas entre las que se sienta
  Roxy. [MCP joins the Agentic AI Foundation](https://blog.modelcontextprotocol.io/posts/2025-12-09-mcp-joins-agentic-ai-foundation/) ·
  [Linux Foundation press release](https://www.linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation).
  *Uso en slide: justifica por qué el problema de seguridad cae "entre"
  dos protocolos que nadie gobierna juntos todavía.*

- **Muy reciente (17 de agosto de 2026):** A2A se movió del paraguas
  general de la Linux Foundation a la AAIF específicamente, quedando bajo
  el mismo techo que MCP. La AAIF creció de menos de 40 miembros en su
  lanzamiento (dic. 2025) a 250+ en agosto 2026.
  [Google's A2A protocol gets a new home (Axios)](https://www.axios.com/2026/08/17/a2a-agentic-ai-foundation-open-ai-standards) ·
  [A2A joins AAIF's open agentic stack](https://aaif.io/blog/a2a-joins-aaif).
  *Uso en slide: gancho de "esto pasó esta semana" para abrir el pitch con
  urgencia real, no genérica.*

- **Adopción empresarial:** 29% de empresas ya corren agentic AI en
  producción (encuesta 2025), 44% más planea sumarse en un año; Gartner
  proyecta que 40% de las apps empresariales tendrán agentes específicos
  para fines de 2026 (vs. menos de 5% en 2025); encuesta a 147 CIOs: 24%
  ya desplegó agentes, 50% experimentando.
  [What is A2A? (Apono)](https://www.apono.io/blog/what-is-agent2agent-a2a-protocol-and-how-to-adopt-it/) ·
  [Gartner press release, ago. 2025](https://www.gartner.com/en/newsroom/press-releases/2025-08-26-gartner-predicts-40-percent-of-enterprise-apps-will-feature-task-specific-ai-agents-by-2026-up-from-less-than-5-percent-in-2025).

- **La estadística de escala más fuerte:** Gartner proyecta que para 2028
  una empresa Fortune 500 promedio tendrá **150,000+ agentes** en uso,
  frente a **menos de 15 en 2025**.
  [Gartner Predicts 2026: Secure AI Agents to Avoid Ungoverned Sprawl and Abuses](https://www.rubrik.com/lp/analyst-reports/gartner-predicts-2026-secure-ai-agents-to-avoid-ungoverned-sprawl-and-abuses)
  (reporte Gartner del 17-dic-2025, vía Rubrik).
  *Uso en slide: la mejor cifra "de aquí a poco esto va a explotar" de
  todo el set.*

- **Un jugador enterprise enorme se está moviendo justo ahora, y
  todavía no llegó:** Workday (11,500+ organizaciones, 65%+ del
  Fortune 500 — y uno de los 50+ partners iniciales de A2A)
  anunció el 2 de junio de 2026 "Agent Passport", una capa de
  gobernanza/identidad para agentes de IA. Sigue en **acceso
  anticipado para el 2do semestre de 2026**, con disponibilidad
  general recién proyectada para fin de año — ni siquiera Workday
  tiene esto en producción todavía, y opera en una capa distinta
  (identidad/atestación del agente, no la frontera A2A→MCP que
  cubre Roxy — ver [existing-solutions.md](existing-solutions.md)).
  [Workday Newsroom, 2-jun-2026](https://newsroom.workday.com/2026-06-02-Workday-Launches-Agent-Passport-to-Test,-Verify,-and-Continuously-Monitor-Every-AI-Agent-in-the-Enterprise).
  *Uso en slide: valida el timing ("hasta Workday se está moviendo
  recién ahora") sin que se lea como que Roxy ya tiene competencia
  directa.*

- **El gap de gobernanza, con números:** Gartner nombró "Agentic AI
  Demands Cybersecurity Oversight" y "IAM Adapts to AI Agents" como las
  dos tendencias de ciberseguridad #1 para 2026 — la gestión de identidad
  no creció al ritmo del despliegue de agentes. Un análisis independiente
  sintetiza el mismo reporte así: **la adopción de agentic AI supera 8 a 1
  a su gobernanza**, y las empresas gastan **17x más en herramientas de
  IA que en asegurarlas**; el gasto total en seguridad de la información
  llega a $244.2B en 2026 (+13.3%).
  [Gartner Predicts 2026 (Rubrik)](https://www.rubrik.com/lp/analyst-reports/gartner-predicts-2026-secure-ai-agents-to-avoid-ungoverned-sprawl-and-abuses) ·
  [Information Security Spending 2026 Hits $244.2B As Agentic AI Outpaces Defenses 8 to 1](https://softwarestrategiesblog.com/2026/03/24/information-security-spending-2026/).
  *Uso en slide: ESTA es la estadística para el slide de "el problema",
  resume todo en una frase.*

- Mismo reporte Gartner: para 2027, el costo de abusos de agentes
  "task-driven" será 4x más alto que en sistemas multi-agente; para 2028,
  las organizaciones que se salten testing ofensivo pre-producción tendrán
  2x más incidentes. (Misma fuente Rubrik arriba.)

## Impacto de mercado

- **Nota de honestidad metodológica primero:** el "market size" de
  agentic AI varía muchísimo según qué se cuente — Gartner cuenta
  capacidad agéntica embebida en software empresarial en general
  ($201.9B en 2026), mientras firmas de investigación de mercado miden
  solo plataformas standalone ($9.1B–$10.9B en 2026, 40%+ CAGR). Ambas
  cifras son reales, miden cosas distintas — hay que ser explícito sobre
  cuál se usa en el slide.
  [Roundup of agentic AI forecasts 2026](https://softwarestrategiesblog.com/2026/02/26/roundup-of-agentic-ai-forecasts-and-market-estimates-2026/) ·
  [Agentic AI Market Report (Fortune Business Insights)](https://www.fortunebusinessinsights.com/agentic-ai-market-114233).

- **Contrapeso honesto sobre el hype:** solo 23% de las organizaciones ha
  escalado realmente un sistema agentic a producción, y Gartner proyecta
  que 40% de los proyectos serán cancelados para 2027 — bueno para no
  sobre-vender, y para argumentar que gobernanza (no solo velocidad) es lo
  que separa a los que sí escalan. (Misma fuente Rubrik/Gartner.)

- **El mercado específico de Roxy, con número exacto:** el mercado de
  "Agentic AI Security" pasa de **$1.65B en 2026 a $13.52B en 2032**
  (CAGR 42%) — esta es la categoría literal en la que cae Roxy. Cifra
  hermana: "Cybersecurity Agentic AI Market" de $2.43B (2026) a $9.63B
  (2031), CAGR 31.7%.
  [Agentic AI Security Market Surges to $13.52 billion by 2032](https://finance.yahoo.com/sectors/technology/articles/agentic-ai-security-market-surges-143000080.html) ·
  [Cybersecurity Agentic AI Market](https://market.us/report/agentic-ai-in-cybersecurity-market/).
  *Uso en slide: TAM/SAM, esta es la cifra a poner como "mercado que
  atacamos".*

- **Costo de NO resolver esto (el número más fuerte de todos, muy fresco —
  reporte IBM 2026 publicado 29-jul-2026, 602 organizaciones, marzo
  2025–feb 2026):** costo promedio global de una brecha = **$4.99M**
  (récord, +12% interanual); brechas **AI-enabled cuestan $6M en
  promedio** (~$1M más que el promedio global); **1 de cada 4 brechas
  maliciosas ya es AI-enabled** — un salto de 56% interanual.
  [IBM: One in Four Malicious Breaches are AI-Enabled, Costing Companies $6 Million on Average](https://newsroom.ibm.com/2026-07-29-ibm-study-one-in-four-malicious-breaches-are-ai-enabled,-costing-companies-6-million-on-average) ·
  [resumen en Help Net Security](https://www.helpnetsecurity.com/2026/07/30/ibm-cost-of-a-data-breach-2026/).

- **El dato más directamente relevante a lo que hace Roxy (Darktrace,
  State of AI Cybersecurity 2026):** 92% de profesionales de seguridad
  están preocupados por agentes de IA; **88% de las empresas que
  desplegaron agentes tuvieron al menos un incidente de seguridad
  relacionado**; costo promedio de una brecha ligada a agentes ≈
  **$4.7M**; en pruebas controladas, agentes autónomos atravesaron
  sistemas empresariales completos en **menos de 2 horas**. Causas raíz:
  **61% por credenciales/permisos excesivos**, **34% por prompt
  injection**.
  [Agentic AI Security: $4.7M Breaches, 92% Alarmed](https://shattered.io/agentic-ai-security-2026/).
  *Uso en narrativa: esas dos causas raíz (exceso de permisos + prompt
  injection) son literalmente el problema que Roxy ataca — línea perfecta
  para conectar "esto es lo que rompe" con "esto es lo que Roxy
  previene".*

- **Dato complementario 2025 (mismo IBM report, año anterior, sobre
  "shadow AI" específicamente):** brechas con alto uso de shadow AI
  cuestan $670K extra sobre el promedio; 97% de organizaciones con
  incidente relacionado a IA admitieron no tener controles de acceso de
  IA apropiados; 63% no tenía ninguna política de gobernanza de IA
  (Instituto Ponemon, n=600).
  [IBM 2025 Cost of a Data Breach: Navigating the AI rush](https://www.ibm.com/think/x-force/2025-cost-of-a-data-breach-navigating-ai).

## Confianza y huecos

Los números de A2A/adopción/gobernanza vienen de fuentes primarias
(Google, Linux Foundation, Gartner directo o vía reventa acreditada) o de
reportes anuales de nombre reconocido (IBM/Ponemon, Darktrace) — alta
confianza. Los "market size" de agentic AI/agentic-AI-security son
proyecciones de firmas de research de mercado de segunda línea (Fortune
Business Insights, market.us, etc.) — direccionalmente creíbles y
consistentes entre sí (todas muestran 30-40%+ CAGR), pero no son cifras a
nivel Gartner/IDC de primera línea; usarlas con la palabra "estimado" en
el slide. No existe todavía una cifra aislada de "mercado de A2A" — es
correcto tratarlo como subset de "agentic AI security".

Nota fuera de scope, para el doc de incidentes si hace falta ampliar:
vimos varias fuentes de incidentes específicos de brechas agentic (beam.ai
"5 Real AI Agent Security Breaches in 2026", digitalapplied.com "1 in 8
Breaches From Agentic Systems") no incluidas en
[a2a-incidents.md](a2a-incidents.md).
