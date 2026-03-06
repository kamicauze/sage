from __future__ import annotations

from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from architect.api.routes.google_workspace import extract_google_drive_file_id, get_drive_file_metadata
from shared.project_control import (
    current_node_id,
    enqueue_mirror_task,
    get_project_snapshot,
    handoff_project,
    list_project_google_assets,
    process_mirror_queue,
    project_status,
    run_project_chat,
    sync_project_snapshot,
    summarize_catalog,
    upsert_project_google_asset,
    upsert_node,
)

router = APIRouter(prefix="/project-control", tags=["project-control"])


class NodeConfigRequest(BaseModel):
    node_id: str = Field(..., min_length=1, max_length=80)
    label: Optional[str] = Field(default=None, max_length=120)
    transport: Literal["local", "ssh"] = "ssh"
    ssh_host: Optional[str] = Field(default=None, max_length=255)
    ssh_user: Optional[str] = Field(default=None, max_length=120)
    ssh_command: Optional[str] = Field(default=None, max_length=255)
    host: Optional[str] = Field(default=None, max_length=255)
    backup_repo_root: Optional[str] = Field(default=None, max_length=500)
    git_host: Optional[str] = Field(default=None, max_length=255)
    git_user: Optional[str] = Field(default=None, max_length=120)


class ProjectRegisterRequest(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=120)
    repo_path: str = Field(..., min_length=1, max_length=1000)
    aliases: List[str] = Field(default_factory=list, max_length=12)
    node_id: Optional[str] = Field(default=None, max_length=80)


class ProjectSyncRequest(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=120)
    repo_path: Optional[str] = Field(default=None, max_length=1000)
    aliases: List[str] = Field(default_factory=list, max_length=12)
    node_id: Optional[str] = Field(default=None, max_length=80)


class ProjectHandoffRequest(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=120)
    source_node: Optional[str] = Field(default=None, max_length=80)
    target_node: Optional[str] = Field(default=None, max_length=80)


class ProjectGoogleAssetRequest(BaseModel):
    drive_url: Optional[str] = Field(default=None, max_length=2000)
    asset_id: Optional[str] = Field(default=None, max_length=255)
    title: Optional[str] = Field(default=None, max_length=255)
    kind: Optional[str] = Field(default=None, max_length=80)
    mime_type: Optional[str] = Field(default=None, max_length=255)
    role: Optional[str] = Field(default=None, max_length=120)
    source: str = Field(default="google_drive", max_length=80)


class ProjectChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(..., min_length=1, max_length=12000)


class ProjectChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=12000)
    project_id: str = Field(..., min_length=1, max_length=120)
    preferred_node: Optional[str] = Field(default=None, max_length=80)
    executor: Literal["codex_cli", "claude_cli"] = "codex_cli"
    history: List[ProjectChatMessage] = Field(default_factory=list, max_length=20)


@router.get("/catalog")
async def get_project_control_catalog() -> Dict:
    try:
        return summarize_catalog()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/nodes")
async def register_node_config(request: NodeConfigRequest) -> Dict:
    try:
        node = upsert_node(request.node_id, request.model_dump(exclude_none=True, exclude={"node_id"}))
        return {"success": True, "node": node}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/register")
async def register_project_control(request: ProjectRegisterRequest) -> Dict:
    try:
        project = sync_project_snapshot(
            request.project_id,
            request.repo_path,
            aliases=request.aliases,
            node_id=request.node_id or current_node_id(),
        )
        return {"success": True, "project": project}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/sync")
async def sync_project_control(request: ProjectSyncRequest) -> Dict:
    try:
        node_id = request.node_id or current_node_id()
        repo_path = request.repo_path
        if not repo_path:
            snapshot = get_project_snapshot(request.project_id, node_id)
            repo_path = str(snapshot.get("path") or "").strip() if snapshot else ""
        if not repo_path:
            raise RuntimeError("Missing repo_path and no existing snapshot path found.")
        project = sync_project_snapshot(
            request.project_id,
            repo_path,
            aliases=request.aliases,
            node_id=node_id,
        )
        return {"success": True, "project": project}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projects/{project_id}/status")
async def get_project_execution_status(project_id: str, preferred_node: Optional[str] = None) -> Dict:
    try:
        return {"success": True, "status": project_status(project_id, preferred_node)}
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/projects/{project_id}/google-assets")
async def get_project_google_assets(project_id: str) -> Dict:
    try:
        return {"success": True, "project_id": project_id, "google_assets": list_project_google_assets(project_id)}
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/projects/{project_id}/google-assets")
async def link_project_google_asset(project_id: str, request: ProjectGoogleAssetRequest) -> Dict:
    try:
        asset_id = request.asset_id
        metadata: Dict[str, Optional[str]] = {}
        if request.drive_url or request.asset_id:
            resolved_id = extract_google_drive_file_id(request.asset_id or request.drive_url or "")
            if not resolved_id:
                raise RuntimeError("Could not extract Google Drive file ID from request.")
            asset_id = resolved_id
            metadata = get_drive_file_metadata(resolved_id)
        result = upsert_project_google_asset(
            project_id,
            {
                "asset_id": asset_id or metadata.get("asset_id") or "",
                "title": request.title or metadata.get("title") or "Untitled",
                "kind": request.kind or metadata.get("kind") or "file",
                "url": request.drive_url or metadata.get("url") or "",
                "mime_type": request.mime_type or metadata.get("mime_type") or "",
                "role": request.role or "",
                "source": request.source or "google_drive",
            },
        )
        return {"success": True, **result}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/handoff")
async def handoff_project_control(request: ProjectHandoffRequest) -> Dict:
    try:
        return {"success": True, "handoff": handoff_project(
            request.project_id,
            source_node=request.source_node,
            target_node=request.target_node,
        )}
    except Exception as exc:
        enqueue = enqueue_mirror_task(
            project_id=request.project_id,
            source_node=request.source_node or current_node_id(),
            target_node=request.target_node or current_node_id(),
        )
        raise HTTPException(
            status_code=503,
            detail=f"{exc}. Mirror task queued as {enqueue['id']}.",
        ) from exc


@router.post("/mirror/process")
async def process_project_mirror_queue(limit: int = 20) -> Dict:
    try:
        return {"success": True, **process_mirror_queue(limit=limit)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/chat")
async def run_project_executor_chat(request: ProjectChatRequest) -> Dict:
    try:
        result = run_project_chat(
            project_id=request.project_id,
            preferred_node=request.preferred_node,
            provider=request.executor,
            message=request.message,
            history=[item.model_dump() for item in request.history],
        )
        status = result["status"]
        return {
            "success": True,
            "reply": result["reply"],
            "provider": request.executor,
            "model": result["model"],
            "project_id": request.project_id,
            "node_id": result["node_id"],
            "latency_ms": result["latency_ms"],
            "branch": status.get("branch"),
            "head": status.get("head"),
            "dirty_count": int(status.get("dirty_count") or 0),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
