"""
utils/storage.py
Armazenamento de configurações por guild com cache em memória.
Suporta dois modos:
  1. guild_get / guild_set — configurações por guild (namespace + key)
  2. get / set / delete / load_all — armazenamento genérico por namespace + key
"""

import logging
import asyncio
from utils.db import Database

log = logging.getLogger("filosofia.storage")


class Storage:
    def __init__(self):
        # Cache de configurações por guild: {guild_id: {namespace: {key: value}}}
        self._guild_cache: dict = {}
        # Cache genérico: {namespace: {key: value}}
        self._generic_cache: dict = {}

    # ── Guild config (usado pela maioria dos cogs) ────────────────────────────

    def guild_get(self, guild_id: int, namespace: str, key: str):
        """Retorna o valor ou None se não existir."""
        return self._guild_cache.get(guild_id, {}).get(namespace, {}).get(key)

    def guild_set(self, guild_id: int, namespace: str, key: str, value):
        """Salva no cache e persiste no banco em background."""
        if guild_id not in self._guild_cache:
            self._guild_cache[guild_id] = {}
        if namespace not in self._guild_cache[guild_id]:
            self._guild_cache[guild_id][namespace] = {}
        self._guild_cache[guild_id][namespace][key] = value

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(Database.guild_set(guild_id, namespace, key, value))
        except RuntimeError:
            pass

    def guild_delete(self, guild_id: int, namespace: str, key: str):
        """Remove do cache e do banco."""
        self._guild_cache.get(guild_id, {}).get(namespace, {}).pop(key, None)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(Database.guild_delete(guild_id, namespace, key))
        except RuntimeError:
            pass

    # ── Armazenamento genérico (usado pelo cog academia) ─────────────────────

    def get(self, namespace: str, key: str):
        """Retorna um valor genérico ou None."""
        return self._generic_cache.get(namespace, {}).get(key)

    def set(self, namespace: str, key: str, value):
        """Salva um valor genérico no cache e persiste no banco."""
        if namespace not in self._generic_cache:
            self._generic_cache[namespace] = {}
        self._generic_cache[namespace][key] = value

        # Persiste no banco usando guild_id=0 como convenção para dados globais
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(Database.guild_set(0, namespace, key, value))
        except RuntimeError:
            pass

    def delete(self, namespace: str, key: str):
        """Remove um valor genérico do cache e do banco."""
        self._generic_cache.get(namespace, {}).pop(key, None)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(Database.guild_delete(0, namespace, key))
        except RuntimeError:
            pass

    def load_all(self, namespace: str) -> dict:
        """Retorna todos os pares key/value de um namespace genérico."""
        return dict(self._generic_cache.get(namespace, {}))

    # ── Pré-carregamento do banco ─────────────────────────────────────────────

    async def preload(self):
        """
        Carrega todos os dados do banco para o cache.
        Chamar uma vez no setup_hook antes de carregar os cogs.
        """
        try:
            rows = await Database.pool.fetch(
                "SELECT guild_id, namespace, key, value FROM guild_config"
            )
            for row in rows:
                gid, ns, k, v = row["guild_id"], row["namespace"], row["key"], row["value"]
                if gid == 0:
                    # Dados genéricos (academia_pending, etc.)
                    if ns not in self._generic_cache:
                        self._generic_cache[ns] = {}
                    self._generic_cache[ns][k] = v
                else:
                    # Dados por guild
                    if gid not in self._guild_cache:
                        self._guild_cache[gid] = {}
                    if ns not in self._guild_cache[gid]:
                        self._guild_cache[gid][ns] = {}
                    self._guild_cache[gid][ns][k] = v
            log.info(f"[STORAGE] {len(rows)} entradas carregadas do banco.")
        except Exception as e:
            log.error(f"[STORAGE] Falha ao pré-carregar dados: {e}")
