"""Review context model for files and configuration."""

from __future__ import annotations

from dataclasses import dataclass, field

from .types import FileContext, ReviewScope


@dataclass
class ReviewContext:
    scope: ReviewScope = ReviewScope.FULL_FILE
    files: list[FileContext] = field(default_factory=list)
    config: dict = field(
        default_factory=lambda: {
            "max_line_length": 100,
            "forbidden_patterns": [
                r"print\(.*\)",
                r"#\s*TODO",
                r"#\s*FIXME",
            ],
            "security_patterns": {
                "eval(": "Avoid eval() - can execute arbitrary code",
                "exec(": "Avoid exec() - can execute arbitrary code",
                "pickle.loads": "Unsafe deserialization with pickle",
                "subprocess.shell": "Shell injection risk with subprocess",
                "os.system": "Shell injection risk with os.system",
            },
            "complexity_threshold": 10,
            "nesting_depth_threshold": 4,
        }
    )

    @classmethod
    def from_file(cls, path: str, content: str) -> ReviewContext:
        return cls(files=[FileContext(path=path, content=content)])

    @classmethod
    def from_diff(cls, files: list[tuple[str, str]]) -> ReviewContext:
        ctx = cls(scope=ReviewScope.DIFF)
        for path, content in files:
            ctx.files.append(FileContext(path=path, content=content))
        return ctx
