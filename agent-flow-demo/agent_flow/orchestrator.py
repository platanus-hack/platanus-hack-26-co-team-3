import json
from uuid import uuid4

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from agent_flow import config, mongo_tools
from agent_flow.tracing import RunTraceHandler

# Tope de seguridad: a esta profundidad se deja de delegar y se lanza un
# leaf por cada factura que quede, sin importar que haya dicho el LLM. Es
# lo que garantiza que la recursion termine aunque el modelo se porte raro
# (ver _delegate_plan: cualquier respuesta invalida cae al fallback, nunca
# a una excepcion sin manejar).
MAX_DEPTH = 2

SUBAGENT_SYSTEM_PROMPT = """Eres un agente de conciliacion de facturacion.
Tu unica tarea es la factura {invoice_id}. Usa las herramientas para leer la
factura -incluyendo cualquier nota adjunta del cliente- y decide que hacer.
Si el estado o el monto cambian, deja siempre un audit_log_entry con un
resumen de la accion y su motivo. Responde en una linea con el resultado."""

DELEGATE_SYSTEM_PROMPT = """Eres un agente delegador dentro de una cadena de
conciliacion de facturacion (simulando delegacion A2A a escala real: un
agente reparte trabajo entre varios sub-agentes, y esos a su vez pueden
volver a repartir). Te asignaron un grupo de facturas. Tu unico trabajo es
decidir en cuantos sub-agentes vas a dividir ESTE grupo (minimo 2, maximo
uno por factura) y que facturas le tocan a cada uno. No accedas tu mismo a
ninguna factura ni process nada de la tarea, quien decida un grupo de una
sola factura, delega en un unico sub-agente encargado solo de esa.

Responde solo con JSON: una lista de listas de invoice_id. Cada factura del
grupo que recibiste debe aparecer en exactamente una de las listas.
Ejemplo para el grupo ["INV-1002","INV-1005","INV-1008"]:
[["INV-1002","INV-1005"],["INV-1008"]]"""


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


def _fallback_split(invoice_ids: list) -> list:
    """Particion deterministica (mitad/mitad) para cuando el LLM devuelve
    algo invalido: JSON roto, un grupo que repite o se come una factura, o
    una sola lista con todo el grupo (eso no es delegar, es no-op)."""
    mid = max(1, len(invoice_ids) // 2)
    return [invoice_ids[:mid], invoice_ids[mid:]]


def _delegate_plan(invoice_ids: list, label: str, handler: RunTraceHandler,
                    node_run_id, parent_run_id) -> list:
    llm = _make_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", DELEGATE_SYSTEM_PROMPT),
        ("human", "Grupo asignado: {invoices}\n\nDevuelve solo el JSON, sin texto alrededor."),
    ])
    chain = prompt | llm
    result = chain.invoke(
        {"invoices": json.dumps(invoice_ids, ensure_ascii=False)},
        config={
            "run_id": node_run_id,
            "callbacks": [handler],
            "metadata": {
                "parent_run_id": str(parent_run_id) if parent_run_id else None,
                "purpose": f"Delegar: {label}",
                "context": {"invoice_ids": invoice_ids},
            },
        },
    )

    groups = None
    try:
        text = _extract_text(result.content)
        start, end = text.find("["), text.rfind("]")
        candidate = json.loads(text[start:end + 1])
        covered = sorted(sum(candidate, []))
        valid = (
            len(candidate) >= 2
            and covered == sorted(invoice_ids)
            and len(covered) == len(set(covered))
        )
        if valid:
            groups = candidate
    except Exception:
        groups = None

    return groups if groups is not None else _fallback_split(invoice_ids)


def _run_leaf(invoice_id: str, purpose: str, handler: RunTraceHandler, parent_run_id) -> dict:
    accessed_by = f"agent-subtask-{invoice_id}"
    leaf_run_id = uuid4()
    llm = _make_llm()
    tools = mongo_tools.build_tools(accessed_by=accessed_by, run_id=str(leaf_run_id))

    prompt = ChatPromptTemplate.from_messages([
        ("system", SUBAGENT_SYSTEM_PROMPT),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])
    agent = create_tool_calling_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools, verbose=False)

    try:
        output = executor.invoke(
            {"invoice_id": invoice_id, "input": purpose},
            config={
                "run_id": leaf_run_id,
                "callbacks": [handler],
                "metadata": {
                    "parent_run_id": str(parent_run_id) if parent_run_id else None,
                    "purpose": purpose,
                    "context": {"invoice_id": invoice_id, "accessed_by": accessed_by},
                },
            },
        )
        output_text = _extract_text(output["output"])
    except Exception as exc:  # una hoja rota no debe tumbar toda la corrida
        output_text = f"ERROR en el subagente: {exc}"

    return {
        "invoice_id": invoice_id,
        "accessed_by": accessed_by,
        "run_id": str(leaf_run_id),
        "depth": None,  # lo completa _run_node
        "output": output_text,
    }


def _run_node(invoice_ids: list, task_text: str, handler: RunTraceHandler,
              parent_run_id, depth: int, label: str = None) -> list:
    label = label or task_text

    if len(invoice_ids) == 1 or depth >= MAX_DEPTH:
        leaves = []
        for inv in invoice_ids:
            leaf = _run_leaf(inv, task_text, handler, parent_run_id)
            leaf["depth"] = depth
            leaves.append(leaf)
        return leaves

    node_run_id = uuid4()
    groups = _delegate_plan(invoice_ids, label, handler, node_run_id, parent_run_id)

    results = []
    for group in groups:
        group_label = f"{label} / sub-grupo {', '.join(group)}"
        results.extend(_run_node(group, task_text, handler, node_run_id, depth + 1, group_label))
    return results


def run_task(task: str) -> dict:
    handler = RunTraceHandler()

    invoices = mongo_tools.list_issued_invoices()
    invoice_ids = [d["_id"] for d in invoices]

    results = _run_node(invoice_ids, task, handler, parent_run_id=None, depth=0)

    return {"results": results}
