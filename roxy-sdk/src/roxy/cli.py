"""CLI de Roxy: mirar lo que hicieron los agentes sin escribir codigo.

    roxy check                    los servicios responden?
    roxy runs                     las ultimas corridas
    roxy tree <sessionId>         el arbol de delegacion de una corrida
    roxy logs [--denied]          las decisiones de Roxy
    roxy audit reglas.json        Z3 sobre tus reglas: hay algun hueco?

Apunta al despliegue publico por defecto. `ROXY_API_URL` lo cambia, o
`--api` en cada comando.
"""
import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

import requests

DEFAULT_API = os.environ.get("ROXY_API_URL", "https://roxygt.lat/api").rstrip("/")
DEFAULT_DEMO_API = os.environ.get("ROXY_DEMO_API_URL", "https://roxygt.lat/demo-api").rstrip("/")
DEFAULT_GATEWAY = os.environ.get("ROXY_GATEWAY_URL", "https://roxygt.lat/gateway").rstrip("/")
TIMEOUT = 20

# Sin color si la salida es un pipe: nadie quiere codigos ANSI en un grep.
_TTY = sys.stdout.isatty()


def c(texto: str, codigo: str) -> str:
    return f"\033[{codigo}m{texto}\033[0m" if _TTY else texto


def rojo(t): return c(t, "31")
def verde(t): return c(t, "32")
def gris(t): return c(t, "90")
def negrita(t): return c(t, "1")


def _get(url: str, **params) -> Any:
    resp = requests.get(url, params=params or None, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# --- comandos --------------------------------------------------------------

def cmd_check(args) -> int:
    """Un vistazo a si el stack esta en pie. Util antes de una demo."""
    objetivos = [
        ("dashboard API", f"{args.api}/log?limit=1"),
        ("demo-api", f"{DEFAULT_DEMO_API}/health/consistency"),
        ("gateway", f"{DEFAULT_GATEWAY}/health"),
    ]
    fallo = False
    for nombre, url in objetivos:
        try:
            resp = requests.get(url, timeout=TIMEOUT)
            ok = resp.status_code in (200, 409)  # 409 = datos inconsistentes, no caida
            print(f"  {verde('ok ') if ok else rojo('FALLA')}  {nombre:16s} {gris(str(resp.status_code))}")
            fallo = fallo or not ok
        except Exception as exc:
            print(f"  {rojo('FALLA')}  {nombre:16s} {gris(type(exc).__name__)}")
            fallo = True
    return 1 if fallo else 0


def cmd_runs(args) -> int:
    sesiones: List[Dict[str, Any]] = _get(f"{args.api}/sessions")
    if args.json:
        print(json.dumps(sesiones, indent=2, ensure_ascii=False))
        return 0
    if not sesiones:
        print(gris("  (todavia no hay corridas registradas)"))
        return 0
    for s in sesiones[: args.limit]:
        marca = {"error": rojo("!"), "denied": rojo("!")}.get(s.get("outcome") or "", verde("."))
        print(f"  {marca} {negrita(s['sessionId'])}")
        print(f"     {s['agentCount']:>3} agentes  {gris(s['startedAt'])}")
        print(f"     {gris(s['rootPurpose'][:88])}")
    return 0


def cmd_tree(args) -> int:
    agentes: List[Dict[str, Any]] = _get(f"{args.api}/agents", sessionId=args.session)
    if args.json:
        print(json.dumps(agentes, indent=2, ensure_ascii=False))
        return 0
    if not agentes:
        print(gris(f"  (sin agentes para la sesion {args.session})"))
        return 0

    hijos: Dict[Optional[str], List[Dict[str, Any]]] = {}
    for a in agentes:
        hijos.setdefault(a.get("parentId"), []).append(a)

    def dibujar(padre: Optional[str], prefijo: str = ""):
        rama = hijos.get(padre, [])
        for i, a in enumerate(rama):
            ultimo = i == len(rama) - 1
            print(f"  {gris(prefijo + ('└─ ' if ultimo else '├─ '))}{a['purpose'][:74]}")
            dibujar(a["_id"], prefijo + ("   " if ultimo else "│  "))

    print(f"  {negrita(args.session)}  {gris(f'{len(agentes)} agentes')}")
    dibujar(None)
    return 0


def cmd_logs(args) -> int:
    params: Dict[str, Any] = {"limit": args.limit}
    if args.denied:
        params["status"] = "denied"
    registros: List[Dict[str, Any]] = _get(f"{args.api}/log", **params)
    if args.json:
        print(json.dumps(registros, indent=2, ensure_ascii=False))
        return 0
    for l in registros:
        denegado = l["status"] == "denied"
        etiqueta = rojo("DENEGADO") if denegado else verde("aprobado")
        print(f"  {etiqueta}  {negrita(l['accessedBy'])}  {gris(l.get('mcpName') or '')}")
        print(f"     {l['description'][:96]}")
    return 0


def cmd_audit(args) -> int:
    """Le pasa tus reglas al motor formal: hay alguna accion destructiva que
    se cuele? El motor no esta expuesto publicamente, asi que hace falta
    --engine (o ROXY_ENGINE_URL)."""
    engine = args.engine or os.environ.get("ROXY_ENGINE_URL")
    if not engine:
        print(rojo("  hace falta --engine http://host:8080 (o ROXY_ENGINE_URL)."), file=sys.stderr)
        print(gris("  El verificador no esta expuesto en el despliegue publico;"), file=sys.stderr)
        print(gris("  se levanta con: cd verifier/engine && cargo run"), file=sys.stderr)
        return 2

    try:
        with open(args.reglas, encoding="utf-8") as f:
            datos = json.load(f)
    except FileNotFoundError:
        print(rojo(f"  no encontre {args.reglas}"), file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(rojo(f"  {args.reglas} no es JSON valido: {exc}"), file=sys.stderr)
        return 2

    # Acepta el documento del MCP entero o solo la lista de reglas.
    mcp = datos if isinstance(datos, dict) and "rules" in datos else {
        "id": "cli", "name": "cli", "description": "reglas pasadas por CLI",
        "rules": datos if isinstance(datos, list) else [],
    }
    mcp.setdefault("id", "cli")
    mcp.setdefault("name", "cli")
    mcp.setdefault("description", "reglas pasadas por CLI")

    resp = requests.post(f"{engine.rstrip('/')}/audit", json={"mcp": mcp}, timeout=60)
    if resp.status_code != 200:
        print(rojo(f"  el motor respondio {resp.status_code}: {resp.text[:200]}"), file=sys.stderr)
        return 1
    cuerpo = resp.json()
    if args.json:
        print(json.dumps(cuerpo, indent=2, ensure_ascii=False))
        return 0

    aud = cuerpo.get("policyAudit", {})
    bypass = aud.get("noDestructiveBypass", {})
    muertas = aud.get("deadRules", [])
    conflictos = aud.get("conflicts", [])

    print(f"  {negrita('reglas auditadas')}  {len(mcp.get('rules', []))}")
    if bypass.get("holds"):
        print(f"  {verde('ok ')}  noDestructiveBypass  {gris('ninguna accion destructiva se cuela')}")
    else:
        print(f"  {rojo('FALLA')}  noDestructiveBypass")
        if bypass.get("counterexample"):
            print(f"        {rojo('contraejemplo:')} {bypass['counterexample']}")
    print(f"  {verde('ok ') if not muertas else rojo('FALLA')}  deadRules  "
          f"{gris('ninguna') if not muertas else rojo(str(muertas))}")
    print(f"  {verde('ok ') if not conflictos else rojo('FALLA')}  conflicts  "
          f"{gris('ninguno') if not conflictos else rojo(json.dumps(conflictos))}")

    # Un hueco encontrado es un fallo: sirve para usarlo en CI.
    return 0 if bypass.get("holds", False) and not muertas and not conflictos else 1


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="roxy", description="Mira lo que hicieron tus agentes.")
    p.add_argument("--api", default=DEFAULT_API, help=f"API del dashboard (por defecto {DEFAULT_API})")
    p.add_argument("--json", action="store_true", help="salida JSON cruda")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check", help="los servicios responden?").set_defaults(fn=cmd_check)

    pr = sub.add_parser("runs", help="ultimas corridas de agentes")
    pr.add_argument("-n", "--limit", type=int, default=10)
    pr.set_defaults(fn=cmd_runs)

    pt = sub.add_parser("tree", help="arbol de delegacion de una corrida")
    pt.add_argument("session")
    pt.set_defaults(fn=cmd_tree)

    pl = sub.add_parser("logs", help="decisiones de Roxy")
    pl.add_argument("-n", "--limit", type=int, default=20)
    pl.add_argument("--denied", action="store_true", help="solo las denegadas")
    pl.set_defaults(fn=cmd_logs)

    pa = sub.add_parser("audit", help="Z3 sobre tus reglas: hay algun hueco?")
    pa.add_argument("reglas", help="JSON con el MCP o con la lista de reglas")
    pa.add_argument("--engine", help="URL del verificador (o ROXY_ENGINE_URL)")
    pa.set_defaults(fn=cmd_audit)

    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except requests.RequestException as exc:
        print(rojo(f"  no se pudo alcanzar {args.api}: {exc}"), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
