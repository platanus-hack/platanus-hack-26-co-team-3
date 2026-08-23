"""Cliente HTTP contra los servicios de Roxy.

El SDK corre dentro del proceso del cliente, que no tiene -ni deberia
tener- acceso a la base de Roxy: todo sale por HTTP.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

DEFAULT_TIMEOUT = 10


class RoxyUnavailable(Exception):
    """Roxy no pudo emitir un veredicto. No es un permiso: quien llama no
    puede asumir ni allow ni deny."""


@dataclass
class Decision:
    allowed: bool
    reason: str
    response: Optional[Any] = None


class RoxyClient:
    def __init__(self, api_url: str, gateway_url: Optional[str] = None,
                 api_key: Optional[str] = None, timeout: int = DEFAULT_TIMEOUT):
        self.api_url = api_url.rstrip("/")
        self.gateway_url = (gateway_url or "").rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        if api_key:
            self._session.headers["Authorization"] = f"Bearer {api_key}"

    # --- trazabilidad -----------------------------------------------------

    def register_agent(self, *, purpose: str, session_id: str,
                       parent_id: Optional[str] = None) -> Optional[str]:
        """Crea un nodo del arbol y devuelve el id que le asigna Roxy. Ese
        id -no el que traiga el framework- es el que sirve de `parentId` de
        sus hijos.

        Devuelve None ante cualquier fallo: perder una traza no puede
        tumbar el agente que la produce.
        """
        try:
            resp = self._session.post(
                f"{self.api_url}/agents",
                json={"purpose": purpose, "sessionId": session_id, "parentId": parent_id},
                timeout=self.timeout,
            )
            if resp.status_code != 201:
                return None
            return resp.json()["_id"]
        except Exception:
            return None

    def fetch_agents(self, session_id: str) -> List[Dict[str, Any]]:
        resp = self._session.get(
            f"{self.api_url}/agents",
            params={"sessionId": session_id},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    # --- control de acceso ------------------------------------------------

    def evaluate(self, *, mcp_name: str, accessed_by: str, action: str,
                 payload: Dict[str, Any], agent_id: Optional[str] = None) -> Decision:
        """Pregunta al gateway si la accion puede ejecutarse.

        El status HTTP es la decision: 403 deniega, 2xx aprueba. Cualquier
        otra cosa -incluido un 2xx que no sea JSON, que es lo que devuelve
        un CDN cuando el gateway esta caido- levanta RoxyUnavailable en vez
        de dejar pasar.
        """
        if not self.gateway_url:
            raise RoxyUnavailable("no hay gateway_url configurada")

        headers = {"X-Roxy-Agent-Run": agent_id} if agent_id else {}
        try:
            resp = self._session.post(
                f"{self.gateway_url}/v1/evaluate",
                json={"mcpName": mcp_name, "accessedBy": accessed_by,
                      "action": action, "payload": payload},
                headers=headers,
                timeout=60,
            )
        except Exception as exc:
            raise RoxyUnavailable(f"no se pudo alcanzar el gateway: {exc}") from exc

        if resp.status_code == 403:
            return Decision(allowed=False, reason="denegado por Roxy")
        if not resp.ok:
            raise RoxyUnavailable(f"gateway status {resp.status_code}: {resp.text[:200]}")
        try:
            body = resp.json()
        except ValueError:
            raise RoxyUnavailable(
                f"gateway status {resp.status_code} con cuerpo no-JSON "
                f"({resp.headers.get('Content-Type', 'sin content-type')})"
            )
        return Decision(allowed=True, reason="aprobado por Roxy", response=body)
