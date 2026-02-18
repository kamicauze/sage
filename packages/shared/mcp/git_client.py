"""
Git MCP Client - Provides git operations for Architect and Brain.
"""
import os
import subprocess
from typing import List, Optional, Dict, Any
from pathlib import Path


class GitMCPClient:
    """
    Git operations client compatible with MCP protocol.
    Provides git functionality for both Architect and Brain components.
    """

    def __init__(self, repo_path: str = None):
        """
        Initialize Git client.

        Args:
            repo_path: Path to git repository. Defaults to current directory.
        """
        self.repo_path = repo_path or os.getcwd()
        self._verify_git_repo()

    def _verify_git_repo(self) -> bool:
        """Verify that repo_path is a git repository."""
        git_dir = Path(self.repo_path) / ".git"
        if not git_dir.exists():
            raise ValueError(f"{self.repo_path} is not a git repository")
        return True

    def _run_git_command(self, args: List[str]) -> Dict[str, Any]:
        """
        Run a git command and return result.

        Args:
            args: Git command arguments (e.g., ['status', '--short'])

        Returns:
            Dict with stdout, stderr, and return code
        """
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Command timed out after 30 seconds",
                "returncode": -1
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "returncode": -1
            }

    async def get_status(self) -> Dict[str, Any]:
        """
        Get git status of the repository.

        Returns:
            Dict with status information
        """
        result = self._run_git_command(["status", "--short"])

        if not result["success"]:
            return result

        # Parse status output
        lines = result["stdout"].split("\n") if result["stdout"] else []
        files = {
            "modified": [],
            "added": [],
            "deleted": [],
            "untracked": []
        }

        for line in lines:
            if not line:
                continue

            status = line[:2]
            filename = line[3:]

            if status.strip() == "M":
                files["modified"].append(filename)
            elif status.strip() == "A":
                files["added"].append(filename)
            elif status.strip() == "D":
                files["deleted"].append(filename)
            elif status.strip() == "??":
                files["untracked"].append(filename)

        return {
            "success": True,
            "files": files,
            "has_changes": len(lines) > 0
        }

    async def get_diff(self, file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Get git diff.

        Args:
            file_path: Optional specific file to diff

        Returns:
            Dict with diff output
        """
        args = ["diff"]
        if file_path:
            args.append(file_path)

        result = self._run_git_command(args)
        return result

    async def create_branch(self, branch_name: str, checkout: bool = True) -> Dict[str, Any]:
        """
        Create a new git branch.

        Args:
            branch_name: Name of the branch to create
            checkout: Whether to checkout the new branch

        Returns:
            Dict with operation result
        """
        # Check if branch already exists
        check_result = self._run_git_command(["branch", "--list", branch_name])
        if check_result["stdout"]:
            return {
                "success": False,
                "error": f"Branch '{branch_name}' already exists"
            }

        # Create branch
        if checkout:
            result = self._run_git_command(["checkout", "-b", branch_name])
        else:
            result = self._run_git_command(["branch", branch_name])

        if result["success"]:
            return {
                "success": True,
                "branch": branch_name,
                "checked_out": checkout
            }
        else:
            return {
                "success": False,
                "error": result["stderr"]
            }

    async def add_files(self, files: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Stage files for commit.

        Args:
            files: List of file paths to stage. If None, stages all changes.

        Returns:
            Dict with operation result
        """
        if files is None or len(files) == 0:
            # Stage all changes
            result = self._run_git_command(["add", "."])
        else:
            # Stage specific files
            result = self._run_git_command(["add"] + files)

        return result

    async def commit(
        self,
        message: str,
        files: Optional[List[str]] = None,
        author: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a git commit.

        Args:
            message: Commit message
            files: Optional list of files to commit. If None, commits all staged files.
            author: Optional author string (e.g., "Name <email>")

        Returns:
            Dict with commit information
        """
        # Stage files if specified
        if files:
            add_result = await self.add_files(files)
            if not add_result["success"]:
                return {
                    "success": False,
                    "error": f"Failed to stage files: {add_result['stderr']}"
                }

        # Build commit command
        args = ["commit", "-m", message]
        if author:
            args.extend(["--author", author])

        result = self._run_git_command(args)

        if result["success"]:
            # Get commit hash
            hash_result = self._run_git_command(["rev-parse", "HEAD"])
            commit_hash = hash_result["stdout"][:7] if hash_result["success"] else "unknown"

            return {
                "success": True,
                "commit_hash": commit_hash,
                "message": message
            }
        else:
            return {
                "success": False,
                "error": result["stderr"]
            }

    async def get_current_branch(self) -> Dict[str, Any]:
        """
        Get the name of the current branch.

        Returns:
            Dict with branch name
        """
        result = self._run_git_command(["branch", "--show-current"])

        if result["success"]:
            return {
                "success": True,
                "branch": result["stdout"]
            }
        else:
            return result

    async def get_remote_url(self, remote: str = "origin") -> Dict[str, Any]:
        """
        Get the URL of a remote.

        Args:
            remote: Remote name (default: origin)

        Returns:
            Dict with remote URL
        """
        result = self._run_git_command(["remote", "get-url", remote])

        if result["success"]:
            return {
                "success": True,
                "remote": remote,
                "url": result["stdout"]
            }
        else:
            return result

    async def get_last_commits(self, count: int = 5) -> Dict[str, Any]:
        """
        Get the last N commits.

        Args:
            count: Number of commits to retrieve

        Returns:
            Dict with commit list
        """
        result = self._run_git_command([
            "log",
            f"-{count}",
            "--pretty=format:%h|%an|%ar|%s"
        ])

        if not result["success"]:
            return result

        commits = []
        for line in result["stdout"].split("\n"):
            if not line:
                continue

            parts = line.split("|", 3)
            if len(parts) == 4:
                commits.append({
                    "hash": parts[0],
                    "author": parts[1],
                    "time": parts[2],
                    "message": parts[3]
                })

        return {
            "success": True,
            "commits": commits
        }

    async def push(
        self,
        remote: str = "origin",
        branch: Optional[str] = None,
        set_upstream: bool = False
    ) -> Dict[str, Any]:
        """
        Push changes to remote.

        Args:
            remote: Remote name (default: origin)
            branch: Branch name. If None, uses current branch.
            set_upstream: Whether to set upstream tracking

        Returns:
            Dict with operation result
        """
        if branch is None:
            branch_result = await self.get_current_branch()
            if not branch_result["success"]:
                return branch_result
            branch = branch_result["branch"]

        args = ["push"]
        if set_upstream:
            args.extend(["-u", remote, branch])
        else:
            args.extend([remote, branch])

        result = self._run_git_command(args)
        return result

    async def auto_commit_and_push(
        self,
        message: str,
        files: Optional[List[str]] = None,
        create_branch: Optional[str] = None,
        push_to_remote: bool = False
    ) -> Dict[str, Any]:
        """
        Convenience method for complete workflow:
        optionally create branch → stage files → commit → optionally push.

        Args:
            message: Commit message
            files: Files to commit (None = all changes)
            create_branch: Optional new branch name
            push_to_remote: Whether to push after commit

        Returns:
            Dict with complete workflow results
        """
        workflow_results = []

        # Create branch if requested
        if create_branch:
            branch_result = await self.create_branch(create_branch, checkout=True)
            workflow_results.append(("create_branch", branch_result))
            if not branch_result["success"]:
                return {
                    "success": False,
                    "error": f"Failed to create branch: {branch_result.get('error')}",
                    "workflow": workflow_results
                }

        # Commit changes
        commit_result = await self.commit(message, files)
        workflow_results.append(("commit", commit_result))
        if not commit_result["success"]:
            return {
                "success": False,
                "error": f"Failed to commit: {commit_result.get('error')}",
                "workflow": workflow_results
            }

        # Push if requested
        if push_to_remote:
            push_result = await self.push(set_upstream=bool(create_branch))
            workflow_results.append(("push", push_result))
            if not push_result["success"]:
                return {
                    "success": False,
                    "error": f"Failed to push: {push_result.get('stderr')}",
                    "workflow": workflow_results
                }

        return {
            "success": True,
            "workflow": workflow_results,
            "commit_hash": commit_result.get("commit_hash")
        }
