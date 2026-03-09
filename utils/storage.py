import json
import os
import asyncio
from typing import Any, Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

class Storage:
    """Armazenamento persistente em JSON, sem banco de dados."""

    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self._cache: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    def _path(self, name: str) -> str:
        return os.path.join(DATA_DIR, f"{name}.json")

    def load(self, name: str) -> dict:
        if name in self._cache:
            return self._cache[name]
        path = self._path(name)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}
        self._cache[name] = data
        return data

    def save(self, name: str, data: dict):
        self._cache[name] = data
        path = self._path(name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get(self, name: str, key: str, default: Any = None) -> Any:
        return self.load(name).get(key, default)

    def set(self, name: str, key: str, value: Any):
        data = self.load(name)
        data[key] = value
        self.save(name, data)

    def delete(self, name: str, key: str):
        data = self.load(name)
        data.pop(key, None)
        self.save(name, data)

    def guild_get(self, guild_id: int, namespace: str, key: str, default: Any = None) -> Any:
        store = self.load(namespace)
        guild_data = store.get(str(guild_id), {})
        return guild_data.get(key, default)

    def guild_set(self, guild_id: int, namespace: str, key: str, value: Any):
        store = self.load(namespace)
        gid = str(guild_id)
        if gid not in store:
            store[gid] = {}
        store[gid][key] = value
        self.save(namespace, store)

    def guild_all(self, guild_id: int, namespace: str) -> dict:
        store = self.load(namespace)
        return store.get(str(guild_id), {})
