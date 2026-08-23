import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

def _env(clave: str, default: str = "") -> str:
    """Una variable presente pero vacia cuenta como no puesta: un
    `DEMO_API_URL=` a medio llenar en el .env no tiene que ganarle al
    default."""
    valor = os.environ.get(clave, "")
    return valor if valor else default


ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = _env("ANTHROPIC_MODEL", "claude-haiku-4-5")

# Los tres servicios con los que habla el flujo. Son URLs y nada mas: este
# bloque no abre bases ni comparte codigo con quien las tiene.
DEMO_API_URL = _env("DEMO_API_URL", "https://roxygt.lat/demo-api").rstrip("/")
DASHBOARD_API_URL = _env("DASHBOARD_API_URL", "https://roxygt.lat/api").rstrip("/")
ROXY_URL = _env("ROXY_URL", "https://roxygt.lat/gateway").rstrip("/")

ROXY_ENABLED = _env("ROXY_ENABLED", "false").lower() == "true"
ROXY_MCP_NAME = _env("ROXY_MCP_NAME", "mongo-catalog-mcp")

# Denegaciones de Roxy que tolera un subagente antes de que se le corte la
# ejecucion. Sin este tope, el agente puede reintentar hasta agotar las
# iteraciones de AgentExecutor (15 por defecto), generando ruido en los logs
# de seguridad por una operacion que Roxy ya rechazo.
MAX_ROXY_DENIALS = int(_env("MAX_ROXY_DENIALS", "2"))
