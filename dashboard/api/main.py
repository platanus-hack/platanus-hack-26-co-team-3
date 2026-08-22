from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pymongo import DESCENDING

from db import get_security_collection
from models import SecurityLog, SecurityStatus

app = FastAPI(title="Roxy Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/security-logs", response_model=list[SecurityLog])
def list_security_logs(
    status: Optional[SecurityStatus] = None,
    mcp_id: Optional[str] = Query(default=None, alias="mcpId"),
    accessed_by: Optional[str] = Query(default=None, alias="accessedBy"),
    limit: int = Query(default=50, ge=1, le=500),
    skip: int = Query(default=0, ge=0),
):
    query: dict = {}
    if status is not None:
        query["status"] = status.value
    if mcp_id is not None:
        try:
            query["mcpId"] = ObjectId(mcp_id)
        except InvalidId:
            raise HTTPException(status_code=400, detail="mcpId is not a valid ObjectId")
    if accessed_by is not None:
        query["accessedBy"] = accessed_by

    collection = get_security_collection()
    cursor = (
        collection.find(query)
        .sort("time", DESCENDING)
        .skip(skip)
        .limit(limit)
    )

    logs = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])
        if doc.get("mcpId") is not None:
            doc["mcpId"] = str(doc["mcpId"])
        logs.append(SecurityLog.model_validate(doc))
    return logs
