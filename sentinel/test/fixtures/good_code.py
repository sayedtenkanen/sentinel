"""
good_code.py — known-good examples used in eval datasets (ADLC Test Phase).
Real-world patterns: Django views, FastAPI endpoints, proper async, auth decorators.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional


def load_config(path: str) -> dict:
    """Load configuration from a JSON file.

    Args:
        path: Path to the configuration file.

    Returns:
        Parsed configuration dictionary.
    """
    with open(path) as f:
        return json.load(f)


def process_items(
    items: list[str],
    batch_size: int = 10,
    max_items: Optional[int] = None,
) -> list[dict]:
    """Process a list of items in batches.

    Args:
        items: Items to process.
        batch_size: Number of items per batch.
        max_items: Maximum total items to process.

    Returns:
        List of processed item results.
    """
    results: list[dict] = []
    limit = min(len(items), max_items or len(items))

    for i in range(0, limit, batch_size):
        batch = items[i : i + batch_size]
        processed = _process_batch(batch)
        results.extend(processed)

    return results


def _process_batch(batch: list[str]) -> list[dict]:
    """Process a single batch of items.

    Args:
        batch: Items to process.

    Returns:
        Processed results for this batch.
    """
    return [{"item": item, "length": len(item)} for item in batch]


class DataProcessor:
    """Processes and transforms data through configurable pipelines."""

    def __init__(self, config: Optional[dict] = None) -> None:
        self.config = config or {}

    def transform(self, data: dict) -> dict:
        """Apply configured transformations to input data.

        Args:
            data: Input data dictionary.

        Returns:
            Transformed data.
        """
        result = dict(data)
        for key, transformer in self.config.get("transformers", {}).items():
            if key in result:
                result[key] = transformer(result[key])
        return result


def fetch_user(user_id: int) -> dict:
    """Fetch user from database with safe parameterized queries.

    Args:
        user_id: The user's unique identifier.

    Returns:
        User data dictionary.
    """
    import sqlite3

    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return {}
    return {"id": row[0], "name": row[1]}


def render_greeting(name: str) -> str:
    """Render a safe greeting using string formatting.

    Args:
        name: The user's name.

    Returns:
        Formatted greeting string.
    """
    return f"Hello, {name}!"


class Config:
    """Application configuration loaded from environment."""

    SECRET_KEY: str = os.environ.get("SECRET_KEY", "")
    DB_URL: str = os.environ.get("DATABASE_URL", "sqlite:///dev.db")
    DEBUG: bool = False

    @classmethod
    def is_safe(cls) -> bool:
        """Check if the configuration is in a safe state.

        Returns:
            True if not in debug mode with a default secret.
        """
        return not (cls.DEBUG and cls.SECRET_KEY == "")
