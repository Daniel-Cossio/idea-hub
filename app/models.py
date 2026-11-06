"""Hito 1: Core Foundation — Pydantic v2 models exactos."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class IdeaStatus(str, Enum):
    INBOX = "inbox"
    REFINING = "refining"
    AGENT_READY = "agent_ready"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    ARCHIVED = "archived"


class IdeaPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IdeaDocument(BaseModel):
    id: str
    slug: str
    title: str
    status: IdeaStatus = IdeaStatus.INBOX
    priority: IdeaPriority = IdeaPriority.MEDIUM
    tags: List[str] = Field(default_factory=list)
    target_stack: List[str] = Field(default_factory=list)
    repo_path: str = ""
    created_at: str
    updated_at: str
    telegram_root_msg_id: Optional[int] = None
    spec_body: str = ""
    capture_log: str = ""


class IdeaCreateRequest(BaseModel):
    title: Optional[str] = None
    raw_input: str
    source_type: str = "text"  # text | voice | link | web
    tags: List[str] = Field(default_factory=list)
    priority: IdeaPriority = IdeaPriority.MEDIUM
    telegram_msg_id: Optional[int] = None


class IdeaUpdateRequest(BaseModel):
    title: Optional[str] = None
    status: Optional[IdeaStatus] = None
    priority: Optional[IdeaPriority] = None
    tags: Optional[List[str]] = None
    target_stack: Optional[List[str]] = None
    repo_path: Optional[str] = None
    spec_body: Optional[str] = None


class IdeaLogAppendRequest(BaseModel):
    entry_text: str
    source_type: str = "note"  # text | voice | link | note | agent
    telegram_msg_id: Optional[int] = None
