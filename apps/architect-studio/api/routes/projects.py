"""
Project management endpoints.
"""
import os
import glob
import json
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import yaml
from architect.paths import PROJECTS_DIR as PROJECTS_DIR_PATH, root_relative
from architect.api.security import validate_project_id

router = APIRouter(prefix="/projects", tags=["projects"])

PROJECTS_DIR = PROJECTS_DIR_PATH


class CreateProjectRequest(BaseModel):
    """Request model for creating a new project."""
    project_id: str
    manifest_content: str  # JSON string representation of the manifest


def _load_manifest(file_path: str) -> Dict[str, Any]:
    """Load a project manifest from YAML file."""
    try:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load manifest: {str(e)}")


@router.get("/")
async def list_projects() -> Dict[str, Any]:
    """
    List all available projects.

    Returns:
        Dictionary with list of projects and their metadata
    """
    try:
        # Find all YAML files in projects directory
        pattern = str(PROJECTS_DIR / "*.yaml")
        manifest_files = glob.glob(pattern)

        projects = []
        for file_path in manifest_files:
            # Skip .keep and other non-manifest files
            if os.path.basename(file_path).startswith('.'):
                continue

            try:
                manifest = _load_manifest(file_path)

                # Extract key info
                project_info = {
                    "id": manifest.get("project", {}).get("id", "unknown"),
                    "name": manifest.get("project", {}).get("name", "Unknown"),
                    "description": manifest.get("project", {}).get("description", ""),
                    "manifest_path": root_relative(PROJECTS_DIR / os.path.basename(file_path)),
                    "stack": manifest.get("stack", {}),
                    "memory_enabled": manifest.get("memory", {}).get("enabled", False),
                    "zone_count": len(manifest.get("memory", {}).get("zones", [])),
                }
                projects.append(project_info)
            except Exception as e:
                print(f"Failed to load {file_path}: {e}")
                continue

        return {
            "total_projects": len(projects),
            "projects": projects
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {str(e)}")


@router.get("/{project_id}")
async def get_project(project_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific project.

    Args:
        project_id: Project ID

    Returns:
        Complete project manifest
    """
    try:
        project_id = validate_project_id(project_id)
        # Find manifest file for this project
        pattern = str(PROJECTS_DIR / "*.yaml")
        manifest_files = glob.glob(pattern)

        for file_path in manifest_files:
            if os.path.basename(file_path).startswith('.'):
                continue

            try:
                manifest = _load_manifest(file_path)
                if manifest.get("project", {}).get("id") == project_id:
                    return {
                        "project_id": project_id,
                        "manifest_path": root_relative(PROJECTS_DIR / os.path.basename(file_path)),
                        "manifest": manifest
                    }
            except:
                continue

        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get project: {str(e)}")


@router.get("/{project_id}/zones")
async def get_project_zones(project_id: str) -> Dict[str, Any]:
    """
    Get cognitive zones for a specific project.

    Args:
        project_id: Project ID

    Returns:
        Zone configuration
    """
    try:
        project_id = validate_project_id(project_id)
        project_data = await get_project(project_id)
        manifest = project_data["manifest"]

        zones = manifest.get("memory", {}).get("zones", [])

        return {
            "project_id": project_id,
            "project_name": manifest.get("project", {}).get("name"),
            "memory_enabled": manifest.get("memory", {}).get("enabled", False),
            "zone_count": len(zones),
            "zones": zones
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get zones: {str(e)}")


@router.get("/{project_id}/config")
async def get_project_config(project_id: str) -> Dict[str, Any]:
    """
    Get project configuration (policy, commands, etc.).

    Args:
        project_id: Project ID

    Returns:
        Project configuration
    """
    try:
        project_id = validate_project_id(project_id)
        project_data = await get_project(project_id)
        manifest = project_data["manifest"]

        return {
            "project_id": project_id,
            "stack": manifest.get("stack", {}),
            "commands": manifest.get("commands", {}),
            "policy": manifest.get("policy", {}),
            "paths": manifest.get("project", {}).get("paths", {})
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")


@router.post("/create")
async def create_project(request: CreateProjectRequest) -> Dict[str, Any]:
    """
    Create a new project manifest file.

    Args:
        request: Project creation request with ID and manifest content

    Returns:
        Success message with project details
    """
    try:
        # Validate project ID format
        validate_project_id(request.project_id)

        # Ensure projects directory exists
        os.makedirs(PROJECTS_DIR, exist_ok=True)

        # Define manifest file path
        manifest_path = str(PROJECTS_DIR / f"{request.project_id}.yaml")

        # Check if project already exists
        if os.path.exists(manifest_path):
            raise HTTPException(
                status_code=409,
                detail=f"Project {request.project_id} already exists"
            )

        # Parse JSON to YAML
        try:
            manifest_data = json.loads(request.manifest_content)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid manifest JSON: {str(e)}"
            )

        # Write YAML file
        with open(manifest_path, 'w') as f:
            yaml.dump(manifest_data, f, default_flow_style=False, sort_keys=False)

        return {
            "status": "success",
            "project_id": request.project_id,
            "manifest_path": root_relative(PROJECTS_DIR / f"{request.project_id}.yaml"),
            "message": f"Project {request.project_id} created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create project: {str(e)}"
        )
