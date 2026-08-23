import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
BILLING_DB_NAME = os.environ.get("BILLING_DB_NAME", "demo_billing")
ROXY_DB_NAME = os.environ.get("ROXY_DB_NAME", "roxy")

# La API funcional que el flujo agentico ataca (bloque 4). Corre local: es
# la que tiene que quedar inconsistente para que se vea el dano.
DEMO_API_URL = os.environ.get("DEMO_API_URL", "http://localhost:8001").rstrip("/")

# Servicios desplegados. Por defecto se apunta a la nube: una corrida local
# sin configurar nada deja su rastro donde el dashboard lo lee.
DASHBOARD_API_URL = os.environ.get("DASHBOARD_API_URL", "https://roxygt.lat/api").rstrip("/")
ROXY_URL = os.environ.get("ROXY_URL", "https://roxygt.lat/gateway").rstrip("/")

ROXY_ENABLED = os.environ.get("ROXY_ENABLED", "false").lower() == "true"
ROXY_MCP_NAME = os.environ.get("ROXY_MCP_NAME", "invoices-mcp")

# Denegaciones de Roxy que tolera un subagente antes de que se le corte la
# ejecucion. Sin este tope, el agente puede reintentar hasta agotar las
# iteraciones de AgentExecutor (15 por defecto), generando ruido en los logs
# de seguridad por una operacion que Roxy ya rechazo.
MAX_ROXY_DENIALS = int(os.environ.get("MAX_ROXY_DENIALS", "2"))

