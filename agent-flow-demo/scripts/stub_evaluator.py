"""Evaluator de mentira para probar la cadena agente -> Roxy en local.

NO es el bloque 10. El verificador real (Sebastian) traduce reglas y
contexto a Z3; esto aplica dos invariantes de facturacion a mano para que
`roxy-gateway` tenga a quien preguntarle mientras ese bloque no exista.
No usarlo en la demo ni desplegarlo.

Contrato (roxy-gateway/internal/policy/remote.go):
  entra {"mcp": {...rules}, "request": {accessedBy, action, payload}, "time"}
  sale  {"allowed": bool, "violatedPriority": int|null, "reason": str}

Uso:
    uvicorn scripts.stub_evaluator:app --port 9000
    # y en roxy-gateway: EVALUATOR_URL=http://localhost:9000/evaluate
"""
from typing import Any, Dict

from fastapi import FastAPI

app = FastAPI(title="stub-evaluator")


@app.post("/evaluate")
def evaluate(body: Dict[str, Any]):
    request = body.get("request") or {}
    payload = request.get("payload") or {}

    total = payload.get("proposedTotal")
    suma = payload.get("computedSubtotalSum")
    if total is not None and suma is not None and float(total) != float(suma):
        return {
            "allowed": False,
            "violatedPriority": 1,
            "reason": f"proposedTotal ({total}) no coincide con computedSubtotalSum ({suma})",
        }

    if payload.get("proposedStatus") == "paid" and not payload.get("appendsAuditLog"):
        return {
            "allowed": False,
            "violatedPriority": 2,
            "reason": "marcar 'paid' sin registro de auditoria",
        }

    return {"allowed": True, "violatedPriority": None, "reason": "cumple las reglas evaluadas"}


@app.get("/health")
def health():
    return {"service": "stub-evaluator", "status": "ok"}
