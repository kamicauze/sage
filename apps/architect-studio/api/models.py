"""
Pydantic models for API request/response schemas.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from architect.paths import project_manifest_path, root_relative


DEFAULT_MANIFEST_PATH = root_relative(project_manifest_path("sage"))
API_VERSION = "1.1.0"
API_COMPAT = "v1"


# Request Models
class PlanRequest(BaseModel):
    """Request to generate a plan."""
    query: str = Field(..., description="Natural language description of what to build")
    request_type: str = Field(default="feature", description="Type of request: feature, bugfix, refactor")
    manifest_path: str = Field(default=DEFAULT_MANIFEST_PATH, description="Path to project manifest")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")


class GitOptions(BaseModel):
    """Git integration options."""
    auto_commit: bool = Field(default=False, description="Automatically commit after successful build")
    commit_message: Optional[str] = Field(default=None, description="Custom commit message (auto-generated if None)")
    create_branch: Optional[str] = Field(default=None, description="Create and checkout new branch before commit")
    push_to_remote: bool = Field(default=False, description="Push to remote after commit")
    files: Optional[List[str]] = Field(default=None, description="Specific files to commit (None = all changes)")


class BuildRequest(BaseModel):
    """Request to execute a build from an existing plan."""
    manifest_path: str = Field(default=DEFAULT_MANIFEST_PATH, description="Path to project manifest")
    git_options: Optional[GitOptions] = Field(default=None, description="Git integration options")


class MemorySearchRequest(BaseModel):
    """Request to search memory."""
    query: str = Field(..., description="Search query")
    project_id: str = Field(default="sage_brain", description="Project ID to search in")
    n_results: int = Field(default=5, description="Number of results to return")
    zone_filter: Optional[str] = Field(default=None, description="Filter by cognitive zone")


class IngestRequest(BaseModel):
    """Request to ingest files into memory."""
    file_paths: List[str] = Field(..., description="List of file paths to ingest")
    manifest_path: str = Field(default=DEFAULT_MANIFEST_PATH, description="Path to project manifest")


# Response Models
class RoutingDecision(BaseModel):
    """Information about routing decision."""
    route: str = Field(..., description="Routing decision: LOCAL, HYBRID, CLOUD")
    score: int = Field(..., description="Routing score (0-15)")
    reason: str = Field(..., description="Explanation of routing decision")
    provider: str = Field(..., description="Selected provider")
    model: str = Field(..., description="Selected model")
    estimated_cost_min: float = Field(..., description="Minimum estimated cost in USD")
    estimated_cost_max: float = Field(..., description="Maximum estimated cost in USD")


class PlanResponse(BaseModel):
    """Response from plan generation."""
    status: str = Field(..., description="Status: SUCCESS, FAILURE, CANCELLED")
    plan_content: str = Field(..., description="Generated plan content")
    plan_path: str = Field(..., description="Path to saved plan file")
    routing_decision: RoutingDecision = Field(..., description="Routing decision details")
    context_snippets: List[Dict[str, str]] = Field(default=[], description="Retrieved context snippets")
    timing: Optional[Dict[str, Any]] = Field(default=None, description="Plan timing metadata")
    summary: str = Field(..., description="Summary message")
    api_version: str = Field(default=API_VERSION, description="API version marker")
    api_compat: str = Field(default=API_COMPAT, description="Backward compatibility marker")


class BuildResponse(BaseModel):
    """Response from build execution."""
    status: str = Field(..., description="Status: SUCCESS, FAILURE, CANCELLED")
    artifacts: List[str] = Field(..., description="Paths to generated artifacts")
    files_built: List[str] = Field(default=[], description="List of files that were built")
    files_skipped: List[Dict[str, Any]] = Field(default=[], description="List of skipped files with reason")
    files_failed: List[Dict[str, Any]] = Field(default=[], description="List of failed file operations with error")
    test_results: Optional[Dict[str, Any]] = Field(default=None, description="Test execution results")
    timing: Optional[Dict[str, Any]] = Field(default=None, description="Build timing metadata")
    build_details: Optional[Dict[str, Any]] = Field(default=None, description="Detailed build telemetry")
    summary: str = Field(..., description="Summary message")
    git_result: Optional[Dict[str, Any]] = Field(default=None, description="Git operation results if auto-commit enabled")
    api_version: str = Field(default=API_VERSION, description="API version marker")
    api_compat: str = Field(default=API_COMPAT, description="Backward compatibility marker")


class UsageStats(BaseModel):
    """Usage and budget statistics."""
    current_month: str = Field(..., description="Current month in YYYY-MM format")
    monthly_spend: float = Field(..., description="Total spend this month in USD")
    monthly_limit: float = Field(..., description="Monthly budget limit in USD")
    daily_spend: float = Field(..., description="Spend today in USD")
    daily_limit: float = Field(..., description="Daily burst limit in USD")
    budget_percentage: float = Field(..., description="Percentage of monthly budget used")
    recent_calls: List[Dict[str, Any]] = Field(default=[], description="Recent API calls")


class MemoryStats(BaseModel):
    """Memory system statistics."""
    project_id: str = Field(..., description="Project ID")
    total_chunks: int = Field(..., description="Total number of chunks stored")
    zones: Dict[str, int] = Field(..., description="Chunk count by zone")
    collection_exists: bool = Field(..., description="Whether collection exists")


class MemorySearchResult(BaseModel):
    """Single search result from memory."""
    content: str = Field(..., description="Content snippet")
    source: str = Field(..., description="Source file path")
    zone_name: str = Field(..., description="Cognitive zone name")
    role: str = Field(..., description="Zone role")
    distance: float = Field(..., description="Similarity distance")


class MemorySearchResponse(BaseModel):
    """Response from memory search."""
    results: List[MemorySearchResult] = Field(..., description="Search results")
    query: str = Field(..., description="Original search query")
    total_results: int = Field(..., description="Total number of results")


class HealthResponse(BaseModel):
    """API health check response."""
    status: str = Field(..., description="API status")
    timestamp: datetime = Field(..., description="Current timestamp")
    architect_version: str = Field(default="1.0.0", description="Architect version")


class ErrorResponse(BaseModel):
    """Error response."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(default=None, description="Detailed error information")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")
