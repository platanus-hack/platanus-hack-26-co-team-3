"""Chequeo de las dependencias externas del flujo antes de gastar tokens.

Sin esto, una dependencia caida se manifiesta como un traceback de urllib3
cuarenta lineas mas abajo, en medio de la corrida.
"""
from dataclasses import dataclass
from typing import List, Optional

import requests

from agent_flow import config


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    hint: str = ""

    def render(self) -> str:
        mark = "OK  " if self.ok else "FALLA"
        line = f"  [{mark}] {self.name}: {self.detail}"
        if not self.ok and self.hint:
            line += f"\n         → {self.hint}"
        return line


def check_mongo() -> Check:
    try:
        from pymongo import MongoClient
        client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        return Check("Mongo local", True, config.MONGO_URI)
    except Exception as exc:
        return Check(
            "Mongo local", False, f"{type(exc).__name__}: {str(exc)[:80]}",
            "cd mongo-data && ./run.sh",
        )


def check_demo_api(url: str) -> Check:
    try:
        resp = requests.get(f"{url}/health/consistency", timeout=5)
        body = resp.json()
        return Check("demo-api", True,
                     f"{url} ({body['checked']} facturas, consistente={body['consistent']})")
    except Exception as exc:
        return Check(
            "demo-api", False, f"{url} — {type(exc).__name__}",
            "cd demo-api && ./run.sh",
        )


def check_roxy() -> Check:
    url = config.ROXY_URL
    try:
        resp = requests.get(f"{url}/health", timeout=15)
        if resp.status_code != 200:
            return Check(
                "roxy-gateway", False, f"{url} devolvio {resp.status_code}",
                "si es la nube, el servicio esta caido; para local: "
                "cd roxy-gateway && go run ./cmd/roxy",
            )
        return Check("roxy-gateway", True, f"{url} — {resp.json()}")
    except Exception as exc:
        return Check(
            "roxy-gateway", False, f"{url} — {type(exc).__name__}",
            "cd roxy-gateway && go run ./cmd/roxy (o apunta ROXY_URL a la nube)",
        )


def check_mcp_registered() -> Check:
    """El MCP tiene que existir en la base que lee la Roxy configurada. Con
    ROXY_URL apuntando a la nube, esta comprobacion mira la base local y no
    dice nada de Atlas: solo sirve cuando Roxy tambien es local."""
    try:
        from pymongo import MongoClient
        client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=3000)
        doc = client["roxy"]["mcps"].find_one({"name": config.ROXY_MCP_NAME})
        if doc is None:
            return Check(
                f"MCP '{config.ROXY_MCP_NAME}' (en Mongo local)", False, "no registrado",
                "python3 scripts/register_invoices_mcp.py",
            )
        return Check(f"MCP '{config.ROXY_MCP_NAME}' (en Mongo local)", True,
                     f"{len(doc.get('rules', []))} reglas")
    except Exception as exc:
        return Check(f"MCP '{config.ROXY_MCP_NAME}'", False,
                     f"{type(exc).__name__}", "revisa Mongo primero")


def run_all(demo_api_url: str, with_roxy: bool) -> List[Check]:
    checks = [check_mongo(), check_demo_api(demo_api_url)]
    if with_roxy:
        checks.append(check_roxy())
        checks.append(check_mcp_registered())
    return checks


def report(checks: List[Check]) -> Optional[str]:
    """Imprime el resultado; devuelve None si todo paso, o el motivo si no."""
    print("Chequeo previo:")
    for c in checks:
        print(c.render())
    failed = [c for c in checks if not c.ok]
    if not failed:
        print()
        return None
    return f"{len(failed)} chequeo(s) fallaron; no se arranca el flujo."
