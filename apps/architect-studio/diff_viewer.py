"""
Diff Viewer for Architect
Shows differences between original and generated code.
"""
import difflib
import os
from typing import Optional


class DiffViewer:
    """Display code differences in unified diff format."""

    def __init__(self, use_color: bool = True):
        self.use_color = use_color and self._supports_color()

    def _supports_color(self) -> bool:
        """Check if terminal supports color output."""
        return hasattr(os.sys.stdout, 'isatty') and os.sys.stdout.isatty()

    def _colorize(self, text: str, color: str) -> str:
        """Add ANSI color codes to text."""
        if not self.use_color:
            return text

        colors = {
            'red': '\033[91m',
            'green': '\033[92m',
            'cyan': '\033[96m',
            'yellow': '\033[93m',
            'reset': '\033[0m'
        }

        return f"{colors.get(color, '')}{text}{colors['reset']}"

    def show_diff(self, original_path: str, new_path: str, context_lines: int = 3) -> None:
        """
        Display unified diff between original and new file.

        Args:
            original_path: Path to original file
            new_path: Path to new/modified file
            context_lines: Number of context lines around changes
        """
        # Read files
        try:
            if os.path.exists(original_path):
                with open(original_path, 'r') as f:
                    original_lines = f.readlines()
                original_label = original_path
            else:
                original_lines = []
                original_label = "/dev/null (new file)"
        except Exception as e:
            print(f"Error reading original file: {e}")
            return

        try:
            with open(new_path, 'r') as f:
                new_lines = f.readlines()
        except Exception as e:
            print(f"Error reading new file: {e}")
            return

        # Generate unified diff
        diff = difflib.unified_diff(
            original_lines,
            new_lines,
            fromfile=original_label,
            tofile=new_path,
            lineterm='',
            n=context_lines
        )

        # Display with colors
        has_changes = False
        for line in diff:
            has_changes = True
            if line.startswith('---'):
                print(self._colorize(line, 'red'))
            elif line.startswith('+++'):
                print(self._colorize(line, 'green'))
            elif line.startswith('@@'):
                print(self._colorize(line, 'cyan'))
            elif line.startswith('-'):
                print(self._colorize(line, 'red'))
            elif line.startswith('+'):
                print(self._colorize(line, 'green'))
            else:
                print(line)

        if not has_changes:
            print("(No changes)")

    def show_diff_summary(self, original_path: str, new_path: str) -> dict:
        """
        Show summary statistics of changes.

        Returns:
            dict with keys: lines_added, lines_removed, lines_changed
        """
        try:
            if os.path.exists(original_path):
                with open(original_path, 'r') as f:
                    original_lines = f.readlines()
            else:
                original_lines = []

            with open(new_path, 'r') as f:
                new_lines = f.readlines()
        except Exception as e:
            print(f"Error: {e}")
            return {"lines_added": 0, "lines_removed": 0, "lines_changed": 0}

        # Calculate statistics
        diff = list(difflib.unified_diff(original_lines, new_lines, lineterm=''))

        lines_added = sum(1 for line in diff if line.startswith('+') and not line.startswith('+++'))
        lines_removed = sum(1 for line in diff if line.startswith('-') and not line.startswith('---'))

        return {
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "lines_changed": lines_added + lines_removed
        }

    def preview_file(self, file_path: str, max_lines: int = 50) -> None:
        """
        Show preview of a file (first N lines).

        Args:
            file_path: Path to file
            max_lines: Maximum number of lines to show
        """
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()

            print(f"\n{self._colorize('Preview:', 'cyan')} {file_path}")
            print("=" * 60)

            for i, line in enumerate(lines[:max_lines], 1):
                print(f"{i:4d} | {line}", end='')

            if len(lines) > max_lines:
                remaining = len(lines) - max_lines
                print(f"\n... ({remaining} more lines)")

            print("=" * 60)

        except Exception as e:
            print(f"Error reading file: {e}")


if __name__ == "__main__":
    # Test
    viewer = DiffViewer()
    print("Diff Viewer initialized. Use show_diff() to compare files.")
