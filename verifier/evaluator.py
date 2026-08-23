"""Fallback local del bloque 10. NO es la implementacion del bloque.

El motor real es `engine/` (Rust): compila las reglas a una politica formal,
decide de forma determinista sobre ella y la audita con Z3. Ese es el que
corre en produccion. Este archivo existe solo para tener a quien preguntarle
en local cuando no hay toolchain de Rust a mano, y cubre unicamente el
escenario de facturas de la demo.

OJO: este fallback NO habla el contrato actual del gateway. El gateway manda
{rules, prompt} (roxy-gateway/internal/policy/remote.go) y esto espera
{mcp, request, time}, asi que responde 422 y el gateway lo traduce a 503.
Ver research/ISSUES.md.

Contrato con el gateway (roxy-gateway/internal/policy/remote.go):

    entra {"mcp": {...rules}, "request": {accessedBy, action, payload}, "time"}
    sale  {"allowed": bool, "violatedPriority": int|null, "reason": str}

Esta version comprueba los invariantes de facturacion sobre el payload. El
objetivo del bloque es traducir reglas y contexto a Z3 y resolverlo ahi; el
contrato de entrada y salida no cambia cuando eso llegue.

    uvicorn evaluator:app --port 9000
"""
from typing import Any, Dict, Optional, Tuple

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="roxy-verifier")


class Attempt(BaseModel):
    accessedBy: str
    action: str
    payload: Optional[Any] = None


class EvaluateRequest(BaseModel):
    mcp: Dict[str, Any]
    request: Attempt
    time: Optional[str] = None


def _total_no_cuadra(payload: Dict[str, Any]) -> Optional[str]:
    total = payload.get("proposedTotal")
    suma = payload.get("computedSubtotalSum")
    if total is None or suma is None or float(total) == float(suma):
        return None
    return f"proposedTotal ({total}) no coincide con computedSubtotalSum ({suma})"


def _pagada_sin_auditoria(payload: Dict[str, Any]) -> Optional[str]:
    if payload.get("proposedStatus") != "paid" or payload.get("appendsAuditLog"):
        return None
    return "marcar la factura como 'paid' sin dejar registro de auditoria"


# El orden es el de las prioridades del MCP: el gateway reporta una sola
# regla violada, y tiene que ser la primera que aplique.
COMPROBACIONES: Tuple = (
    (1, _total_no_cuadra),
    (2, _pagada_sin_auditoria),
)


@app.post("/evaluate")
def evaluate(body: EvaluateRequest):
    payload = body.request.payload if isinstance(body.request.payload, dict) else {}

    for prioridad, comprobar in COMPROBACIONES:
        motivo = comprobar(payload)
        if motivo:
            return {"allowed": False, "violatedPriority": prioridad, "reason": motivo}

    return {"allowed": True, "violatedPriority": None,
            "reason": "el contexto no cae bajo ninguna regla del MCP"}


@app.get("/health")
def health():
    return {"service": "roxy-verifier", "status": "ok"}
