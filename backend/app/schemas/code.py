from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict


# codesession schemas
class CodeSessionCreate(BaseModel):
    name: str
    description: Optional[str] = None


class CodeSessionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class CodeSessionResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    user_id: int
    is_active: bool
    last_accessed: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# codefile schemas
class CodeFileCreate(BaseModel):
    name: str
    path: str
    content: str = ""
    file_type: str = "python"


class CodeFileUpdate(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None
    content: Optional[str] = None
    file_type: Optional[str] = None


class CodeFileResponse(BaseModel):
    id: int
    name: str
    path: str
    content: str
    file_type: str
    session_id: int
    size_bytes: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# codeexecution schemas
class CodeExecutionCreate(BaseModel):
    session_id: int
    code: Optional[str] = None  # For direct code execution
    command: Optional[str] = None  # For terminal commands
    input_data: Optional[str] = None
    language: Optional[str] = "python"  # Default to Python


# codeexecutionrequest schema - used for the /code/execute endpoint
class CodeExecutionRequest(BaseModel):
    session_id: int
    code: str
    language: str = "python"
    input_data: Optional[str] = None


class CodeExecutionResponse(BaseModel):
    id: int
    session_id: int
    command: str
    input_data: Optional[str]
    output: Optional[str]
    error: Optional[str]
    exit_code: Optional[int]
    execution_time_ms: Optional[float]
    memory_usage_mb: Optional[float]
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# codesubmission schemas
class CodeSubmissionCreate(BaseModel):
    session_id: Optional[int] = None
    file_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    code_content: str


class CodeSubmissionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None


class CodeSubmissionResponse(BaseModel):
    id: int
    session_id: Optional[int] = None
    file_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    code_content: str
    submitter_id: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# codereview schemas
class CodeReviewCreate(BaseModel):
    status: str  # approved, rejected, revision_requested
    comments: Optional[str] = None
    feedback: Optional[str] = None
    quality_before_edits: Optional[int] = None  # 1-5 rating scale
    quality_after_edits: Optional[int] = None  # 1-5 rating scale
    edits_made: Optional[str] = None  # descriptoin of edits made
    is_customer_ready: Optional[bool] = None  # if task is good enough to send to customer


class CodeReviewUpdate(BaseModel):
    status: Optional[str] = None
    comments: Optional[str] = None
    feedback: Optional[str] = None
    quality_before_edits: Optional[int] = None
    quality_after_edits: Optional[int] = None
    edits_made: Optional[str] = None
    is_customer_ready: Optional[bool] = None
    review_time_minutes: Optional[float] = None


class CodeReviewResponse(BaseModel):
    id: int
    submission_id: int
    reviewer_id: int
    status: str
    comments: Optional[str]
    feedback: Optional[str]
    quality_before_edits: Optional[int]
    quality_after_edits: Optional[int]
    edits_made: Optional[str]
    is_customer_ready: Optional[bool]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# terminal/WebSocket schemas
class TerminalCommand(BaseModel):
    command: str
    session_id: int
    input_data: Optional[str] = None


class TerminalResponse(BaseModel):
    output: Optional[str] = None
    error: Optional[str] = None
    exit_code: Optional[int] = None
    execution_time_ms: Optional[float] = None
    status: str  # running, completed, failed, timeout


# file system operation schemas
class FileSystemOperation(BaseModel):
    operation: str  # ls, cat, mkdir, rm, etc.
    path: str
    session_id: int
    content: Optional[str] = None  # write operations


class FileSystemResponse(BaseModel):
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    files: Optional[List[Dict[str, Any]]] = None  # ls operations


# more code review Scchemas
class CodeSubmissionListResponse(BaseModel):
    """Response schema for code submission list"""

    id: int
    title: str
    description: Optional[str]
    submitter_id: int
    status: str
    created_at: datetime
    code_content: str  # code content for review

    model_config = ConfigDict(from_attributes=True)
