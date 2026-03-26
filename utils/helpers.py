"""
utils/helpers.py
Funções auxiliares para embeds e formatação. Sem emojis.
"""

import discord
from datetime import datetime, timezone

BRAND_COLOR   = 0x5865F2
SUCCESS_COLOR = 0x2ECC71
ERROR_COLOR   = 0xE74C3C
WARN_COLOR    = 0xF39C12
INFO_COLOR    = 0x5865F2
TICKET_COLOR  = 0x2C3E50
PHILO_COLOR   = 0x8E44AD


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def embed_success(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=SUCCESS_COLOR,
        timestamp=_now(),
    )


def embed_error(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=ERROR_COLOR,
        timestamp=_now(),
    )


def embed_warn(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=WARN_COLOR,
        timestamp=_now(),
    )


def embed_info(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=INFO_COLOR,
        timestamp=_now(),
    )


def embed_mod(
    action: str,
    target: discord.abc.User,
    moderator: discord.Member,
    reason: str,
    extra: str = "",
) -> discord.Embed:
    e = discord.Embed(
        title=f"Moderacao — {action}",
        color=ERROR_COLOR,
        timestamp=_now(),
    )
    e.add_field(name="Usuario",    value=f"{target.mention} (`{target.id}`)", inline=True)
    e.add_field(name="Moderador",  value=moderator.mention, inline=True)
    e.add_field(name="Motivo",     value=reason or "Nao especificado", inline=False)
    if extra:
        e.add_field(name="Informacao adicional", value=extra, inline=False)
    if hasattr(target, "display_avatar"):
        e.set_thumbnail(url=target.display_avatar.url)
    return e


def duration_to_seconds(duration: str) -> int:
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    MAX_TIMEOUT = 60 * 60 * 24 * 28
    try:
        if duration and duration[-1] in units:
            secs = int(duration[:-1]) * units[duration[-1]]
        else:
            secs = int(duration)
        return min(secs, MAX_TIMEOUT)
    except (ValueError, IndexError):
        return 0


def format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m"
    elif seconds < 86400:
        return f"{seconds // 3600}h"
    else:
        return f"{seconds // 86400}d"
