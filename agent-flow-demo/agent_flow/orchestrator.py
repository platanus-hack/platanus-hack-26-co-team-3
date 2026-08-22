import json
from uuid import uuid4

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from agent_flow import config, mongo_tools
from agent_flow.tracing import RunTraceHandler

SUBAGENT_SYSTEM_PROMPT = """Eres un agente de conciliacion de facturacion.
Tu unica tarea es la factura {invoice_id}. Usa las herramientas para leer la
factura -incluyendo cualquier nota adjunta del cliente- y decide que hacer.
Si el estado o el monto cambian, deja siempre un audit_log_entry con un
resumen de la accion y su motivo. Responde en una linea con el resultado."""

ORCHESTRATOR_SYSTEM_PROMPT = """Eres el orquestador de un flujo de
conciliacion de facturacion. Recibes una tarea de alto nivel y una lista de
facturas 'issued'. Tu unico trabajo es devolver, en JSON, la lista de
sub-tareas a delegar (una por factura), cada una con "invoice_id" y
"purpose" (una instruccion breve para el subagente encargado). No accedas
tu mismo a las facturas."""


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block["text"])
    return " ".join(parts)


def _make_llm(temperature: float = 0.0) -> ChatAnthropic:
    return ChatAnthropic(
        model=config.ANTHROPIC_MODEL,
        api_key=config.ANTHROPIC_API_KEY,
        temperature=temperature,
        max_tokens=1024,
    )


def _plan(task: str, invoices: list, handler: RunTraceHandler, root_run_id) -> list:
    llm = _make_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", ORCHESTRATOR_SYSTEM_PROMPT),
        ("human", "Tarea: {task}\n\nFacturas 'issued':\n{invoices}\n\n"
                  "Devuelve solo el JSON, sin texto alrededor."),
    ])
    chain = prompt | llm
    result = chain.invoke(
        {"task": task, "invoices": json.dumps(invoices, ensure_ascii=False)},
        config={
            "run_id": root_run_id,
            "callbacks": [handler],
            "metadata": {"purpose": "Orquestador: planear delegacion", "context": task},
        },
    )
    text = _extract_text(result.content)
    start, end = text.find("["), text.rfind("]")
    return json.loads(text[start:end + 1])


def _run_subagent(invoice_id: str, purpose: str, handler: RunTraceHandler, root_run_id) -> dict:
    accessed_by = f"agent-subtask-{invoice_id}"
    sub_run_id = uuid4()
    llm = _make_llm()
    tools = mongo_tools.build_tools(accessed_by=accessed_by, run_id=str(sub_run_id))

    prompt = ChatPromptTemplate.from_messages([
        ("system", SUBAGENT_SYSTEM_PROMPT),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])
    agent = create_tool_calling_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools, verbose=False)

    output = executor.invoke(
        {"invoice_id": invoice_id, "input": purpose},
        config={
            "run_id": sub_run_id,
            "callbacks": [handler],
            "metadata": {
                "parent_run_id": str(root_run_id),
                "purpose": purpose,
                "context": {"invoice_id": invoice_id, "accessed_by": accessed_by},
            },
        },
    )
    return {
        "invoice_id": invoice_id,
        "accessed_by": accessed_by,
        "run_id": str(sub_run_id),
        "output": _extract_text(output["output"]),
    }


def run_task(task: str) -> dict:
    handler = RunTraceHandler()
    root_run_id = uuid4()

    invoices = mongo_tools.list_issued_invoices()
    plan = _plan(task, invoices, handler, root_run_id)

    results = []
    for step in plan:
        results.append(_run_subagent(step["invoice_id"], step["purpose"], handler, root_run_id))

    return {"root_run_id": str(root_run_id), "results": results}
