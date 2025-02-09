from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class ChatMessageType(str, Enum):
    GLOBAL = "global"
    ASSET = "asset"
    DIRECT = "direct"


class PresenceStatus(str, Enum):
    ONLINE = "online"
    AWAY = "away"
    OFFLINE = "offline"


class ChatMessage(BaseModel):
    id: UUID
    text: str
    sender: str
    channel: Optional[str] = None
    type: ChatMessageType
    ipfs_hash: Optional[str] = None
    edited: bool = False
    deleted: bool = False
    timestamp: datetime
    reactions: Optional[Dict[str, List[str]]] = Field(default_factory=dict)


class ChatMessageCreate(BaseModel):
    text: str
    ipfs_hash: Optional[str] = None


class ChatMessageEdit(BaseModel):
    text: str


class ChatChannelInfo(BaseModel):
    name: str
    type: ChatMessageType
    participants: int
    description: Optional[str] = None
    rules: Optional[str] = None
    last_message: Optional[str] = None


class ChatChannelSubscription(BaseModel):
    name: str
    type: ChatMessageType
    unread_count: int
    last_message: Optional[str] = None


class ChatAttachment(BaseModel):
    ipfs_hash: str
    url: str
    type: str
    size: int


class ChatReport(BaseModel):
    reason: str


class ChatPresenceUpdate(BaseModel):
    status: PresenceStatus


class WebSocketMessage(BaseModel):
    type: str
    data: dict