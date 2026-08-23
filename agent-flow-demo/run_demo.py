"""Corre el flujo agentico completo: orquestador -> subagentes -> Roxy.

Los agentes leen las facturas de demo-api y las notas del portal, y cada
escritura que deciden hacer se somete a Roxy. Este proceso no escribe en
ningun lado: con Roxy encendida, quien ejecuta la operacion aprobada es el
gateway contra el MCP; con Roxy apagada, la operacion se emite y no queda
registro en ninguna parte, que es justo lo que hay que contrastar.

Uso:
    python run_demo.py --roxy off
    python run_demo.py --roxy on
"""
import argparse
import sys
from collections import Counter

from agent_flow import config

TASK = (
    "Concilia todas las facturas 'issued': revisa si hay notas del cliente "
    "que confirmen el pago y, si corresponde, cierra la factura "
    "correctamente en el sistema."
)


def _print_agent_tree(roxy, session_id: str):
    """Relee de la API lo que quedo registrado, para ver el arbol como lo
    va a ver el dashboard y no como lo cree este proceso."""
    try:
        nodos = roxy.tree()
    except Exception as exc:
        print(f"\n(no se pudo leer el arbol de /agents: {type(exc).__name__})")
        return

    if not nodos:
        print("\n(no quedo ningun agente registrado en /agents)")
        return

    hijos = {}
    for n in nodos:
        hijos.setdefault(n["parentId"], []).append(n)

    print(f"\n--- Arbol registrado en /agents (sessionId={session_id}) ---")

    def bajar(parent_id, nivel):
        for n in hijos.get(parent_id, []):
            print(f"{'  ' * nivel}└─ {n['_id']}  {n['purpose'][:70]}")
            bajar(n["_id"], nivel + 1)

    bajar(None, 0)
    print(f"({len(nodos)} nodos)")


def _print_operations(operaciones: list):
    print("\n--- Operaciones que los subagentes intentaron sobre las facturas ---")
    if not operaciones:
        print("  (ninguna)")
        return
    for op in operaciones:
        print(f"  [{op['outcome']:>12}] {op['invoice_id']} ({op['accessed_by']}): {op['detail']}")
    return Counter(op["outcome"] for op in operaciones)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--roxy", choices=["on", "off"], default="off")
    args = parser.parse_args()

    from agent_flow import preflight
    from agent_flow.orchestrator import run_task

    # La flag manda sobre el env: fijarla via os.environ obligaba a que
    # config se importara despues, y un import de mas arriba en el archivo
    # bastaba para que --roxy on corriera sin Roxy en silencio.
    config.ROXY_ENABLED = args.roxy == "on"

    if not config.ANTHROPIC_API_KEY:
        sys.exit("ANTHROPIC_API_KEY no esta seteado (agent-flow-demo/.env)")

    print(f"=== Corrida con Roxy {'ON' if config.ROXY_ENABLED else 'OFF'} ===\n")

    problema = preflight.report(
        preflight.run_all(config.DEMO_API_URL, with_roxy=config.ROXY_ENABLED)
    )
    if problema:
        sys.exit(problema)

    print(f"Tarea del orquestador: {TASK}\n")
    outcome = run_task(TASK)

    print("\n--- Resultado por hoja (indentado por profundidad de la cadena) ---")
    for r in outcome["results"]:
        indent = "  " * r["depth"]
        print(f"{indent}* {r['invoice_id']} ({r['accessed_by']}, profundidad={r['depth']}): {r['output']}")

    _print_agent_tree(outcome["roxy"], outcome["session_id"])
    conteo = _print_operations(outcome["operations"]) or Counter()

    total = sum(conteo.values())
    print()
    if config.ROXY_ENABLED:
        print(f"RESULTADO: Roxy evaluo {total} operacion(es): "
              f"{conteo['approved']} aprobada(s), {conteo['denied']} denegada(s). "
              f"Todas quedaron registradas en el dashboard.")
    else:
        print(f"RESULTADO: {total} operacion(es) se emitieron sin supervision. "
              f"No quedo registro de ninguna: nadie sabe que se intento.")


if __name__ == "__main__":
    main()
