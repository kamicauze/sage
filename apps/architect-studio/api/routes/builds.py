"""
Build endpoints for plan generation and execution.
"""
import os
from fastapi import APIRouter, HTTPException, Request

from architect.api.models import (
    PlanRequest,
    BuildRequest,
    PlanResponse,
    BuildResponse,
    RoutingDecision,
    API_VERSION,
    API_COMPAT,
)
from architect.router import ArchitectRouter, BuildRequest as ArchBuildRequest
from architect.manifest import ProjectManifest
from architect.router_logic import RouterScorer
from architect.paths import workspace_plan_path, workspace_sandbox_path, root_relative
from architect.api.security import resolve_manifest_path, validate_project_id
from architect.logging_utils import log_event

router = APIRouter(prefix="/builds", tags=["builds"])


def _estimate_cost(provider: str, model: str) -> tuple[float, float]:
    """
    Estimate cost range for a request.

    Returns:
        Tuple of (min_cost, max_cost)
    """
    # Simplified cost estimation
    # In production, this should use token counts and actual pricing
    cost_map = {
        "ollama": (0.0, 0.0),
        "google": (0.05, 0.25),
        "anthropic": (0.15, 0.50),
        "openai": (0.10, 0.40),
        "xai": (0.20, 0.60)
    }
    return cost_map.get(provider, (0.0, 0.0))


def _create_routing_decision_response(decision) -> RoutingDecision:
    """Create RoutingDecision response from router decision."""
    min_cost, max_cost = _estimate_cost(decision.provider, decision.model)

    return RoutingDecision(
        route=decision.route,
        score=decision.score,
        reason=decision.reason,
        provider=decision.provider,
        model=decision.model,
        estimated_cost_min=min_cost,
        estimated_cost_max=max_cost
    )


@router.post("/plan", response_model=PlanResponse)
async def generate_plan(request: PlanRequest, http_request: Request) -> PlanResponse:
    """
    Generate an implementation plan.

    This endpoint:
    1. Analyzes the query and retrieves relevant context from memory
    2. Determines routing (LOCAL/HYBRID/CLOUD) based on complexity
    3. Generates an implementation plan using the selected LLM
    4. Saves the plan to the workspace

    Args:
        request: PlanRequest with query and configuration

    Returns:
        PlanResponse with generated plan and routing information
    """
    try:
        correlation_id = getattr(http_request.state, "correlation_id", None)
        log_event(
            "api.builds",
            "plan_request_started",
            correlation_id=correlation_id,
            manifest_path=request.manifest_path,
            request_type=request.request_type,
        )
        safe_manifest_path = resolve_manifest_path(request.manifest_path)

        # Load manifest
        try:
            manifest = ProjectManifest.load(str(safe_manifest_path))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid manifest: {str(e)}")

        # Create router (non-interactive mode for API)
        arch_router = ArchitectRouter(interactive=False, lazy_memory=True)

        # Create BuildRequest for architect
        build_req = ArchBuildRequest(
            manifest_path=str(safe_manifest_path),
            request_type=request.request_type,
            query=request.query,
            context=request.context,
            correlation_id=correlation_id,
        )

        # Get routing decision (for transparency)
        scorer = RouterScorer(manifest.policy)
        preliminary_decision = scorer.determine_route(request.query, "plan", context_files=[])

        # Retrieve context if needed
        context_snippets = []
        if preliminary_decision.score >= 4:
            try:
                results = arch_router.memory.query(manifest.id, request.query, n_results=3)
            except Exception as e:
                results = {"documents": [], "metadatas": []}
                log_event(
                    "api.builds",
                    "plan_memory_unavailable",
                    level="warning",
                    correlation_id=correlation_id,
                    project_id=manifest.id,
                    error=str(e),
                )

            if results.get('documents'):
                for i, doc in enumerate(results['documents'][0]):
                    meta = results['metadatas'][0][i]
                    context_snippets.append({
                        "source": meta['source'],
                        "zone_name": meta['zone_name'],
                        "content_preview": doc[:200] + "..."
                    })

            # Re-score with context
            decision = scorer.determine_route(
                request.query,
                "plan",
                context_files=[s['source'] for s in context_snippets]
            )
        else:
            decision = preliminary_decision

        # Process request
        result = arch_router.process_request(build_req)
        details = result.details or {}

        # Read generated plan
        plan_path = workspace_plan_path(manifest.id)
        plan_content = ""
        if plan_path.exists():
            with open(plan_path, 'r') as f:
                plan_content = f.read()

        response = PlanResponse(
            status=result.status,
            plan_content=plan_content,
            plan_path=root_relative(plan_path),
            routing_decision=_create_routing_decision_response(decision),
            context_snippets=context_snippets,
            timing=details.get("timing"),
            summary=result.summary,
            api_version=API_VERSION,
            api_compat=API_COMPAT,
        )
        log_event(
            "api.builds",
            "plan_request_completed",
            correlation_id=correlation_id,
            project_id=manifest.id,
            status=result.status,
            route=decision.route,
        )
        return response

    except HTTPException:
        raise
    except Exception as e:
        log_event(
            "api.builds",
            "plan_request_failed",
            level="error",
            correlation_id=getattr(http_request.state, "correlation_id", None),
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Failed to generate plan: {str(e)}")


@router.post("/build", response_model=BuildResponse)
async def execute_build(request: BuildRequest, http_request: Request) -> BuildResponse:
    """
    Execute a build from an existing plan.

    This endpoint:
    1. Loads the existing plan from the workspace
    2. Generates code files based on the plan
    3. Runs tests and attempts self-healing if tests fail
    4. Returns build results

    Args:
        request: BuildRequest with manifest path

    Returns:
        BuildResponse with build results and artifacts
    """
    try:
        correlation_id = getattr(http_request.state, "correlation_id", None)
        log_event(
            "api.builds",
            "build_request_started",
            correlation_id=correlation_id,
            manifest_path=request.manifest_path,
        )
        safe_manifest_path = resolve_manifest_path(request.manifest_path)

        # Load manifest
        try:
            manifest = ProjectManifest.load(str(safe_manifest_path))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid manifest: {str(e)}")

        # Check if plan exists
        plan_path = workspace_plan_path(manifest.id)
        if not plan_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Plan not found at {root_relative(plan_path)}. Generate a plan first."
            )

        # Create router and execute build
        arch_router = ArchitectRouter(interactive=False, lazy_memory=True)

        build_req = ArchBuildRequest(
            manifest_path=str(safe_manifest_path),
            request_type="build",
            query="",  # Not needed for build
            correlation_id=correlation_id,
        )

        result = arch_router.process_request(build_req)

        details = result.details or {}
        file_details = details.get("files", {})
        files_built = file_details.get("built", [])
        files_skipped = file_details.get("skipped", [])
        files_failed = file_details.get("failed", [])
        test_results = details.get("tests")

        response = BuildResponse(
            status=result.status,
            artifacts=result.artifacts,
            files_built=files_built,
            files_skipped=files_skipped,
            files_failed=files_failed,
            test_results=test_results,
            timing=details.get("timing"),
            build_details=details if details else None,
            summary=result.summary,
            api_version=API_VERSION,
            api_compat=API_COMPAT,
        )
        log_event(
            "api.builds",
            "build_request_completed",
            correlation_id=correlation_id,
            project_id=manifest.id,
            status=result.status,
            built_count=len(files_built),
            failed_count=len(files_failed),
        )
        return response

    except HTTPException:
        raise
    except Exception as e:
        log_event(
            "api.builds",
            "build_request_failed",
            level="error",
            correlation_id=getattr(http_request.state, "correlation_id", None),
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Failed to execute build: {str(e)}")


@router.get("/plan/{project_id}")
async def get_plan(project_id: str) -> dict:
    """
    Get the current plan for a project.

    Args:
        project_id: Project ID

    Returns:
        Dictionary with plan content and metadata
    """
    project_id = validate_project_id(project_id)
    plan_path = workspace_plan_path(project_id)

    if not plan_path.exists():
        raise HTTPException(status_code=404, detail=f"No plan found for project {project_id}")

    try:
        with open(plan_path, 'r') as f:
            content = f.read()

        # Get file stats
        stats = os.stat(plan_path)

        return {
            "project_id": project_id,
            "plan_path": root_relative(plan_path),
            "content": content,
            "size_bytes": stats.st_size,
            "modified_at": stats.st_mtime
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read plan: {str(e)}")


@router.get("/artifacts/{project_id}")
async def list_artifacts(project_id: str) -> dict:
    """
    List all artifacts (generated files) for a project.

    Args:
        project_id: Project ID

    Returns:
        Dictionary with list of artifacts
    """
    project_id = validate_project_id(project_id)
    sandbox_dir = workspace_sandbox_path(project_id)

    if not sandbox_dir.exists():
        return {
            "project_id": project_id,
            "sandbox_dir": root_relative(sandbox_dir),
            "artifacts": []
        }

    try:
        artifacts = []
        for root, dirs, files in os.walk(sandbox_dir):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, sandbox_dir)
                stats = os.stat(file_path)

                artifacts.append({
                    "path": rel_path,
                    "full_path": root_relative(file_path),
                    "size_bytes": stats.st_size,
                    "modified_at": stats.st_mtime
                })

        return {
            "project_id": project_id,
            "sandbox_dir": root_relative(sandbox_dir),
            "artifact_count": len(artifacts),
            "artifacts": artifacts
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list artifacts: {str(e)}")


@router.delete("/plan/{project_id}")
async def delete_plan(project_id: str) -> dict:
    """
    Delete the current plan for a project.

    Args:
        project_id: Project ID

    Returns:
        Success message
    """
    project_id = validate_project_id(project_id)
    plan_path = workspace_plan_path(project_id)

    if not plan_path.exists():
        raise HTTPException(status_code=404, detail=f"No plan found for project {project_id}")

    try:
        os.remove(plan_path)
        return {
            "status": "success",
            "message": f"Plan for {project_id} deleted successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete plan: {str(e)}")
