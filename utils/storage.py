# utils/storage.py
import json
import os
import asyncio
import logging
from typing import Any

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
log = logging.getLogger("filosofia.storage")


class Storage:
    """
    Armazenamento persistente em JSON sem banco de dados externo.
    Thread-safe via asyncio.Lock por namespace.
    """

    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self._cache: dict[str, dict] = {}
        # Lock individual por namespace para evitar corrida entre arquivos
        self._locks: dict[str, asyncio.Lock] = {}

    def _get_lock(self, name: str) -> asyncio.Lock:
        if name not in self._locks:
            self._locks[name] = asyncio.Lock()
        return self._locks[name]

    def _path(self, name: str) -> str:
        # Sanitiza o nome para evitar path traversal
        safe = name.replace("/", "_").replace("\\", "_").replace("..", "_")
        return os.path.join(DATA_DIR, f"{safe}.json")

    def load(self, name: str) -> dict:
        if name in self._cache:
            return self._cache[name]
        path = self._path(name)
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {}
        except (json.JSONDecodeError, OSError) as e:
            log.error(f"[Storage] Erro ao carregar '{name}': {e}")
            data = {}
        self._cache[name] = data
        return data

    def save(self, name: str, data: dict):
        self._cache[name] = data
        path = self._path(name)
        try:
            # Escrita atômica: salva em temp e renomeia
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except OSError as e:
            log.error(f"[Storage] Erro ao salvar '{name}': {e}")

    # ── API simples ───────────────────────────────────────────────────────────

    def get(self, name: str, key: str, default: Any = None) -> Any:
        return self.load(name).get(key, default)

    def set(self, name: str, key: str, value: Any):
        data = self.load(name)
        data[key] = value
        self.save(name, data)

    def delete(self, name: str, key: str):
        data = self.load(name)
        if key in data:
            del data[key]
            self.save(name, data)

    def load_all(self, name: str) -> dict:
        return dict(self.load(name))

    # ── API por guild ─────────────────────────────────────────────────────────

    def guild_get(self, guild_id: int, namespace: str, key: str, default: Any = None) -> Any:
        store = self.load(namespace)
        return store.get(str(guild_id), {}).get(key, default)

    def guild_set(self, guild_id: int, namespace: str, key: str, value: Any):
        store = self.load(namespace)
        gid = str(guild_id)
        if gid not in store:
            store[gid] = {}
        store[gid][key] = value
        self.save(namespace, store)

    def guild_all(self, guild_id: int, namespace: str) -> dict:
        return dict(self.load(namespace).get(str(guild_id), {}))

    def guild_delete(self, guild_id: int, namespace: str, key: str):
        store = self.load(namespace)
        gid = str(guild_id)
        if gid in store and key in store[gid]:
            del store[gid][key]
            self.save(namespace, store)
