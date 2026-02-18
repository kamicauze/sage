"""
Memory search and management endpoints.
"""
from typing import List
from fastapi import APIRouter, HTTPException

from architect.api.models import (
    MemorySearchRequest,
    MemorySearchResponse,
    MemorySearchResult,
    IngestRequest
)
from architect.memory import ArchitectMemory
from architect.manifest import ProjectManifest
from architect.paths import root_relative
from architect.api.security import (
    resolve_manifest_path,
    resolve_repo_file_path,
    validate_project_id,
)

router = APIRouter(prefix="/memory", tags=["memory"])


@router.post("/search", response_model=MemorySearchResponse)
async def search_memory(request: MemorySearchRequest) -> MemorySearchResponse:
    """
    Search the memory system for relevant code snippets.

    This endpoint performs semantic search over the ingested codebase
    using vector similarity.

    Args:
        request: MemorySearchRequest with query and filters

    Returns:
        MemorySearchResponse with matching code snippets
    """
    try:
        project_id = validate_project_id(request.project_id)
        memory = ArchitectMemory()

        # Query memory
        results = memory.query(
            project_id=project_id,
            query_text=request.query,
            n_results=request.n_results,
            zone_filter=request.zone_filter
        )

        # Parse results
        search_results: List[MemorySearchResult] = []

        if results['documents'] and len(results['documents']) > 0:
            documents = results['documents'][0]
            metadatas = results['metadatas'][0] if results['metadatas'] else []
            distances = results['distances'][0] if results['distances'] else []

            for i, doc in enumerate(documents):
                meta = metadatas[i] if i < len(metadatas) else {}
                distance = distances[i] if i < len(distances) else 0.0

                search_results.append(MemorySearchResult(
                    content=doc,
                    source=meta.get('source', 'unknown'),
                    zone_name=meta.get('zone_name', 'unknown'),
                    role=meta.get('role', 'generic'),
                    distance=distance
                ))

        return MemorySearchResponse(
            results=search_results,
            query=request.query,
            total_results=len(search_results)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Memory search failed: {str(e)}")


@router.post("/ingest")
async def ingest_files(request: IngestRequest) -> dict:
    """
    Ingest files into memory.

    This endpoint processes files and adds them to the vector store
    for later retrieval during plan generation.

    Args:
        request: IngestRequest with file paths and manifest

    Returns:
        Dictionary with ingestion results
    """
    try:
        safe_manifest_path = resolve_manifest_path(request.manifest_path)

        # Load manifest
        try:
            manifest = ProjectManifest.load(str(safe_manifest_path))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid manifest: {str(e)}")

        memory = ArchitectMemory()

        # Ingest each file
        ingested = []
        failed = []

        for file_path in request.file_paths:
            try:
                safe_file_path = resolve_repo_file_path(file_path, manifest_repo_path=manifest.repo_path)
            except HTTPException as path_exc:
                failed.append({
                    "path": file_path,
                    "error": path_exc.detail
                })
                continue

            try:
                memory.ingest(manifest, str(safe_file_path))
                ingested.append(root_relative(safe_file_path))
            except Exception as e:
                failed.append({
                    "path": file_path,
                    "error": str(e)
                })

        return {
            "status": "success" if len(ingested) > 0 else "failed",
            "ingested_count": len(ingested),
            "failed_count": len(failed),
            "ingested_files": ingested,
            "failed_files": failed
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.get("/zones/{project_id}")
async def get_zones(project_id: str) -> dict:
    """
    Get all cognitive zones for a project.

    Args:
        project_id: Project ID

    Returns:
        Dictionary with zone information
    """
    try:
        project_id = validate_project_id(project_id)
        memory = ArchitectMemory()

        # Get collection
        try:
            collection = memory._get_collection(project_id)
            total_chunks = collection.count()

            if total_chunks > 0:
                # Get all items
                results = collection.get()

                # Group by zone
                zones = {}
                if results and results.get('metadatas'):
                    for meta in results['metadatas']:
                        zone_name = meta.get('zone_name', 'unknown')
                        role = meta.get('role', 'generic')

                        if zone_name not in zones:
                            zones[zone_name] = {
                                "name": zone_name,
                                "role": role,
                                "chunk_count": 0,
                                "files": set()
                            }

                        zones[zone_name]["chunk_count"] += 1
                        zones[zone_name]["files"].add(meta.get('source', 'unknown'))

                # Convert sets to lists for JSON serialization
                for zone in zones.values():
                    zone["files"] = sorted(list(zone["files"]))

                return {
                    "project_id": project_id,
                    "total_chunks": total_chunks,
                    "zone_count": len(zones),
                    "zones": list(zones.values())
                }
            else:
                return {
                    "project_id": project_id,
                    "total_chunks": 0,
                    "zone_count": 0,
                    "zones": []
                }

        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Collection not found: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get zones: {str(e)}")


@router.delete("/collection/{project_id}")
async def delete_collection(project_id: str) -> dict:
    """
    Delete the entire memory collection for a project.

    WARNING: This will permanently delete all ingested data.

    Args:
        project_id: Project ID

    Returns:
        Success message
    """
    try:
        project_id = validate_project_id(project_id)
        memory = ArchitectMemory()

        try:
            memory.client.delete_collection(name=project_id)
            return {
                "status": "success",
                "message": f"Collection {project_id} deleted successfully"
            }
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Collection not found: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete collection: {str(e)}")


@router.get("/files/{project_id}")
async def list_indexed_files(project_id: str) -> dict:
    """
    List all files that have been indexed in memory.

    Args:
        project_id: Project ID

    Returns:
        Dictionary with indexed file information
    """
    try:
        project_id = validate_project_id(project_id)
        memory = ArchitectMemory()

        try:
            collection = memory._get_collection(project_id)
            total_chunks = collection.count()

            if total_chunks > 0:
                results = collection.get()

                # Extract unique files
                files = {}
                if results and results.get('metadatas'):
                    for meta in results['metadatas']:
                        source = meta.get('source', 'unknown')

                        if source not in files:
                            files[source] = {
                                "path": source,
                                "zone_name": meta.get('zone_name', 'unknown'),
                                "role": meta.get('role', 'generic'),
                                "chunk_count": 0
                            }

                        files[source]["chunk_count"] += 1

                return {
                    "project_id": project_id,
                    "file_count": len(files),
                    "total_chunks": total_chunks,
                    "files": sorted(list(files.values()), key=lambda x: x["path"])
                }
            else:
                return {
                    "project_id": project_id,
                    "file_count": 0,
                    "total_chunks": 0,
                    "files": []
                }

        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Collection not found: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")
