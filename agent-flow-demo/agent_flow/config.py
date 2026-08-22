import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
BILLING_DB_NAME = os.environ.get("BILLING_DB_NAME", "demo_billing")

ROXY_ENABLED = os.environ.get("ROXY_ENABLED", "false").lower() == "true"
ROXY_URL = os.environ.get("ROXY_URL", "http://localhost:8080").rstrip("/")
ROXY_MCP_NAME = os.environ.get("ROXY_MCP_NAME", "invoices-mcp")

# Denegaciones de Roxy que tolera un subagente antes de que se le corte la
# ejecucion. Sin este tope, el agente puede reintentar hasta agotar las
# iteraciones de AgentExecutor (15 por defecto), generando ruido en los logs
# de seguridad por una operacion que Roxy ya rechazo.
MAX_ROXY_DENIALS = int(os.environ.get("MAX_ROXY_DENIALS", "2"))

TRACES_PATH = ROOT_DIR / "traces" / "run.jsonl"
