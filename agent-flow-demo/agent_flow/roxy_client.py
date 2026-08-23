from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from agent_flow import config


class RoxyUnavailable(Exception):
    """Roxy no pudo emitir un veredicto (evaluator caido, MCP caido, MCP
    inexistente). No es un permiso: no se puede asumir ni allow ni deny."""


@dataclass
class RoxyDecision:
    allowed: bool
    reason: str
    mcp_response: Optional[Any]


def evaluate(
    *,
    accessed_by: str,
    run_id: str,
    action: str,
    payload: Dict[str, Any],
    mcp_name: str = None,
) -> RoxyDecision:
    """POST /v1/evaluate en roxy-gateway.

    Contrato V2 (roxy-gateway/README.md): Roxy ya no devuelve un JSON de
    decision. Segun el veredicto del evaluator, o corta con 403, o le pega
    al MCP el mismo (inyectando credenciales, que nunca vuelven al agente) y
    devuelve la respuesta cruda del MCP. El status HTTP ES la decision.
    """
    resp = requests.post(
        f"{config.ROXY_URL}/v1/evaluate",
        json={
            "mcpName": mcp_name or config.ROXY_MCP_NAME,
            "accessedBy": accessed_by,
            "action": action,
            "payload": payload,
        },
        headers={"X-Roxy-Agent-Run": run_id},
        timeout=60,
    )

    if resp.status_code == 403:
        return RoxyDecision(allowed=False, reason="denegado por Roxy", mcp_response=None)

    if resp.status_code in (502, 503, 404):
        raise RoxyUnavailable(f"roxy status {resp.status_code}: {resp.text[:200]}")

    resp.raise_for_status()

    try:
        body = resp.json()
    except ValueError:
        body = resp.text

    return RoxyDecision(allowed=True, reason="aprobado por Roxy", mcp_response=body)
