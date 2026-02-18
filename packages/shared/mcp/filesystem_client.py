"""
Filesystem MCP Client.
Provides advanced file operations with better error handling, atomic writes,
and directory watching capabilities.
"""
import os
import asyncio
import aiofiles
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, AsyncIterator
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent


class FilesystemWatcher(FileSystemEventHandler):
    """Handler for filesystem events."""

    def __init__(self, patterns: List[str], callback):
        super().__init__()
        self.patterns = patterns
        self.callback = callback

    def _matches_pattern(self, path: str) -> bool:
        """Check if path matches any watch pattern."""
        from fnmatch import fnmatch
        for pattern in self.patterns:
            if fnmatch(path, pattern):
                return True
        return False

    def on_any_event(self, event: FileSystemEvent):
        """Handle any filesystem event."""
        if event.is_directory:
            return

        if self._matches_pattern(event.src_path):
            asyncio.create_task(self.callback({
                'type': event.event_type,
                'path': event.src_path,
                'timestamp': datetime.now().isoformat()
            }))


class FilesystemMCPClient:
    """
    Client for advanced filesystem operations.
    Can be used by both Architect and Brain for file management.
    """

    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize filesystem client.

        Args:
            base_path: Base path for all operations (defaults to cwd)
        """
        self.base_path = Path(base_path or os.getcwd())
        self.observers: Dict[str, Observer] = {}

    def _resolve_path(self, path: str) -> Path:
        """Resolve path relative to base_path."""
        p = Path(path)
        if p.is_absolute():
            return p
        return self.base_path / p

    async def read_file(self, path: str, encoding: str = 'utf-8') -> Dict[str, Any]:
        """
        Read file with automatic encoding detection.

        Args:
            path: File path
            encoding: File encoding (default: utf-8)

        Returns:
            Dict with file content and metadata
        """
        try:
            resolved_path = self._resolve_path(path)

            if not resolved_path.exists():
                return {
                    "success": False,
                    "error": f"File not found: {path}"
                }

            async with aiofiles.open(resolved_path, 'r', encoding=encoding) as f:
                content = await f.read()

            stat = resolved_path.stat()

            return {
                "success": True,
                "content": content,
                "path": str(resolved_path),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "encoding": encoding
            }
        except UnicodeDecodeError:
            # Try reading as binary
            try:
                async with aiofiles.open(resolved_path, 'rb') as f:
                    content = await f.read()
                return {
                    "success": True,
                    "content": content.hex(),
                    "path": str(resolved_path),
                    "encoding": "binary",
                    "note": "File read as binary (hex encoded)"
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to read file: {str(e)}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to read file: {str(e)}"
            }

    async def write_file(
        self,
        path: str,
        content: str,
        encoding: str = 'utf-8',
        atomic: bool = True,
        create_dirs: bool = True
    ) -> Dict[str, Any]:
        """
        Write file with atomic operation support.

        Args:
            path: File path
            content: Content to write
            encoding: File encoding
            atomic: Use atomic write (write to temp, then rename)
            create_dirs: Create parent directories if needed

        Returns:
            Dict with operation result
        """
        try:
            resolved_path = self._resolve_path(path)

            # Create parent directories
            if create_dirs:
                resolved_path.parent.mkdir(parents=True, exist_ok=True)

            if atomic:
                # Atomic write: write to temp file, then rename
                temp_path = resolved_path.with_suffix(resolved_path.suffix + '.tmp')
                async with aiofiles.open(temp_path, 'w', encoding=encoding) as f:
                    await f.write(content)
                temp_path.rename(resolved_path)
            else:
                # Direct write
                async with aiofiles.open(resolved_path, 'w', encoding=encoding) as f:
                    await f.write(content)

            stat = resolved_path.stat()

            return {
                "success": True,
                "path": str(resolved_path),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to write file: {str(e)}"
            }

    async def append_file(
        self,
        path: str,
        content: str,
        encoding: str = 'utf-8'
    ) -> Dict[str, Any]:
        """
        Append content to file.

        Args:
            path: File path
            content: Content to append
            encoding: File encoding

        Returns:
            Dict with operation result
        """
        try:
            resolved_path = self._resolve_path(path)

            async with aiofiles.open(resolved_path, 'a', encoding=encoding) as f:
                await f.write(content)

            stat = resolved_path.stat()

            return {
                "success": True,
                "path": str(resolved_path),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to append to file: {str(e)}"
            }

    async def delete_file(self, path: str) -> Dict[str, Any]:
        """
        Delete file.

        Args:
            path: File path

        Returns:
            Dict with operation result
        """
        try:
            resolved_path = self._resolve_path(path)

            if not resolved_path.exists():
                return {
                    "success": False,
                    "error": f"File not found: {path}"
                }

            resolved_path.unlink()

            return {
                "success": True,
                "path": str(resolved_path),
                "deleted": True
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to delete file: {str(e)}"
            }

    async def copy_file(self, src: str, dest: str) -> Dict[str, Any]:
        """
        Copy file.

        Args:
            src: Source file path
            dest: Destination file path

        Returns:
            Dict with operation result
        """
        try:
            import shutil

            src_path = self._resolve_path(src)
            dest_path = self._resolve_path(dest)

            if not src_path.exists():
                return {
                    "success": False,
                    "error": f"Source file not found: {src}"
                }

            # Create destination directory if needed
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            shutil.copy2(src_path, dest_path)

            stat = dest_path.stat()

            return {
                "success": True,
                "src": str(src_path),
                "dest": str(dest_path),
                "size": stat.st_size
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to copy file: {str(e)}"
            }

    async def move_file(self, src: str, dest: str) -> Dict[str, Any]:
        """
        Move/rename file.

        Args:
            src: Source file path
            dest: Destination file path

        Returns:
            Dict with operation result
        """
        try:
            src_path = self._resolve_path(src)
            dest_path = self._resolve_path(dest)

            if not src_path.exists():
                return {
                    "success": False,
                    "error": f"Source file not found: {src}"
                }

            # Create destination directory if needed
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            src_path.rename(dest_path)

            return {
                "success": True,
                "src": str(src_path),
                "dest": str(dest_path)
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to move file: {str(e)}"
            }

    async def get_file_hash(self, path: str, algorithm: str = 'sha256') -> Dict[str, Any]:
        """
        Calculate file hash.

        Args:
            path: File path
            algorithm: Hash algorithm (md5, sha1, sha256)

        Returns:
            Dict with hash value
        """
        try:
            resolved_path = self._resolve_path(path)

            if not resolved_path.exists():
                return {
                    "success": False,
                    "error": f"File not found: {path}"
                }

            hash_obj = hashlib.new(algorithm)

            async with aiofiles.open(resolved_path, 'rb') as f:
                while chunk := await f.read(8192):
                    hash_obj.update(chunk)

            return {
                "success": True,
                "path": str(resolved_path),
                "algorithm": algorithm,
                "hash": hash_obj.hexdigest()
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to calculate hash: {str(e)}"
            }

    async def list_directory(
        self,
        path: str = ".",
        recursive: bool = False,
        max_depth: int = 3,
        patterns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        List directory contents.

        Args:
            path: Directory path
            recursive: List recursively
            max_depth: Maximum recursion depth
            patterns: File patterns to match (e.g., ["*.py", "*.ts"])

        Returns:
            Dict with directory tree
        """
        try:
            from fnmatch import fnmatch

            resolved_path = self._resolve_path(path)

            if not resolved_path.exists():
                return {
                    "success": False,
                    "error": f"Directory not found: {path}"
                }

            if not resolved_path.is_dir():
                return {
                    "success": False,
                    "error": f"Not a directory: {path}"
                }

            def scan_dir(dir_path: Path, depth: int = 0) -> List[Dict]:
                """Recursively scan directory."""
                items = []

                if depth > max_depth:
                    return items

                try:
                    for entry in dir_path.iterdir():
                        # Skip hidden files
                        if entry.name.startswith('.'):
                            continue

                        stat = entry.stat()
                        item = {
                            "name": entry.name,
                            "path": str(entry.relative_to(resolved_path)),
                            "type": "directory" if entry.is_dir() else "file",
                            "size": stat.st_size if entry.is_file() else None,
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                        }

                        # Filter by pattern
                        if patterns and entry.is_file():
                            matches = any(fnmatch(entry.name, p) for p in patterns)
                            if not matches:
                                continue

                        items.append(item)

                        # Recurse into subdirectories
                        if recursive and entry.is_dir():
                            item["children"] = scan_dir(entry, depth + 1)

                except PermissionError:
                    pass

                return items

            items = scan_dir(resolved_path)

            return {
                "success": True,
                "path": str(resolved_path),
                "items": items,
                "count": len(items)
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to list directory: {str(e)}"
            }

    async def watch_directory(
        self,
        path: str,
        patterns: List[str],
        callback
    ) -> Dict[str, Any]:
        """
        Watch directory for changes.

        Args:
            path: Directory path to watch
            patterns: File patterns to watch (e.g., ["**/*.py", "*.ts"])
            callback: Async function to call on changes

        Returns:
            Dict with watch ID
        """
        try:
            resolved_path = self._resolve_path(path)

            if not resolved_path.exists():
                return {
                    "success": False,
                    "error": f"Directory not found: {path}"
                }

            # Create observer
            observer = Observer()
            handler = FilesystemWatcher(patterns, callback)
            observer.schedule(handler, str(resolved_path), recursive=True)
            observer.start()

            # Store observer
            watch_id = str(resolved_path)
            self.observers[watch_id] = observer

            return {
                "success": True,
                "watch_id": watch_id,
                "path": str(resolved_path),
                "patterns": patterns
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to watch directory: {str(e)}"
            }

    async def unwatch_directory(self, watch_id: str) -> Dict[str, Any]:
        """
        Stop watching directory.

        Args:
            watch_id: Watch ID from watch_directory

        Returns:
            Dict with operation result
        """
        try:
            if watch_id not in self.observers:
                return {
                    "success": False,
                    "error": f"Watch not found: {watch_id}"
                }

            observer = self.observers[watch_id]
            observer.stop()
            observer.join()
            del self.observers[watch_id]

            return {
                "success": True,
                "watch_id": watch_id
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to unwatch directory: {str(e)}"
            }

    async def create_directory(
        self,
        path: str,
        parents: bool = True,
        exist_ok: bool = True
    ) -> Dict[str, Any]:
        """
        Create directory.

        Args:
            path: Directory path
            parents: Create parent directories
            exist_ok: Don't error if directory exists

        Returns:
            Dict with operation result
        """
        try:
            resolved_path = self._resolve_path(path)
            resolved_path.mkdir(parents=parents, exist_ok=exist_ok)

            return {
                "success": True,
                "path": str(resolved_path)
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create directory: {str(e)}"
            }

    async def delete_directory(
        self,
        path: str,
        recursive: bool = False
    ) -> Dict[str, Any]:
        """
        Delete directory.

        Args:
            path: Directory path
            recursive: Delete recursively (dangerous!)

        Returns:
            Dict with operation result
        """
        try:
            import shutil

            resolved_path = self._resolve_path(path)

            if not resolved_path.exists():
                return {
                    "success": False,
                    "error": f"Directory not found: {path}"
                }

            if recursive:
                shutil.rmtree(resolved_path)
            else:
                resolved_path.rmdir()

            return {
                "success": True,
                "path": str(resolved_path),
                "deleted": True
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to delete directory: {str(e)}"
            }

    async def get_disk_usage(self, path: str = ".") -> Dict[str, Any]:
        """
        Get disk usage statistics.

        Args:
            path: Directory path

        Returns:
            Dict with disk usage info
        """
        try:
            import shutil

            resolved_path = self._resolve_path(path)

            if not resolved_path.exists():
                return {
                    "success": False,
                    "error": f"Path not found: {path}"
                }

            usage = shutil.disk_usage(resolved_path)

            return {
                "success": True,
                "path": str(resolved_path),
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent_used": (usage.used / usage.total) * 100
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get disk usage: {str(e)}"
            }

    async def close(self):
        """Close all watchers."""
        for watch_id in list(self.observers.keys()):
            await self.unwatch_directory(watch_id)


# Context manager support
class FilesystemMCPClientContext:
    """Context manager for FilesystemMCPClient."""

    def __init__(self, *args, **kwargs):
        self.client = FilesystemMCPClient(*args, **kwargs)

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.close()
