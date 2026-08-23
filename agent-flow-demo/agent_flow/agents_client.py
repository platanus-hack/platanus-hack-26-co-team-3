"""Registro del arbol de delegacion contra la API del dashboard (bloque 3).

`POST /agents` devuelve el `_id` que Mongo le asigna al nodo, y ese id es
el que hay que mandar como `parentId` de sus hijos: la API valida que sea
un ObjectId, asi que un id inventado por nosotros no sirve. Eso obliga a
registrar de arriba hacia abajo -- el padre existe antes que el hijo.

La trazabilidad no es la tarea: si la API no responde, se devuelve None y
el flujo sigue sin arbol en vez de caerse.
"""
from typing import Optional
from uuid import uuid4

import requests

from agent_flow import config


def new_session_id() -> str:
    """Agrupa todos los nodos de una corrida. `sessionId` es texto libre en
    el esquema, asi que un UUID entra sin problema."""
    return str(uuid4())


def register(*, purpose: str, session_id: str, parent_id: Optional[str] = None) -> Optional[str]:
    """Crea un nodo de agente. Devuelve su `_id`, o None si no se pudo."""
    try:
        resp = requests.post(
            f"{config.DASHBOARD_API_URL}/agents",
            json={"purpose": purpose, "sessionId": session_id, "parentId": parent_id},
            timeout=10,
        )
        if resp.status_code != 201:
            print(f"  [trace] /agents devolvio {resp.status_code}: {resp.text[:120]}")
            return None
        return resp.json()["_id"]
    except Exception as exc:
        print(f"  [trace] no se pudo registrar el agente: {type(exc).__name__}")
        return None


def fetch_tree(session_id: str) -> list:
    """Los nodos de una corrida, como los ve el dashboard."""
    resp = requests.get(
        f"{config.DASHBOARD_API_URL}/agents",
        params={"sessionId": session_id},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()
