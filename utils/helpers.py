import discord
from datetime import datetime
from utils.emojis import E

BRAND_COLOR   = 0x5865F2
SUCCESS_COLOR = 0x57F287
ERROR_COLOR   = 0xED4245
WARN_COLOR    = 0xFEE75C
INFO_COLOR    = 0x5865F2
TICKET_COLOR  = 0x2F3136
PHILO_COLOR   = 0x9B59B6


def embed_success(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(
        title=f"{E['verified']} {title}",
        description=description,
        color=SUCCESS_COLOR,
        timestamp=datetime.utcnow()
    )


def embed_error(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(
        title=f"{E['exclaim']} {title}",
        description=description,
        color=ERROR_COLOR,
        timestamp=datetime.utcnow()
    )


def embed_warn(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(
        title=f"{E['warning']} {title}",
        description=description,
        color=WARN_COLOR,
        timestamp=datetime.utcnow()
    )


def embed_info(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(
        title=f"{E['star']} {title}",
        description=description,
        color=INFO_COLOR,
        timestamp=datetime.utcnow()
    )


def embed_mod(action: str, target, moderator: discord.Member, reason: str, extra: str = "") -> discord.Embed:
    e = discord.Embed(
        title=f"{E['fire_white']} Moderação — {action}",
        color=ERROR_COLOR,
        timestamp=datetime.utcnow()
    )
    e.add_field(name=f"{E['arrow_white']} Usuário",  value=f"{target.mention} (`{target.id}`)", inline=True)
    e.add_field(name=f"{E['pin']} Moderador",        value=f"{moderator.mention}", inline=True)
    e.add_field(name=f"{E['rules']} Motivo",         value=reason or "Não especificado", inline=False)
    if extra:
        e.add_field(name=f"{E['dash']} Info extra",  value=extra, inline=False)
    if hasattr(target, 'display_avatar'):
        e.set_thumbnail(url=target.display_avatar.url)
    return e


def duration_to_seconds(duration: str) -> int:
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    try:
        if duration[-1] in units:
            return int(duration[:-1]) * units[duration[-1]]
        return int(duration)
    except Exception:
        return 0
