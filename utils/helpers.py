# utils/helpers.py
import discord
from datetime import datetime, timezone
from utils.emojis import E

# ── Paleta de cores ───────────────────────────────────────────────────────────
BRAND_COLOR   = 0x5865F2
SUCCESS_COLOR = 0x57F287
ERROR_COLOR   = 0xED4245
WARN_COLOR    = 0xFEE75C
INFO_COLOR    = 0x5865F2
TICKET_COLOR  = 0x2F3136
PHILO_COLOR   = 0x9B59B6


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def embed_success(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(
        title=f"{E['verified']} {title}",
        description=description,
        color=SUCCESS_COLOR,
        timestamp=_now(),
    )


def embed_error(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(
        title=f"{E['exclaim']} {title}",
        description=description,
        color=ERROR_COLOR,
        timestamp=_now(),
    )


def embed_warn(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(
        title=f"{E['warning']} {title}",
        description=description,
        color=WARN_COLOR,
        timestamp=_now(),
    )


def embed_info(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(
        title=f"{E['star']} {title}",
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
        title=f"{E['fire_white']} Moderação — {action}",
        color=ERROR_COLOR,
        timestamp=_now(),
    )
    e.add_field(name=f"{E['arrow_white']} Usuário",  value=f"{target.mention} (`{target.id}`)", inline=True)
    e.add_field(name=f"{E['pin']} Moderador",        value=moderator.mention, inline=True)
    e.add_field(name=f"{E['rules']} Motivo",         value=reason or "Não especificado", inline=False)
    if extra:
        e.add_field(name=f"{E['dash']} Informação adicional", value=extra, inline=False)
    if hasattr(target, "display_avatar"):
        e.set_thumbnail(url=target.display_avatar.url)
    return e


def duration_to_seconds(duration: str) -> int:
    """
    Converte strings como '10m', '2h', '1d', '1w' em segundos.
    Retorna 0 em caso de formato inválido.
    Limita a 28 dias (máximo do Discord para timeout).
    """
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    MAX_TIMEOUT = 60 * 60 * 24 * 28  # 28 dias
    try:
        if duration and duration[-1] in units:
            secs = int(duration[:-1]) * units[duration[-1]]
        else:
            secs = int(duration)
        return min(secs, MAX_TIMEOUT)
    except (ValueError, IndexError):
        return 0


def format_duration(seconds: int) -> str:
    """Formata segundos em string legível."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m"
    elif seconds < 86400:
        return f"{seconds // 3600}h"
    else:
        return f"{seconds // 86400}d"
