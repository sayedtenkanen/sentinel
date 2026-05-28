"""Context Hub — versioned, editable storage for review rules (ADLC Deploy phase).

Provides a centralized storage abstraction for configuration profiles,
suppression policies, and agent settings, with version tracking.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROFILES_DIR_NAME = ".sentinel-profiles"


@dataclass
class ProfileEntry:
    key: str
    value: Any
    version: str
    updated_at: str
    description: str = ""


@dataclass
class Profile:
    name: str
    entries: dict[str, ProfileEntry] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "entries": {
                k: {
                    "value": v.value,
                    "version": v.version,
                    "updated_at": v.updated_at,
                    "description": v.description,
                }
                for k, v in self.entries.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> Profile:
        entries = {}
        for k, v in data.get("entries", {}).items():
            entries[k] = ProfileEntry(
                key=k,
                value=v["value"],
                version=v.get("version", ""),
                updated_at=v.get("updated_at", ""),
                description=v.get("description", ""),
            )
        return cls(
            name=data["name"],
            entries=entries,
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


class ContextHub:
    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir = Path(base_dir or Path.cwd() / PROFILES_DIR_NAME)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _profile_path(self, name: str) -> Path:
        return self.base_dir / f"{name}.json"

    def list_profiles(self) -> list[str]:
        return sorted(p.stem for p in self.base_dir.glob("*.json") if not p.name.startswith("."))

    def get_profile(self, name: str) -> Profile | None:
        path = self._profile_path(name)
        if not path.exists():
            return None
        with open(path) as f:
            return Profile.from_dict(json.load(f))

    def create_profile(self, name: str, entries: dict[str, Any] | None = None) -> Profile:
        if self._profile_path(name).exists():
            raise FileExistsError(f"Profile '{name}' already exists")
        now = datetime.now(timezone.utc).isoformat()
        profile = Profile(name=name, created_at=now, updated_at=now)
        if entries:
            for k, v in entries.items():
                profile.entries[k] = ProfileEntry(
                    key=k,
                    value=v,
                    version=self._hash(v),
                    updated_at=now,
                )
        self._save_profile(profile)
        return profile

    def set_entry(
        self, profile_name: str, key: str, value: Any, description: str = ""
    ) -> ProfileEntry:
        profile = self.get_profile(profile_name)
        if profile is None:
            raise KeyError(f"Profile '{profile_name}' not found")
        now = datetime.now(timezone.utc).isoformat()
        entry = ProfileEntry(
            key=key,
            value=value,
            version=self._hash(value),
            updated_at=now,
            description=description,
        )
        profile.entries[key] = entry
        profile.updated_at = now
        self._save_profile(profile)
        return entry

    def get_entry(self, profile_name: str, key: str) -> ProfileEntry | None:
        profile = self.get_profile(profile_name)
        if profile is None:
            return None
        return profile.entries.get(key)

    def delete_entry(self, profile_name: str, key: str) -> bool:
        profile = self.get_profile(profile_name)
        if profile is None or key not in profile.entries:
            return False
        del profile.entries[key]
        now = datetime.now(timezone.utc).isoformat()
        profile.updated_at = now
        self._save_profile(profile)
        return True

    def delete_profile(self, name: str) -> bool:
        path = self._profile_path(name)
        if not path.exists():
            return False
        path.unlink()
        return True

    def _save_profile(self, profile: Profile) -> None:
        path = self._profile_path(profile.name)
        with open(path, "w") as f:
            json.dump(profile.to_dict(), f, indent=2)

    @staticmethod
    def _hash(value: Any) -> str:
        raw = json.dumps(value, sort_keys=True).encode()
        return hashlib.sha256(raw).hexdigest()[:12]
