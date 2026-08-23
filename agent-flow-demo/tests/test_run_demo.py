"""La flag --roxy decide si el flujo consulta a Roxy.

Vivio rota un rato: run_demo fijaba ROXY_ENABLED via os.environ contando
con que config se importara despues, y un import de mas arriba en el
archivo bastaba para que `--roxy on` corriera sin Roxy en silencio.
"""
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def cabecera(flag: str) -> str:
    """Corre run_demo hasta el chequeo previo y devuelve lo que imprimio.
    Falla en el preflight (no hay servicios en el test), que es justo lo
    que lo hace barato: no gasta tokens ni toca la base."""
    res = subprocess.run(
        [sys.executable, "run_demo.py", "--roxy", flag],
        cwd=RAIZ, capture_output=True, text=True, timeout=120,
        env={"PATH": "/usr/bin:/bin",
             "DEMO_API_URL": "http://127.0.0.1:1",
             "DASHBOARD_API_URL": "http://127.0.0.1:1",
             "ROXY_URL": "http://127.0.0.1:1",
             "ANTHROPIC_API_KEY": "sk-test"},
    )
    return res.stdout


def test_on_dice_on():
    assert "Roxy ON" in cabecera("on")


def test_off_dice_off():
    assert "Roxy OFF" in cabecera("off")


def test_con_roxy_se_chequea_el_gateway():
    """Con la flag encendida el preflight tiene que mirar el gateway; si
    no lo mira, la flag no llego a ningun lado."""
    assert "roxy-gateway" in cabecera("on")


def test_sin_roxy_no_se_chequea_el_gateway():
    assert "roxy-gateway" not in cabecera("off")
