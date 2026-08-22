# Roxy
### Sistema de agente de seguridad de MCPs

## Problema
Desde marzo de 2026 se comenzo el desarrollo de A2A, el cual promueve la idea de worflows completamente agenticos que delegan tareas entre sí. Esto implica que la seguridad de estas tareas delegadas dependen de un punto inicial de seguridad, y los sistemas detras de los MCPs quedan vulnerables a la deliberación de acciones de los agentes delegados. Esto significa que una empresa que maneje procesos de delegación de agentes a escala y conecta sistemas de datos sensibles a estos agentes, está sensible a que pueda haber problemas de modificaciones no deseadas.

## Solucion
Un sistema de agente de seguridad para los MCPs el cual maneja el protocolo A2A para comunicarse con los agentes delegados y determina si permite acceso (hace exchange de token) preguntando al agente cual es la intencion, o asumiendo de la request del agente al MCP (agente agnostico a la capa de seguridad). Adicionalmente el sistema de seguridad reporta los intentos de acceso indebido para trazabilidad.


## Bloques
1. Datos de Mongo (schema y mock) - **Santiago**
    - MCPs
        - Nombre, etc
        - Server
        - Authorization
        - Reglas
            - Instrucction
            - Prioridad
    - Logs de seguridad
        - Estado
        - MCP ingresado
        - Time
        - Who accessed
        - Log description

2. Roxy Gateway - API/MCP de agente - **Stiven**
    - Authorization con token de agente
    - Routing a MCP
    - Verificacion
        - Verifica detalle de MCP
            - Descripcion
            - Reglas
    - Peticion Aprobada (Opcional)
        - Realiza peticion
        - Genera log positivo informativo
    - Peticion Denegada (Opcional)
        - General log negativo actionable
    - Respuesta a agente

3. Dashboard (full stack web) - **Santiago**
    - API de dashboard que lee logs
    - Frontend que muestra logs pero principalmente alertas

4. API funcional de demo con datos en Mongodb - **Freddy**
    - Defecto de posible falla en inconsistencia de datos

5. Langchain/Other flujo de agentes para demo - **Andres**
    - 2 agentes, 1 orquestador que recibe tarea y que lance múltiples sub-agentes y que algunos de esos agentes hagan operaciones que no deben y otros operaciones que si, para que se muestre como quedan operaciones indebidas las cuales el agente no sepa cuales son.
    - Debería haber un agente que tiene injecciones de modificaciones nocivas para la base de datos (reglas a especificar luego)
    - Proceso que efectua cambios nocivos para la API funcional
        - Conecta con MCP de Mongo
        - Con/Sin Roxy

6. Investigación - **Freddy**
    - Segun criterios de evaluacion
    - A2A en la industria
    - Accidentes Reales de A2A
    - Otras soluciones existentes
    - Impacto de solucion en el mercado (impacto de soliconar este problema)
    - Le cuenta al equipo


7. Demo interactivo - **Todos**
    - API funciona normalmente
    - API despues de proceso agentic sin Roxy
        - Ver dashboard
    - API despues de proceso agentic con Roxy
        - Ver dashboard
	
8. Landing Page - Freddy


9. Langchain interceptor class that creates trace of nodes (agents) and register directly into database with their context, their purpose - **Santiago**
    - Callback para eventos de langchain (on_chain_start, on_tool_start, on_llm_start)


