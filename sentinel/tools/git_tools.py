"""Git diff parsing and language detection utilities."""

from __future__ import annotations

import re


def parse_diff(diff_text: str) -> list[dict]:
    files = []
    current_file: dict | None = None

    for line in diff_text.split("\n"):
        if line.startswith("+++ b/"):
            if current_file:
                files.append(current_file)
            current_file = {"path": line[6:], "added": [], "removed": []}
        elif line.startswith("@@") and current_file:
            match = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if match:
                current_file["start_line"] = int(match.group(1))
                current_file["hunk_header"] = line
        elif current_file is not None:
            if line.startswith("+"):
                current_file["added"].append(line[1:])
            elif line.startswith("-"):
                current_file["removed"].append(line[1:])

    if current_file:
        files.append(current_file)

    return files


def detect_language(filename: str) -> str:
    ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescriptreact",
        ".jsx": "javascriptreact",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".rb": "ruby",
        ".php": "php",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".cs": "csharp",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "bash",
        ".sql": "sql",
        ".html": "html",
        ".css": "css",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".md": "markdown",
        ".rst": "markdown",
        ".dockerfile": "dockerfile",
        ".tf": "terraform",
    }
    import os

    _, ext = os.path.splitext(filename)
    return ext_map.get(ext.lower(), "")
