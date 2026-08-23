"""Cliente del gateway de Roxy.

El SDK (`roxy-guard`) se sigue usando para el arbol de agentes, pero para el
veredicto hace falta este cliente: da por sentado que una aprobacion viene en
JSON y que una denegacion llega como 403, y en el despliegue no pasa ninguna
de las dos cosas.

- CloudFront remapea 403 y 404 a 200 con /index.html para toda la
  distribucion (infra/main.tf), asi que la denegacion llega como el HTML del
  dashboard. Que el MCP existe se comprueba en el chequeo previo; a partir de
  ahi, ese HTML solo puede ser una denegacion.
- El MCP de Mongo contesta por event-stream, no por JSON.
"""
from dataclasses import dataclass

import requests

from agent_flow import config

TIMEOUT = 120


class GatewayUnavailable(Exception):
    """Roxy no pudo emitir un veredicto. No es un permiso: quien llama no
    puede asumir ni allow ni deny."""


@dataclass
class Verdict:
    allowed: bool
    reason: str
    evidence: str = ""


def evaluate(*, action: str, payload: dict, accessed_by: str, mcp_name: str) -> Verdict:
    try:
        resp = requests.post(
            f"{config.ROXY_URL}/v1/evaluate",
            json={"mcpName": mcp_name, "accessedBy": accessed_by,
                  "action": action, "payload": payload},
            timeout=TIMEOUT,
        )
    except Exception as exc:
        raise GatewayUnavailable(f"no se pudo alcanzar el gateway: {exc}") from exc

    if resp.status_code == 403:
        return Verdict(allowed=False, reason="denegado por Roxy")

    if not resp.ok:
        raise GatewayUnavailable(f"gateway status {resp.status_code}: {resp.text[:200]}")

    if "text/html" in resp.headers.get("Content-Type", ""):
        return Verdict(allowed=False,
                       reason="denegado por Roxy (403 enmascarado por CloudFront)")

    return Verdict(allowed=True, reason="aprobado por Roxy y ejecutado contra el MCP",
                   evidence=resp.text[:300])


def mcp_reachable(mcp_name: str) -> bool:
    """Somete una lectura inofensiva para saber si el MCP existe y contesta.

    Es lo unico que separa "lo denegaron" de "ese MCP no esta registrado":
    los dos casos llegan como el mismo HTML. Se hace una vez, en el chequeo
    previo, y despues ese HTML ya solo puede ser una denegacion.
    """
    try:
        veredicto = evaluate(
            action="read",
            payload={"intent": "read-only query listing the collections"},
            accessed_by="roxy-preflight",
            mcp_name=mcp_name,
        )
    except GatewayUnavailable:
        return False
    return veredicto.allowed
