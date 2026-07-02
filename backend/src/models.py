"""Bug Whisperer — Data Models"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class BugSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BugStatus(str, Enum):
    NEW = "new"
    ANALYZING = "analyzing"
    RESOLVED = "resolved"
    RECALLED = "recalled"  # Fixed via memory recall


class DebugSession(BaseModel):
    """A debugging session capturing a bug encounter"""
    id: str = Field(default_factory=lambda: f"session_{datetime.now().timestamp()}")
    timestamp: datetime = Field(default_factory=datetime.now)
    error_message: str
    stack_trace: str
    language: str = "python"
    files_involved: list[str] = Field(default_factory=list)
    severity: BugSeverity = BugSeverity.MEDIUM


class FixRecord(BaseModel):
    """A recorded fix for a bug"""
    id: str
    session_id: str
    root_cause: str
    fix_description: str
    code_snippet: Optional[str] = None
    files_changed: list[str] = Field(default_factory=list)
    worked: bool = True
    timestamp: datetime = Field(default_factory=datetime.now)


class BugMemoryEntry(BaseModel):
    """Complete memory entry stored in Cognee"""
    error_signature: str  # Unique-ish error fingerprint
    error_message: str
    stack_trace: str
    root_cause: str
    fix_description: str
    code_snippet: Optional[str] = None
    files_involved: list[str] = Field(default_factory=list)
    language: str = "python"
    severity: BugSeverity = BugSeverity.MEDIUM
    occurrences: int = 1
    first_seen: datetime = Field(default_factory=datetime.now)
    last_seen: datetime = Field(default_factory=datetime.now)
    recall_count: int = 0


class RecallResult(BaseModel):
    """Result from memory recall"""
    found: bool
    confidence: float = 0.0
    matched_entries: list[BugMemoryEntry] = Field(default_factory=list)
    suggestion: Optional[str] = None
    reasoning: Optional[str] = None


class NewBugRequest(BaseModel):
    """Request to analyze a new bug"""
    error_message: str
    stack_trace: str = ""
    language: str = "python"
    files_involved: list[str] = Field(default_factory=list)


class FixSubmission(BaseModel):
    """Submit a fix for a bug"""
    session_id: str
    root_cause: str
    fix_description: str
    code_snippet: Optional[str] = None
    files_changed: list[str] = Field(default_factory=list)
    worked: bool = True


class StatsResponse(BaseModel):
    """Dashboard statistics"""
    total_bugs: int = 0
    bugs_resolved: int = 0
    bugs_recalled_from_memory: int = 0
    recall_hit_rate: float = 0.0
    estimated_time_saved_minutes: int = 0
    memory_graph_size: int = 0
