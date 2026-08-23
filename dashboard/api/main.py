from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pymongo import DESCENDING, ReturnDocument

from db import get_agents_collection, get_security_collection
from models import (
    Agent,
    AgentCreate,
    AgentOutcomeUpdate,
    SecurityLog,
    SecurityLogCreate,
    SecurityStatus,
    Session,
)

app = FastAPI(title="Roxy Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/log", response_model=list[SecurityLog])
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


@app.post("/log", status_code=201, response_model=SecurityLog)
def create_security_log(payload: SecurityLogCreate):
    doc = payload.model_dump(by_alias=True, exclude={"mcp_id"})
    if payload.mcp_id is not None:
        try:
            doc["mcpId"] = ObjectId(payload.mcp_id)
        except InvalidId:
            raise HTTPException(status_code=400, detail="mcpId is not a valid ObjectId")

    collection = get_security_collection()
    result = collection.insert_one(doc)

    doc["_id"] = str(result.inserted_id)
    if doc.get("mcpId") is not None:
        doc["mcpId"] = str(doc["mcpId"])
    return SecurityLog.model_validate(doc)


@app.post("/agents", status_code=201, response_model=Agent)
def create_agent(payload: AgentCreate):
    doc = payload.model_dump(by_alias=True, exclude={"parent_id"})
    doc["parentId"] = None
    if payload.parent_id is not None:
        try:
            doc["parentId"] = ObjectId(payload.parent_id)
        except InvalidId:
            raise HTTPException(status_code=400, detail="parentId is not a valid ObjectId")

    collection = get_agents_collection()
    result = collection.insert_one(doc)

    doc["_id"] = str(result.inserted_id)
    if doc.get("parentId") is not None:
        doc["parentId"] = str(doc["parentId"])
    return Agent.model_validate(doc)


@app.patch("/agents/{agent_id}", response_model=Agent)
def update_agent_outcome(agent_id: str, payload: AgentOutcomeUpdate):
    try:
        object_id = ObjectId(agent_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="agent_id is not a valid ObjectId")

    collection = get_agents_collection()
    doc = collection.find_one_and_update(
        {"_id": object_id},
        {"$set": {"outcome": payload.outcome.value}},
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="agent not found")

    doc["_id"] = str(doc["_id"])
    if doc.get("parentId") is not None:
        doc["parentId"] = str(doc["parentId"])
    return Agent.model_validate(doc)


@app.get("/agents", response_model=list[Agent])
def list_agents_by_session(session_id: str = Query(alias="sessionId")):
    collection = get_agents_collection()
    cursor = collection.find({"sessionId": session_id})

    agents = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])
        if doc.get("parentId") is not None:
            doc["parentId"] = str(doc["parentId"])
        agents.append(Agent.model_validate(doc))
    return agents


@app.get("/sessions", response_model=list[Session])
def list_sessions(limit: int = Query(default=50, ge=1, le=500)):
    collection = get_agents_collection()
    pipeline = [
        {"$sort": {"_id": 1}},
        {
            "$group": {
                "_id": "$sessionId",
                "agentCount": {"$sum": 1},
                # agent_flow always registers the root/orchestrator agent
                # before any child (its id is the parentId children need),
                # so within a session group the earliest _id is the root.
                "rootPurpose": {"$first": "$purpose"},
                "rootId": {"$first": "$_id"},
                "outcomes": {"$push": "$outcome"},
            }
        },
        {"$sort": {"rootId": -1}},
        {"$limit": limit},
    ]

    outcome_rank = {"error": 2, "denied": 1, "ok": 0}
    sessions = []
    for doc in collection.aggregate(pipeline):
        recorded = [o for o in doc["outcomes"] if o is not None]
        worst = max(recorded, key=lambda o: outcome_rank.get(o, -1)) if recorded else None
        sessions.append(
            Session.model_validate(
                {
                    "sessionId": doc["_id"],
                    "rootPurpose": doc["rootPurpose"],
                    "agentCount": doc["agentCount"],
                    "startedAt": doc["rootId"].generation_time,
                    "outcome": worst,
                }
            )
        )
    return sessions
