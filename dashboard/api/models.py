from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SecurityStatus(str, Enum):
    approved = "approved"
    denied = "denied"


class ViolatedRule(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    priority: int
    instruction: str


class SecurityLog(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    status: SecurityStatus
    mcp_id: Optional[str] = Field(default=None, alias="mcpId")
    mcp_name: Optional[str] = Field(default=None, alias="mcpName")
    time: datetime
    accessed_by: str = Field(alias="accessedBy")
    action: Optional[str] = None
    violated_rule: Optional[ViolatedRule] = Field(default=None, alias="violatedRule")
    description: str


class SecurityLogCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: SecurityStatus
    mcp_id: Optional[str] = Field(default=None, alias="mcpId")
    mcp_name: Optional[str] = Field(default=None, alias="mcpName")
    accessed_by: str = Field(alias="accessedBy")
    action: Optional[str] = None
    violated_rule: Optional[ViolatedRule] = Field(default=None, alias="violatedRule")
    description: str
    time: datetime


class Agent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    purpose: str
    parent_id: Optional[str] = Field(default=None, alias="parentId")
    session_id: str = Field(alias="sessionId")


class AgentCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    purpose: str
    parent_id: Optional[str] = Field(default=None, alias="parentId")
    session_id: str = Field(alias="sessionId")


class Session(BaseModel):
    """One row per distinct `sessionId` in `agents`, aggregated server-side.

    `startedAt` isn't a stored field anywhere -- `agents` has no timestamp
    at all -- it's the real creation time embedded in the root agent's
    ObjectId (the first-inserted doc per session, since agent_flow always
    registers the orchestrator/root before any child). Not invented data,
    just read out of the id Mongo already assigned.
    """

    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(alias="sessionId")
    root_purpose: str = Field(alias="rootPurpose")
    agent_count: int = Field(alias="agentCount")
    started_at: datetime = Field(alias="startedAt")
