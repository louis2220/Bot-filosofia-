"""
utils/storage.py
Armazenamento de configurações por guild com cache em memória.
Os dados são carregados do PostgreSQL na inicialização e salvos de volta
a cada escrita, permitindo uso síncrono nos cogs.
"""

import logging
from utils.db import Database

log = logging.getLogger("filosofia.storage")


class Storage:
    """
    Cache em memória de configurações por guild.
    Uso nos cogs (síncrono):
        valor = self.storage.guild_get(guild_id, namespace, key)
        self.storage.guild_set(guild_id, namespace, key, valor)
    """

    def __init__(self):
        # _cache[guild_id][namespace][key] = value
        self._cache: dict = {}

    def guild_get(self, guild_id: int, namespace: str, key: str):
        """Retorna o valor ou None se não existir."""
        return self._cache.get(guild_id, {}).get(namespace, {}).get(key)

    def guild_set(self, guild_id: int, namespace: str, key: str, value):
        """Salva no cache em memória e persiste no banco em background."""
        if guild_id not in self._cache:
            self._cache[guild_id] = {}
        if namespace not in self._cache[guild_id]:
            self._cache[guild_id][namespace] = {}
        self._cache[guild_id][namespace][key] = value

        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(Database.guild_set(guild_id, namespace, key, value))
        except RuntimeError:
            pass

    def guild_delete(self, guild_id: int, namespace: str, key: str):
        """Remove do cache e do banco."""
        self._cache.get(guild_id, {}).get(namespace, {}).pop(key, None)
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(Database.guild_delete(guild_id, namespace, key))
        except RuntimeError:
            pass

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
                if gid not in self._cache:
                    self._cache[gid] = {}
                if ns not in self._cache[gid]:
                    self._cache[gid][ns] = {}
                self._cache[gid][ns][k] = v
            log.info(f"[STORAGE] {len(rows)} entradas carregadas do banco.")
        except Exception as e:
            log.error(f"[STORAGE] Falha ao pré-carregar dados: {e}")
