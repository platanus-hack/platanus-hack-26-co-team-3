import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.consistency import check_all
from app.db import get_invoices_collection
from app.seed import reset_db, seed_if_empty

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        seed_if_empty()
    except Exception:
        # Startup seeding is a convenience, not a hard requirement: if Mongo is
        # briefly unreachable at boot, the app should still come up (routes will
        # surface the real error per-request) instead of refusing to start at all.
        logger.exception("startup seeding failed; continuing so the API can still serve requests")
    yield


app = FastAPI(title="demo-api", lifespan=lifespan)

# The dashboard reads /health/consistency straight from the browser to show
# the damage next to the agent tree, so the browser needs these headers.
# Read-only endpoints, public data, no credentials -- nothing here is secret;
# this API is the deliberately-unprotected victim in the demo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5183",
        "https://roxygt.lat",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


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
