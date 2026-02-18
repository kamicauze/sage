"""
Architect Bridge
Allows Brain to trigger Architect tasks asynchronously.

This bridge enables voice commands like "Add expense tracking to brain"
to flow from the Brain service to the Architect for code generation.
"""
import sys
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional

# Add repo root so `architect.*` and `shared.*` imports resolve when Brain
# is started as a script (sys.path[0] would otherwise be only brain-runtime).
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class ArchitectBridge:
    """
    Bridge between Brain and Architect services.
    
    The Architect is synchronous (CLI-oriented), so we wrap it
    in an executor to not block the Brain's async event loop.
    """
    
    def __init__(self, max_workers: int = 1):
        """
        Args:
            max_workers: Number of concurrent Architect tasks allowed
        """
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._router = None  # Lazy initialization
        self._import_error = None
        
    def _get_router(self):
        """Lazy-load the Architect router."""
        if self._router is not None:
            return self._router
            
        if self._import_error is not None:
            raise self._import_error
            
        try:
            from architect.router import ArchitectRouter
            self._router = ArchitectRouter()
            return self._router
        except ImportError as e:
            self._import_error = ImportError(f"Could not import Architect: {e}")
            raise self._import_error

    @staticmethod
    def _normalize_task_type(task_type: str) -> str:
        """
        Normalize upstream task hints into Architect execution modes.

        Returns one of:
            - "plan": draft plan only
            - "build": execute existing plan only
            - "plan_then_build": draft then execute (for code/fix/test intents)
        """
        normalized = (task_type or "plan").strip().lower()
        if normalized == "build":
            return "build"
        if normalized in {"code", "fix", "test"}:
            return "plan_then_build"
        return "plan"

    async def dispatch(
        self,
        project_id: str,
        query: str,
        task_type: str = 'plan',
        routing_hint: Any = None
    ) -> Dict[str, Any]:
        """
        Dispatch a task to the Architect.
        
        Args:
            project_id: The manifest project ID (e.g., 'sage_brain')
            query: The user's request (e.g., "Add expense tracking")
            task_type: Upstream task hint ('plan', 'build', 'code', 'fix', 'test')
            routing_hint: Pre-computed RouteDecision (optional)
        
        Returns:
            Result dict with:
                - status: 'SUCCESS', 'FAILURE'
                - artifacts: List of created files
                - summary: Human-readable summary
        """
        execution_mode = self._normalize_task_type(task_type)

        # Resolve manifest path
        manifest_path = self._resolve_manifest(project_id)
        
        if manifest_path is None:
            return {
                "status": "FAILURE",
                "artifacts": [],
                "summary": f"Project '{project_id}' not found"
            }
        
        print(f"[ArchitectBridge] Dispatching to manifest: {manifest_path}")
        print(
            f"[ArchitectBridge] Query: '{query}' "
            f"(task={task_type}, mode={execution_mode})"
        )
        
        # Build request context
        context = {}
        if routing_hint:
            context['routing_hint'] = (
                routing_hint.__dict__ 
                if hasattr(routing_hint, '__dict__') 
                else routing_hint
            )
        
        # Run in executor to not block async loop
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                self._executor,
                self._sync_process,
                manifest_path,
                execution_mode,
                query,
                context
            )
            return result
        except Exception as e:
            print(f"[ArchitectBridge] Error: {e}")
            return {
                "status": "FAILURE",
                "artifacts": [],
                "summary": f"Architect error: {str(e)}"
            }

    def _resolve_manifest(self, project_id: str) -> Optional[str]:
        """
        Resolve project ID to manifest file path.
        
        Tries multiple path patterns:
            1. architect/projects/{project_id}.yaml
            2. architect/projects/{project_id/with/slashes}.yaml
            3. Falls back to sage.yaml
        """
        base_path = "architect/projects"
        
        # Try exact match
        candidates = [
            f"{base_path}/sage.yaml",  # Default fallback
        ]
        
        if project_id:
            candidates.insert(0, f"{base_path}/{project_id.replace('_', '/')}.yaml")
            candidates.insert(0, f"{base_path}/{project_id}.yaml")
        
        for path in candidates:
            if os.path.exists(path):
                return path
        
        # Last resort: check if sage.yaml exists
        if os.path.exists(f"{base_path}/sage.yaml"):
            print(f"[ArchitectBridge] Warning: '{project_id}' not found, using sage.yaml")
            return f"{base_path}/sage.yaml"
        
        return None

    def _sync_process(
        self,
        manifest_path: str,
        task_type: str,
        query: str,
        context: Dict
    ) -> Dict[str, Any]:
        """
        Synchronous wrapper for the Architect.
        Called from executor.
        """
        try:
            from architect.router import ArchitectRouter, BuildRequest

            router = self._get_router()

            if task_type == "plan_then_build":
                # Voice "code/fix/test" intents should execute end-to-end in one pass.
                plan_request = BuildRequest(
                    manifest_path=manifest_path,
                    request_type="plan",
                    query=query,
                    context=context
                )
                plan_result = router.process_request(plan_request)
                if plan_result.status != "SUCCESS":
                    return {
                        "status": plan_result.status,
                        "artifacts": plan_result.artifacts,
                        "summary": plan_result.summary
                    }

                build_request = BuildRequest(
                    manifest_path=manifest_path,
                    request_type="build",
                    query="",
                    context=context
                )
                build_result = router.process_request(build_request)

                artifacts = []
                for path in (plan_result.artifacts or []) + (build_result.artifacts or []):
                    if path not in artifacts:
                        artifacts.append(path)

                return {
                    "status": build_result.status,
                    "artifacts": artifacts,
                    "summary": build_result.summary
                }

            request_type = "build" if task_type == "build" else "plan"
            request = BuildRequest(
                manifest_path=manifest_path,
                request_type=request_type,
                query=query if request_type == "plan" else "",
                context=context
            )

            result = router.process_request(request)

            return {
                "status": result.status,
                "artifacts": result.artifacts,
                "summary": result.summary
            }
            
        except Exception as e:
            return {
                "status": "FAILURE",
                "artifacts": [],
                "summary": f"Architect process error: {str(e)}"
            }

    async def get_status(self, project_id: str) -> Dict[str, Any]:
        """
        Get the status of a project (memory, last build, etc.)
        """
        # TODO: Implement project status check
        return {
            "project_id": project_id,
            "memory_loaded": False,
            "last_build": None
        }

    def shutdown(self):
        """Shutdown the executor gracefully."""
        self._executor.shutdown(wait=True)


# For testing
async def test_bridge():
    """Test the architect bridge."""
    bridge = ArchitectBridge()
    
    # Test with sage_brain project
    result = await bridge.dispatch(
        project_id="sage_brain",
        query="Add a test pattern",
        task_type="plan"
    )
    
    print(f"Result: {result}")
    bridge.shutdown()


if __name__ == "__main__":
    asyncio.run(test_bridge())
