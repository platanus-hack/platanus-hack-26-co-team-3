from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from agent_flow import config


@dataclass
class RoxyDecision:
    decision: str
    reason: str
    violated_rule: Optional[Dict[str, Any]]
    log_id: Optional[str]

    @property
    def allowed(self) -> bool:
        return self.decision == "approved"


def evaluate(
    *,
    accessed_by: str,
    run_id: str,
    action: str,
    payload: Dict[str, Any],
    mcp_name: str = None,
) -> RoxyDecision:
    """POST /v1/evaluate on roxy-gateway. Roxy only judges — it never
    forwards the call to the real MCP, so the caller still has to execute
    the actual write itself once (and if) this returns allowed=True.
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
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    return RoxyDecision(
        decision=body["decision"],
        reason=body.get("reason", ""),
        violated_rule=body.get("violatedRule"),
        log_id=body.get("logId"),
    )
