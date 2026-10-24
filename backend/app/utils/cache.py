"""Tiny JSON file cache with expiry (used for research results)."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path


class FileCache:
    def __init__(self, directory: str | Path, ttl_seconds: int):
        self.dir = Path(directory)
        self.ttl = ttl_seconds
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.dir / (hashlib.sha256(key.encode()).hexdigest()[:32] + ".json")

    def get(self, key: str):
        if self.ttl <= 0:
            return None
        path = self._path(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if time.time() - payload.get("stored_at", 0) > self.ttl:
            return None
        return payload.get("value")

    def set(self, key: str, value) -> None:
        if self.ttl <= 0:
            return
        try:
            self._path(key).write_text(
                json.dumps({"stored_at": time.time(), "key": key, "value": value}), encoding="utf-8"
            )
        except OSError:
            pass
