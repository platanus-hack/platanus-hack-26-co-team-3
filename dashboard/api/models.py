from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SecurityStatus(str, Enum):
    approved = "approved"
    denied = "denied"


class SecurityLog(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    status: SecurityStatus
    mcp_id: Optional[str] = Field(default=None, alias="mcpId")
    mcp_name: Optional[str] = Field(default=None, alias="mcpName")
    time: datetime
    accessed_by: str = Field(alias="accessedBy")
    description: str
