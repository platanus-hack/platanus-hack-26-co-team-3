"""Chequeo de los servicios con los que habla el flujo, antes de gastar
tokens. Sin esto, un servicio caido se manifiesta como un traceback de
urllib3 cuarenta lineas mas abajo, en medio de la corrida.
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
    blocking: bool = True

    def render(self) -> str:
        if self.ok:
            mark = "OK  "
        else:
            mark = "FALLA" if self.blocking else "AVISO"
        line = f"  [{mark}] {self.name}: {self.detail}"
        if not self.ok and self.hint:
            line += f"\n         → {self.hint}"
        return line


def check_demo_api(url: str) -> Check:
    """La API funcional sobre la que trabajan los agentes. Solo se lee."""
    try:
        resp = requests.get(f"{url}/health/consistency", timeout=10)
        body = resp.json()
        return Check("demo-api", True,
                     f"{url} ({body['checked']} facturas, consistente={body['consistent']})")
    except Exception as exc:
        return Check(
            "demo-api", False, f"{url} — {type(exc).__name__}",
            "revisa DEMO_API_URL o si el servicio esta arriba",
        )


def check_roxy() -> Check:
    url = config.ROXY_URL
    try:
        resp = requests.get(f"{url}/health", timeout=15)
        if resp.status_code != 200:
            return Check("roxy-gateway", False, f"{url} devolvio {resp.status_code}",
                         "revisa ROXY_URL o si el gateway esta arriba")
        return Check("roxy-gateway", True, f"{url} — {resp.json()}")
    except Exception as exc:
        return Check("roxy-gateway", False, f"{url} — {type(exc).__name__}",
                     "revisa ROXY_URL o si el gateway esta arriba")


def check_dashboard_api() -> Check:
    """El arbol de delegacion se registra contra /agents; si no responde, la
    corrida igual funciona pero no queda traza para el dashboard."""
    url = config.DASHBOARD_API_URL
    try:
        resp = requests.get(f"{url}/agents", params={"sessionId": "preflight"}, timeout=10)
        if resp.status_code != 200:
            return Check("dashboard API (/agents)", False,
                         f"{url} devolvio {resp.status_code}",
                         "revisa DASHBOARD_API_URL", blocking=False)
        if "application/json" not in resp.headers.get("Content-Type", ""):
            return Check("dashboard API (/agents)", False,
                         f"{url} respondio HTML, no JSON",
                         "el endpoint /agents no esta desplegado en esa URL",
                         blocking=False)
        return Check("dashboard API (/agents)", True, url)
    except Exception as exc:
        return Check("dashboard API (/agents)", False, f"{url} — {type(exc).__name__}",
                     "revisa DASHBOARD_API_URL", blocking=False)


def run_all(demo_api_url: str, with_roxy: bool) -> List[Check]:
    checks = [check_demo_api(demo_api_url), check_dashboard_api()]
    if with_roxy:
        checks.append(check_roxy())
    return checks


def report(checks: List[Check]) -> Optional[str]:
    """Imprime el resultado; devuelve None si todo paso, o el motivo si no."""
    print("Chequeo previo:")
    for c in checks:
        print(c.render())
    bloqueantes = [c for c in checks if not c.ok and c.blocking]
    print()
    if not bloqueantes:
        return None
    return f"{len(bloqueantes)} chequeo(s) fallaron; no se arranca el flujo."
