# Roxy
### Sistema de agente de seguridad de MCPs

## Problema
Desde marzo de 2026 se comenzo el desarrollo de A2A, el cual promueve la idea de worflows completamente agenticos que delegan tareas entre sí. Esto implica que la seguridad de estas tareas delegadas dependen de un punto inicial de seguridad, y los sistemas detras de los MCPs quedan vulnerables a la deliberación de acciones de los agentes delegados. Esto significa que una empresa que maneje procesos de delegación de agentes a escala y conecta sistemas de datos sensibles a estos agentes, está sensible a que pueda haber problemas de modificaciones no deseadas.

## Solucion
Un sistema de agente de seguridad para los MCPs el cual maneja el protocolo A2A para comunicarse con los agentes delegados y determina si permite acceso (hace exchange de token) preguntando al agente cual es la intencion, o asumiendo de la request del agente al MCP (agente agnostico a la capa de seguridad). Adicionalmente el sistema de seguridad reporta los intentos de acceso indebido para trazabilidad.


## Context
Roxy es un agente que vigila la entrada de peticiones a los MCPS. Este no interactua con agentes, sino con el contexto entregado a los MCPs. Apartir de este contexto verifica una por una las reglas del MCP. El modo de verificacion se basa en comprobar si el contexto de entrada se ajusta dentro del contenido de la regla, escencialmente respondiendo la pregunta para cada regla:

    "Este contexto peticion, se encuenta bajo lo que rige esta regla?"

Por ejemplo,

    MCP Objetivo: MongoDB Atlas
    Context: "Borrar documentos 1, 2 y 3 de collecion ropa"
    Rules:
        - 1. "No borrar coleccion"
        - 2. "No borrar documentos de la collecion ropa"
    
    Ejecucion:
        1. Context -> Rule 1 = Cumple (Contexto no busca borrar collecion)
        2. Context -> Rule 2 = NO-Cumple (Contexto busca borrar documentos de collecion ropa)
    
    Veredicto: all(1., 2.) = NO

## Dashboard
The Roxy dashboard provides an interactive panel for users to see (for now one user) to see the logs of the requests that have arrived to Roxy, and tell what the outcome has been an a description. There are positive green logs which are telling when Roxy allowed entry, and there are negative red logs which are telling when Roxy denied entry with the reason of denial. Indepentent of the status of the log, it should show the detail of what happened in that request -- requested, status, description, time, etc --.


## Bloques
1. [x] Datos de Mongo (schema y mock) - **Santiago**
    - [x] MCPs
        - [x] Nombre, etc
        - [x] Server
        - [x] Authorization
        - [x] Reglas
            - [x] Instrucction
            - [x] Prioridad
    - [x] Logs de seguridad
        - [x] Estado
        - [x] MCP ingresado
        - [x] Time
        - [x] Who accessed
        - [x] Log description

2. [ ] Roxy Gateway - API/MCP de agente - **Stiven**
    - [ ] Authorization con token de agente
    - [ ] Routing a MCP
    - [ ] Verificacion
        - [ ] Verifica detalle de MCP
            - [ ] Descripcion
            - [ ] Reglas
    - [ ] Peticion Aprobada (Opcional)
        - [ ] Realiza peticion
        - [ ] Genera log positivo informativo
    - [ ] Peticion Denegada (Opcional)
        - [ ] General log negativo actionable
    - [ ] Respuesta a agente

3. [x] Dashboard (full stack web) - **Santiago**
    - [x] API de dashboard que lee logs
    - [x] Frontend que muestra logs pero principalmente alertas

4. [x] API funcional de demo con datos en Mongodb - **Freddy**
    - [x] Defecto de posible falla en inconsistencia de datos

5. [ ] Langchain/Other flujo de agentes para demo - **Andres**
    - [ ] 2 agentes, 1 orquestador que recibe tarea y que lance múltiples sub-agentes y que algunos de esos agentes hagan operaciones que no deben y otros operaciones que si, para que se muestre como quedan operaciones indebidas las cuales el agente no sepa cuales son.
    - [ ] Debería haber un agente que tiene injecciones de modificaciones nocivas para la base de datos (reglas a especificar luego)
    - [ ] Proceso que efectua cambios nocivos para la API funcional
        - [ ] Conecta con MCP de Mongo
        - [ ] Con/Sin Roxy

6. [x] Investigación - **Freddy**
    - [x] Segun criterios de evaluacion
    - [x] A2A en la industria
    - [x] Accidentes Reales de A2A
    - [x] Otras soluciones existentes
    - [x] Impacto de solucion en el mercado (impacto de soliconar este problema)
    - [ ] Le cuenta al equipo


7. [ ] Demo interactivo - **Todos**
    - [ ] API funciona normalmente
    - [ ] API despues de proceso agentic sin Roxy
        - [ ] Ver dashboard
    - [ ] API despues de proceso agentic con Roxy
        - [ ] Ver dashboard
	
8. [ ] Landing Page - Freddy


9. [ ] Langchain interceptor class that creates trace of nodes (agents) and register directly into database with their context, their purpose - **Santiago**
    - [ ] Callback para eventos de langchain (on_chain_start, on_tool_start, on_llm_start)

10. [ ] Capa de verificación - **Sebastian**
    - [ ] Traducir lenguaje natural (componentes de contexto y reglas) a lenguaje para Z3
    - [ ] Verificar con Z3 la lógica de que el contexto se encuentre correspondiente a las reglas


