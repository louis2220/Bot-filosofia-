"""
cogs/cores.py
Sistema de Nick Color — cores normais e degradê (boosters/VIPs).
- Botões de pincel customizados com toggle automático
- /cores setup      → admin configura os cargos
- /cores painel     → envia painel de cores normais
- /cores painel_vip → envia painel de cores degradê (canal privado)
- /cores lista      → lista configuração atual
- /cores remover    → remove todas as cores de um membro
"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from utils.helpers import PHILO_COLOR, embed_success, embed_error, embed_info
from utils.storage import Storage
from utils.emojis import E

log = logging.getLogger("filosofia.cores")

# ── Cores normais ─────────────────────────────────────────────────────────────
# (key, label, emoji_pincel_customizado, hex_cor)
# Ordem conforme print: vermelho, laranja, amarelo, verde, azul, rosa, branco, marrom, roxo
CORES_NORMAIS = [
    ("vermelho", "Vermelho", "<:1000010231:1482084219814416464>", 0xE74C3C),
    ("laranja",  "Laranja",  "<:1000010232:1482092477946134579>", 0xE67E22),
    ("amarelo",  "Amarelo",  "<:1000010233:1482092507755188244>", 0xF1C40F),
    ("verde",    "Verde",    "<:1000010234:1482092539195424768>", 0x2ECC71),
    ("azul",     "Azul",     "<:1000010235:1482092570023825591>", 0x3498DB),
    ("rosa",     "Rosa",     "<:1000010236:1482092600172351589>", 0xFF69B4),
    ("marrom",   "Marrom",   "<:1000010263:1482103964215279706>", 0x8B4513),
    ("branco",   "Branco",   "<:1000010273:1482103994913525892>", 0xFFFFFF),
]

# ── Cores degradê ─────────────────────────────────────────────────────────────
# (key, label, emoji_pincel_customizado, descricao)
# Ordem conforme print: 11 pincéis degradê
CORES_DEGRADE = [
    ("grad_1", "Degradê 1", "<:1000010250:1482092724428603412>", "Degradê"),
    ("grad_2", "Degradê 2", "<:1000010264:1482104044699779173>", "Degradê"),
    ("grad_3", "Degradê 3", "<:1000010265:1482104072898347028>", "Degradê"),
    ("grad_4", "Degradê 4", "<:1000010266:1482104100320710778>", "Degradê"),
    ("grad_5", "Degradê 5", "<:1000010267:1482104126753079498>", "Degradê"),
    ("grad_6", "Degradê 6", "<:1000010268:1482104151751004421>", "Degradê"),
    ("grad_7", "Degradê 7", "<:1000010269:1482104177302966342>", "Degradê"),
    ("grad_8", "Degradê 8", "<:1000010270:1482104213315260466>", "Degradê"),
]


# ═════════════════════════════════════════════════════════════════════════════
# VIEWS — Cores Normais
# ═════════════════════════════════════════════════════════════════════════════

class ColorButton(discord.ui.Button):
    """Botão de cor individual com toggle automático."""

    def __init__(self, key: str, label: str, emoji_str: str, color_hex: int, row: int):
        super().__init__(
            label="​",
            emoji=discord.PartialEmoji.from_str(emoji_str),
            style=discord.ButtonStyle.secondary,
            custom_id=f"cores:normal:{key}",
            row=row,
        )
        self.key       = key
        self.color_hex = color_hex

    async def callback(self, inter: discord.Interaction):
        cog = inter.client.cogs.get("Cores")
        if cog:
            await cog.toggle_color_role(inter, self.key, degrade=False)


class ColorNormalView(discord.ui.View):
    """View persistente — 9 cores normais em 3 linhas de 3 (3+3+3)."""

    def __init__(self):
        super().__init__(timeout=None)
        for i, (key, label, emoji_str, hex_c) in enumerate(CORES_NORMAIS):
            row = i // 3
            self.add_item(ColorButton(key, label, emoji_str, hex_c, row=row))


# ═════════════════════════════════════════════════════════════════════════════
# VIEWS — Cores Degradê
# ═════════════════════════════════════════════════════════════════════════════

class DegradeButton(discord.ui.Button):
    """Botão de cor degradê individual."""

    def __init__(self, key: str, label: str, emoji_str: str, row: int):
        super().__init__(
            label="​",
            emoji=discord.PartialEmoji.from_str(emoji_str),
            style=discord.ButtonStyle.secondary,
            custom_id=f"cores:degrade:{key}",
            row=row,
        )
        self.key = key

    async def callback(self, inter: discord.Interaction):
        cog = inter.client.cogs.get("Cores")
        if cog:
            await cog.toggle_color_role(inter, self.key, degrade=True)


class ColorDegradeView(discord.ui.View):
    """View persistente — 11 cores degradê em 3 linhas (4 + 4 + 3)."""

    def __init__(self):
        super().__init__(timeout=None)
        for i, (key, label, emoji_str, _desc) in enumerate(CORES_DEGRADE):
            row = i // 4
            self.add_item(DegradeButton(key, label, emoji_str, row=row))


# ═════════════════════════════════════════════════════════════════════════════
# COG PRINCIPAL
# ═════════════════════════════════════════════════════════════════════════════

class Cores(commands.Cog):
    """Sistema de Nick Color — cores normais e degradê."""

    def __init__(self, bot: commands.Bot):
        self.bot     = bot
        self.storage: Storage = bot.storage
        bot.add_view(ColorNormalView())
        bot.add_view(ColorDegradeView())

    def _cfg(self, guild_id: int, key: str, default=None):
        return self.storage.guild_get(guild_id, "cores_config", key) or default

    def _set(self, guild_id: int, key: str, value):
        self.storage.guild_set(guild_id, "cores_config", key, value)

    def _role_id(self, guild_id: int, key: str) -> int | None:
        v = self._cfg(guild_id, f"role_{key}")
        return int(v) if v else None

    def _all_color_role_ids(self, guild_id: int) -> set:
        ids = set()
        for key, *_ in CORES_NORMAIS + CORES_DEGRADE:
            rid = self._role_id(guild_id, key)
            if rid:
                ids.add(rid)
        return ids

    # ── Toggle ────────────────────────────────────────────────────────────────

    async def toggle_color_role(self, inter: discord.Interaction, key: str, degrade: bool):
        await inter.response.defer(ephemeral=True)
        guild  = inter.guild
        member = inter.user

        role_id = self._role_id(guild.id, key)
        if not role_id:
            return await inter.followup.send(
                embed=embed_error(
                    "Cor não configurada",
                    f"Esta cor ainda não foi configurada.\n{E['bulb']} Um administrador deve usar `/cores setup`."
                ),
                ephemeral=True,
            )

        role = guild.get_role(role_id)
        if not role:
            return await inter.followup.send(
                embed=embed_error("Cargo não encontrado", "O cargo desta cor não existe mais no servidor."),
                ephemeral=True,
            )

        # Verifica acesso VIP para degradê
        if degrade:
            vip_channel_id = self._cfg(guild.id, "vip_channel")
            if vip_channel_id:
                vip_ch = guild.get_channel(int(vip_channel_id))
                if vip_ch:
                    perms = vip_ch.permissions_for(member)
                    if not perms.read_messages:
                        return await inter.followup.send(
                            embed=embed_error(
                                "Acesso restrito",
                                f"{E['exclaim']} As cores degradê são exclusivas para membros com acesso a {vip_ch.mention}.\n\n"
                                f"{E['star']} Impulsione o servidor ou adquira um cargo VIP para ter acesso!"
                            ),
                            ephemeral=True,
                        )

        # Toggle: já tem → remove
        if role in member.roles:
            await member.remove_roles(role, reason="Nick Color: removido pelo usuário")
            label = next((l for k, l, *_ in (CORES_DEGRADE if degrade else CORES_NORMAIS) if k == key), key)
            return await inter.followup.send(
                embed=discord.Embed(
                    description=f"{E['muted']} Cor **{label}** removida do seu perfil.",
                    color=0x99AAB5,
                ),
                ephemeral=True,
            )

        # Não tem → remove outras do mesmo tipo e adiciona a nova
        if degrade:
            same_keys = [k for k, *_ in CORES_DEGRADE]
        else:
            same_keys = [k for k, *_ in CORES_NORMAIS]

        same_ids = {self._role_id(guild.id, k) for k in same_keys if self._role_id(guild.id, k)}
        to_remove = [r for r in member.roles if r.id in same_ids]
        if to_remove:
            await member.remove_roles(*to_remove, reason="Nick Color: troca de cor")

        await member.add_roles(role, reason=f"Nick Color: {key}")

        label     = next((l for k, l, *_ in (CORES_DEGRADE if degrade else CORES_NORMAIS) if k == key), key)
        color_val = next((h for k, l, e, h in CORES_NORMAIS if k == key), PHILO_COLOR) if not degrade else PHILO_COLOR

        await inter.followup.send(
            embed=discord.Embed(
                description=(
                    f"{E['verified']} Cor **{label}** aplicada ao seu perfil!\n\n"
                    f"{E['dash']} Clique no mesmo botão novamente para remover."
                ),
                color=color_val,
            ),
            ephemeral=True,
        )

    # ═════════════════════════════════════════════════════════════════════════
    # SLASH COMMANDS
    # ═════════════════════════════════════════════════════════════════════════

    cores_group = app_commands.Group(name="cores", description="Sistema de Nick Color")

    @cores_group.command(name="setup", description="Configura o cargo de uma cor (normal ou degradê)")
    @app_commands.describe(
        cor="Cor a configurar",
        cargo="Cargo do Discord que representa esta cor",
    )
    @app_commands.choices(cor=[
        app_commands.Choice(name="Vermelho",  value="vermelho"),
        app_commands.Choice(name="Laranja",   value="laranja"),
        app_commands.Choice(name="Amarelo",   value="amarelo"),
        app_commands.Choice(name="Verde",     value="verde"),
        app_commands.Choice(name="Azul",      value="azul"),
        app_commands.Choice(name="Rosa",      value="rosa"),
        app_commands.Choice(name="Marrom",    value="marrom"),
        app_commands.Choice(name="Branco",    value="branco"),
        app_commands.Choice(name="Degradê 1", value="grad_1"),
        app_commands.Choice(name="Degradê 2", value="grad_2"),
        app_commands.Choice(name="Degradê 3", value="grad_3"),
        app_commands.Choice(name="Degradê 4", value="grad_4"),
        app_commands.Choice(name="Degradê 5", value="grad_5"),
        app_commands.Choice(name="Degradê 6", value="grad_6"),
        app_commands.Choice(name="Degradê 7", value="grad_7"),
        app_commands.Choice(name="Degradê 8", value="grad_8"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def cores_setup(self, inter: discord.Interaction, cor: str, cargo: discord.Role):
        self._set(inter.guild.id, f"role_{cor}", str(cargo.id))
        is_degrade = cor.startswith("grad_")
        label = next((l for k, l, *_ in (CORES_DEGRADE if is_degrade else CORES_NORMAIS) if k == cor), cor)
        emoji = next((e for k, l, e, *_ in (CORES_DEGRADE if is_degrade else CORES_NORMAIS) if k == cor), "🎨")
        await inter.response.send_message(
            embed=embed_success(
                "Cor configurada!",
                f"{emoji} **{label}** → {cargo.mention}\n"
                f"{E['dash']} Tipo: {'Degradê' if is_degrade else 'Normal'}\n\n"
                f"{E['arrow_blue']} Use `/cores painel` ou `/cores painel_vip` para atualizar o painel."
            ),
            ephemeral=True,
        )

    @cores_group.command(name="setup_vip", description="Define o canal VIP — apenas quem tem acesso pode pegar cores degradê")
    @app_commands.describe(canal="Canal privado de boosters/VIPs")
    @app_commands.default_permissions(administrator=True)
    async def cores_setup_vip(self, inter: discord.Interaction, canal: discord.TextChannel):
        self._set(inter.guild.id, "vip_channel", str(canal.id))
        await inter.response.send_message(
            embed=embed_success(
                "Canal VIP definido",
                f"{E['star']} Apenas membros com acesso a {canal.mention} poderão pegar cores degradê.\n\n"
                f"{E['bulb']} Envie o painel degradê nesse canal com `/cores painel_vip`."
            ),
            ephemeral=True,
        )

    @cores_group.command(name="painel", description="Envia o painel de cores normais no canal")
    @app_commands.describe(canal="Canal onde enviar (padrão: canal atual)")
    @app_commands.default_permissions(manage_guild=True)
    async def cores_painel(self, inter: discord.Interaction, canal: discord.TextChannel = None):
        ch = canal or inter.channel

        linhas = []
        for key, label, emoji_str, hex_c in CORES_NORMAIS:
            rid  = self._role_id(inter.guild.id, key)
            role = inter.guild.get_role(rid) if rid else None
            linhas.append(f"{emoji_str} **{label}** → {role.mention if role else '*não configurada*'}")

        emb = discord.Embed(
            title="🎨 | Nick Color",
            description=(
                f"{E['star']} Cansou da cor do seu apelido? Deixe seu perfil mais colorido!\n\n"
                + "\n".join(linhas) +
                f"\n\n**Como usar:**\n"
                f"1. Clique no botão com o pincel da cor desejada\n"
                f"2. Seu apelido receberá a nova cor automaticamente\n"
                f"3. Clique no mesmo botão novamente para remover"
            ),
            color=PHILO_COLOR,
        )
        emb.set_footer(text="Filosofia Bot • Nick Color — apenas uma cor por vez")
        await ch.send(embed=emb, view=ColorNormalView())
        await inter.response.send_message(
            embed=embed_success("Painel enviado!", f"Painel de cores enviado em {ch.mention}."),
            ephemeral=True,
        )

    @cores_group.command(name="painel_vip", description="Envia o painel de cores degradê (canal privado VIP)")
    @app_commands.describe(canal="Canal privado onde enviar")
    @app_commands.default_permissions(manage_guild=True)
    async def cores_painel_vip(self, inter: discord.Interaction, canal: discord.TextChannel = None):
        ch = canal or inter.channel

        linhas = []
        for key, label, emoji_str, desc in CORES_DEGRADE:
            rid  = self._role_id(inter.guild.id, key)
            role = inter.guild.get_role(rid) if rid else None
            linhas.append(f"{emoji_str} **{label}** → {role.mention if role else '*não configurada*'}")

        emb = discord.Embed(
            title="✨ | Nick Color — Degradê Exclusivo",
            description=(
                f"{E['trophy']} Benefício exclusivo para membros especiais!\n\n"
                f"{E['fire_blue']} **Cores com gradiente disponíveis:**\n"
                + "\n".join(linhas) +
                f"\n\n{E['bulb']} **Sobre cores degradê:**\n"
                f"Os cargos degradê usam o recurso de cor em gradiente do Discord.\n"
                f"Configure em **Cargos → [cargo] → Cor → Gradiente**.\n\n"
                f"**Como usar:**\n"
                f"1. Clique no botão da cor desejada\n"
                f"2. Seu nome receberá o gradiente automaticamente\n"
                f"3. Clique novamente para remover"
            ),
            color=0x9B59B6,
        )
        emb.set_footer(text="Filosofia Bot • Nick Color Degradê — benefício exclusivo")
        await ch.send(embed=emb, view=ColorDegradeView())
        await inter.response.send_message(
            embed=embed_success("Painel VIP enviado!", f"Painel degradê enviado em {ch.mention}."),
            ephemeral=True,
        )

    @cores_group.command(name="lista", description="Lista todos os cargos de cor configurados no servidor")
    @app_commands.default_permissions(manage_guild=True)
    async def cores_lista(self, inter: discord.Interaction):
        emb = discord.Embed(title=f"{E['bulb']} Nick Color — Configuração", color=PHILO_COLOR)

        normais_txt = []
        for key, label, emoji_str, _ in CORES_NORMAIS:
            rid  = self._role_id(inter.guild.id, key)
            role = inter.guild.get_role(rid) if rid else None
            normais_txt.append(f"{emoji_str} {label}: {role.mention if role else '`não configurado`'}")
        emb.add_field(name="🎨 Cores Normais", value="\n".join(normais_txt), inline=False)

        degrade_txt = []
        for key, label, emoji_str, _ in CORES_DEGRADE:
            rid  = self._role_id(inter.guild.id, key)
            role = inter.guild.get_role(rid) if rid else None
            degrade_txt.append(f"{emoji_str} {label}: {role.mention if role else '`não configurado`'}")
        emb.add_field(name="✨ Cores Degradê", value="\n".join(degrade_txt), inline=False)

        vip_ch_id = self._cfg(inter.guild.id, "vip_channel")
        vip_ch    = inter.guild.get_channel(int(vip_ch_id)) if vip_ch_id else None
        emb.add_field(name=f"{E['star']} Canal VIP", value=vip_ch.mention if vip_ch else "`não configurado`", inline=False)
        emb.set_footer(text="Filosofia Bot • /cores lista")
        await inter.response.send_message(embed=emb, ephemeral=True)

    @cores_group.command(name="remover", description="Remove todas as cores de nick de um membro")
    @app_commands.describe(membro="Membro alvo")
    @app_commands.default_permissions(manage_roles=True)
    async def cores_remover(self, inter: discord.Interaction, membro: discord.Member):
        await inter.response.defer(ephemeral=True)
        all_ids   = self._all_color_role_ids(inter.guild.id)
        to_remove = [r for r in membro.roles if r.id in all_ids]
        if to_remove:
            await membro.remove_roles(*to_remove, reason=f"Nick Color: remoção por {inter.user}")
        await inter.followup.send(
            embed=embed_success("Cores removidas", f"Todas as cores de {membro.mention} foram removidas."),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Cores(bot))
