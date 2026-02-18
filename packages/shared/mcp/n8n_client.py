"""
n8n Workflow Automation Client.
Provides integration with n8n workflow automation platform.
"""
import aiohttp
from typing import Dict, List, Optional, Any


class N8NClient:
    """
    Client for triggering n8n workflows.
    Can be used by both Architect and Brain for workflow automation.
    """

    def __init__(self, base_url: str = "http://localhost:5678", api_key: Optional[str] = None):
        """
        Initialize n8n client.

        Args:
            base_url: n8n instance URL
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            headers = {}
            if self.api_key:
                headers["X-N8N-API-KEY"] = self.api_key
            self.session = aiohttp.ClientSession(headers=headers)
        return self.session

    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def trigger_webhook(self, webhook_path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Trigger an n8n workflow via webhook.

        Args:
            webhook_path: Webhook path (e.g., "git-auto-commit")
            data: Data to send to the workflow

        Returns:
            Dict with workflow execution result
        """
        session = await self._get_session()
        url = f"{self.base_url}/webhook/{webhook_path}"

        try:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "data": result
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {await response.text()}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def trigger_workflow_by_id(self, workflow_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Trigger a specific workflow by ID.

        Args:
            workflow_id: n8n workflow ID
            data: Input data for the workflow

        Returns:
            Dict with execution result
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/v1/workflows/{workflow_id}/execute"

        try:
            async with session.post(url, json=data) as response:
                if response.status in (200, 201):
                    result = await response.json()
                    return {
                        "success": True,
                        "execution_id": result.get("id"),
                        "data": result
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {await response.text()}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def get_workflow_status(self, execution_id: str) -> Dict[str, Any]:
        """
        Get status of a workflow execution.

        Args:
            execution_id: Execution ID from trigger_workflow_by_id

        Returns:
            Dict with execution status
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/v1/executions/{execution_id}"

        try:
            async with session.get(url) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "status": "finished" if result.get("finished") else "running",
                        "data": result
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {await response.text()}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def list_workflows(self) -> Dict[str, Any]:
        """
        List all workflows.

        Returns:
            Dict with list of workflows
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/v1/workflows"

        try:
            async with session.get(url) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "workflows": result.get("data", [])
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {await response.text()}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def create_workflow(
        self,
        name: str,
        nodes: List[Dict],
        connections: Dict,
        active: bool = False
    ) -> Dict[str, Any]:
        """
        Create a new workflow programmatically.

        Args:
            name: Workflow name
            nodes: List of node definitions
            connections: Connection definitions
            active: Whether workflow should be active immediately after creation

        Returns:
            Dict with created workflow info
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/v1/workflows"

        workflow_data = {
            "name": name,
            "nodes": nodes,
            "connections": connections,
            "active": active
        }

        try:
            async with session.post(url, json=workflow_data) as response:
                if response.status in (200, 201):
                    result = await response.json()
                    return {
                        "success": True,
                        "workflow_id": result.get("id"),
                        "data": result
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {await response.text()}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    # Convenience methods for common workflows

    async def git_auto_commit(
        self,
        repo_path: str,
        message: str,
        files: Optional[List[str]] = None,
        branch: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Trigger git auto-commit workflow.

        Args:
            repo_path: Repository path
            message: Commit message
            files: Files to commit (None = all)
            branch: Branch to create/use

        Returns:
            Workflow execution result
        """
        return await self.trigger_webhook("git-auto-commit", {
            "repo_path": repo_path,
            "message": message,
            "files": files,
            "branch": branch
        })

    async def architect_build_complete(
        self,
        project_id: str,
        artifacts: List[str],
        status: str
    ) -> Dict[str, Any]:
        """
        Trigger post-build workflow.

        Args:
            project_id: Project ID
            artifacts: List of generated files
            status: Build status (SUCCESS/FAILURE)

        Returns:
            Workflow execution result
        """
        return await self.trigger_webhook("architect-build-complete", {
            "project_id": project_id,
            "artifacts": artifacts,
            "status": status
        })

    async def brain_pattern_detected(
        self,
        pattern: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Trigger pattern detection workflow from Brain.

        Args:
            pattern: Pattern name (e.g., "OVERWORK_LATE")
            context: Pattern context data

        Returns:
            Workflow execution result
        """
        return await self.trigger_webhook("brain-pattern", {
            "pattern": pattern,
            "context": context
        })


# Context manager support
class N8NClientContext:
    """Context manager for N8NClient."""

    def __init__(self, *args, **kwargs):
        self.client = N8NClient(*args, **kwargs)

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.close()
