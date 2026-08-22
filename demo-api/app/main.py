from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.consistency import check_all
from app.db import get_invoices_collection
from app.seed import reset_db, seed_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_if_empty()
    yield


app = FastAPI(title="demo-api", lifespan=lifespan)


@app.get("/invoices")
def list_invoices():
    collection = get_invoices_collection()
    return list(collection.find({}))


@app.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: str):
    collection = get_invoices_collection()
    invoice = collection.find_one({"_id": invoice_id})
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@app.get("/health/consistency")
def health_consistency():
    collection = get_invoices_collection()
    invoices = list(collection.find({}))
    violations = check_all(invoices)
    body = {
        "consistent": len(violations) == 0,
        "checked": len(invoices),
        "violations": violations,
    }
    status_code = 200 if body["consistent"] else 409
    return JSONResponse(content=body, status_code=status_code)


@app.post("/admin/reset")
def admin_reset():
    count = reset_db()
    return {"reset": True, "count": count}
