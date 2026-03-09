from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class JSONCache:
    def __init__(self, file_path: Path, ttl_seconds: int):
        self._file_path = file_path
        self._ttl_seconds = max(ttl_seconds, 0)
        self._loaded = False
        self._store: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> Any | None:
        self._load()
        item = self._store.get(key)
        if not item:
            return None

        timestamp = item.get("ts")
        if not isinstance(timestamp, (int, float)):
            self._store.pop(key, None)
            self._persist()
            return None

        if self._ttl_seconds > 0 and (time.time() - float(timestamp)) > self._ttl_seconds:
            self._store.pop(key, None)
            self._persist()
            return None

        return item.get("value")

    def set(self, key: str, value: Any) -> None:
        self._load()
        self._store[key] = {"ts": time.time(), "value": value}
        self._persist()

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True

        if not self._file_path.exists():
            self._store = {}
            return

        try:
            raw_data = self._file_path.read_text(encoding="utf-8")
            parsed = json.loads(raw_data)
            if isinstance(parsed, dict):
                self._store = parsed
            else:
                self._store = {}
        except (OSError, json.JSONDecodeError):
            self._store = {}

    def _persist(self) -> None:
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._file_path.write_text(
            json.dumps(self._store, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
