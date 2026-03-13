"""
cogs/cores.py
Sistema de Nick Color — cores normais e degradê (boosters/VIPs).
- Botões só com emoji pincel (sem label), maiores com espaços
- Embed totalmente editável: título, descrição, cor, thumbnail, banner
- /cores painel     → envia painel normal (com opção de editar embed antes)
- /cores painel_vip → envia painel degradê (com opção de editar embed antes)
- /cores setup      → admin vincula cargo a cada cor
- /cores setup_vip  → define canal VIP para restrição de acesso
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

# ── Cores normais (8) ─────────────────────────────────────────────────────────
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

# ── Cores degradê (8) ─────────────────────────────────────────────────────────
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

# Espaços para forçar botão maior (mantém só o emoji visível)
BTN_PAD = "\u2000\u2000\u2000\u2000\u2000\u2000\u2000\u2000\u2000\u2000"


# ═════════════════════════════════════════════════════════════════════════════
# MODAL — Editor de Embed
# ═════════════════════════════════════════════════════════════════════════════

class EmbedEditorModal(discord.ui.Modal):
    titulo = discord.ui.TextInput(
        label="Título",
        default="🎨 | Nick Color",
        max_length=256,
    )
    descricao = discord.ui.TextInput(
        label="Descrição / Mensagem",
        style=discord.TextStyle.paragraph,
        default="Cansou da cor do seu apelido? Deixe seu perfil mais colorido!\n\nClique no pincel da cor desejada. Clique novamente para remover.",
        max_length=2000,
    )
    cor = discord.ui.TextInput(
        label="Cor hex (ex: #9B59B6)",
        default="#9B59B6",
        max_length=9,
        required=False,
    )
    thumbnail = discord.ui.TextInput(
        label="URL da miniatura (canto superior direito)",
        placeholder="https://i.imgur.com/exemplo.png",
        required=False,
        max_length=500,
    )
    banner = discord.ui.TextInput(
        label="URL do banner (imagem grande)",
        placeholder="https://i.imgur.com/exemplo.png",
        required=False,
        max_length=500,
    )

    def __init__(self, canal: discord.TextChannel, view_cls, title: str = "Configurar Painel"):
        super().__init__(title=title)
        self.canal    = canal
        self.view_cls = view_cls

    async def on_submit(self, inter: discord.Interaction):
        # Responde imediatamente para evitar timeout de 3s do Discord
        await inter.response.defer(ephemeral=True)

        try:
            color = int(self.cor.value.lstrip("#"), 16) if self.cor.value.strip() else PHILO_COLOR
        except ValueError:
            color = PHILO_COLOR

        emb = discord.Embed(
            title=self.titulo.value,
            description=self.descricao.value,
            color=color,
        )
        if self.thumbnail.value.strip():
            emb.set_thumbnail(url=self.thumbnail.value.strip())
        if self.banner.value.strip():
            emb.set_image(url=self.banner.value.strip())
        emb.set_footer(text="Filosofia Bot • Nick Color — apenas uma cor por vez")

        await self.canal.send(embed=emb, view=self.view_cls())
        await inter.followup.send(
            embed=embed_success("Painel enviado!", f"Painel enviado em {self.canal.mention}."),
            ephemeral=True,
        )


# ═════════════════════════════════════════════════════════════════════════════
# VIEW de confirmação — Enviar direto ou Editar embed
# ═════════════════════════════════════════════════════════════════════════════

class PainelConfirmView(discord.ui.View):
    def __init__(self, canal: discord.TextChannel, view_cls, default_title: str, default_desc: str, default_color: int):
        super().__init__(timeout=60)
        self.canal         = canal
        self.view_cls      = view_cls
        self.default_title = default_title
        self.default_desc  = default_desc
        self.default_color = default_color

    @discord.ui.button(label="Enviar padrão", style=discord.ButtonStyle.success,
                       emoji="<a:9582dsicordveriyblack:1430269158024810598>")
    async def enviar_padrao(self, inter: discord.Interaction, button: discord.ui.Button):
        emb = discord.Embed(
            title=self.default_title,
            description=self.default_desc,
            color=self.default_color,
        )
        emb.set_footer(text="Filosofia Bot • Nick Color — apenas uma cor por vez")
        await self.canal.send(embed=emb, view=self.view_cls())
        await inter.response.edit_message(
            embed=embed_success("Painel enviado!", f"Painel enviado em {self.canal.mention}."),
            view=None,
        )

    @discord.ui.button(label="Personalizar embed", style=discord.ButtonStyle.primary,
                       emoji="<:w_p:1445474432893063299>")
    async def personalizar(self, inter: discord.Interaction, button: discord.ui.Button):
        modal = EmbedEditorModal(
            canal=self.canal,
            view_cls=self.view_cls,
            title="Personalizar Painel",
        )
        modal.titulo.default    = self.default_title
        modal.descricao.default = self.default_desc
        modal.cor.default       = f"#{self.default_color:06X}"
        await inter.response.send_modal(modal)


# ═════════════════════════════════════════════════════════════════════════════
# BOTÕES DE COR
# ═════════════════════════════════════════════════════════════════════════════

class ColorButton(discord.ui.Button):
    def __init__(self, key: str, label: str, emoji_str: str, color_hex: int, row: int):
        super().__init__(
            label=BTN_PAD,  # espaços para botão maior, só o emoji fica visível
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
    """9 cores normais — layout 3+3+2."""
    def __init__(self):
        super().__init__(timeout=None)
        for i, (key, label, emoji_str, hex_c) in enumerate(CORES_NORMAIS):
            self.add_item(ColorButton(key, label, emoji_str, hex_c, row=i // 3))


class DegradeButton(discord.ui.Button):
    def __init__(self, key: str, label: str, emoji_str: str, row: int):
        super().__init__(
            label=BTN_PAD,
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
    """8 degradês — layout 3+3+2."""
    def __init__(self):
        super().__init__(timeout=None)
        for i, (key, label, emoji_str, _) in enumerate(CORES_DEGRADE):
            self.add_item(DegradeButton(key, label, emoji_str, row=i // 3))


# ═════════════════════════════════════════════════════════════════════════════
# COG
# ═════════════════════════════════════════════════════════════════════════════

class Cores(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot     = bot
        self.storage: Storage = bot.storage
        bot.add_view(ColorNormalView())
        bot.add_view(ColorDegradeView())

    def _cfg(self, guild_id: int, key: str, default=None):
        return self.storage.guild_get(guild_id, "cores_config", key) or default

    def _set(self, guild_id: int, key: str, value):
        self.storage.guild_set(guild_id, "cores_config", key, value)

    def _role_id(self, guild_id: int, key: str):
        v = self._cfg(guild_id, f"role_{key}")
        return int(v) if v else None

    def _all_color_role_ids(self, guild_id: int) -> set:
        ids = set()
        for key, *_ in CORES_NORMAIS + CORES_DEGRADE:
            rid = self._role_id(guild_id, key)
            if rid:
                ids.add(rid)
        return ids

    async def toggle_color_role(self, inter: discord.Interaction, key: str, degrade: bool):
        await inter.response.defer(ephemeral=True)
        guild  = inter.guild
        member = inter.user

        role_id = self._role_id(guild.id, key)
        if not role_id:
            return await inter.followup.send(
                embed=embed_error("Cor não configurada",
                    f"Esta cor não foi configurada ainda.\n{E['bulb']} Um admin deve usar `/cores setup`."),
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
            vip_ch_id = self._cfg(guild.id, "vip_channel")
            if vip_ch_id:
                vip_ch = guild.get_channel(int(vip_ch_id))
                if vip_ch and not vip_ch.permissions_for(member).read_messages:
                    return await inter.followup.send(
                        embed=embed_error(
                            "Acesso restrito",
                            f"{E['exclaim']} As cores degradê são exclusivas para membros com acesso a {vip_ch.mention}.\n\n"
                            f"{E['star']} Impulsione o servidor ou adquira um cargo VIP para ter acesso!"
                        ),
                        ephemeral=True,
                    )

        # Toggle
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

        # Remove outras cores do mesmo tipo antes de adicionar
        same_keys = [k for k, *_ in (CORES_DEGRADE if degrade else CORES_NORMAIS)]
        same_ids  = {self._role_id(guild.id, k) for k in same_keys if self._role_id(guild.id, k)}
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

    # ── Slash commands ────────────────────────────────────────────────────────

    cores_group = app_commands.Group(name="cores", description="Sistema de Nick Color")

    @cores_group.command(name="setup", description="Vincula um cargo do Discord a uma cor normal ou degradê")
    @app_commands.describe(cor="Cor a configurar", cargo="Cargo que representa esta cor")
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
                f"{E['dash']} Tipo: {'Degradê' if is_degrade else 'Normal'}"
            ),
            ephemeral=True,
        )

    @cores_group.command(name="setup_vip", description="Define o canal VIP — só quem tem acesso pode pegar cores degradê")
    @app_commands.describe(canal="Canal privado de boosters/VIPs")
    @app_commands.default_permissions(administrator=True)
    async def cores_setup_vip(self, inter: discord.Interaction, canal: discord.TextChannel):
        self._set(inter.guild.id, "vip_channel", str(canal.id))
        await inter.response.send_message(
            embed=embed_success(
                "Canal VIP definido",
                f"{E['star']} Apenas membros com acesso a {canal.mention} poderão pegar cores degradê."
            ),
            ephemeral=True,
        )

    @cores_group.command(name="painel", description="Envia o painel de cores normais (com opção de personalizar a embed)")
    @app_commands.describe(canal="Canal onde enviar (padrão: canal atual)")
    @app_commands.default_permissions(manage_guild=True)
    async def cores_painel(self, inter: discord.Interaction, canal: discord.TextChannel = None):
        ch = canal or inter.channel

        linhas = []
        for key, label, emoji_str, hex_c in CORES_NORMAIS:
            rid  = self._role_id(inter.guild.id, key)
            role = inter.guild.get_role(rid) if rid else None
            linhas.append(f"{emoji_str} **{label}** → {role.mention if role else '*não configurada*'}")

        default_title = "🎨 | Nick Color"
        default_desc  = (
            f"{E['star']} Cansou da cor do seu apelido? Deixe seu perfil mais colorido!\n\n"
            + "\n".join(linhas) +
            "\n\n**Como usar:**\n"
            "1. Clique no pincel da cor desejada\n"
            "2. Seu apelido receberá a nova cor\n"
            "3. Clique novamente para remover"
        )

        confirm = discord.Embed(
            title=f"{E['bulb']} Painel de Cores Normais",
            description=(
                f"Canal: {ch.mention}\n\n"
                f"{E['arrow_white']} **Enviar padrão** — envia a embed com as cores e instruções prontas\n"
                f"{E['pin']} **Personalizar embed** — edite título, descrição, cor, miniatura e banner antes de enviar"
            ),
            color=PHILO_COLOR,
        )
        view = PainelConfirmView(ch, ColorNormalView, default_title, default_desc, PHILO_COLOR)
        await inter.response.send_message(embed=confirm, view=view, ephemeral=True)

    @cores_group.command(name="painel_vip", description="Envia o painel de cores degradê (com opção de personalizar a embed)")
    @app_commands.describe(canal="Canal privado onde enviar")
    @app_commands.default_permissions(manage_guild=True)
    async def cores_painel_vip(self, inter: discord.Interaction, canal: discord.TextChannel = None):
        ch = canal or inter.channel

        linhas = []
        for key, label, emoji_str, _ in CORES_DEGRADE:
            rid  = self._role_id(inter.guild.id, key)
            role = inter.guild.get_role(rid) if rid else None
            linhas.append(f"{emoji_str} **{label}** → {role.mention if role else '*não configurada*'}")

        default_title = "✨ | Nick Color — Degradê Exclusivo"
        default_desc  = (
            f"{E['trophy']} Benefício exclusivo para membros especiais!\n\n"
            f"{E['fire_blue']} **Cores com gradiente disponíveis:**\n"
            + "\n".join(linhas) +
            f"\n\n{E['bulb']} Configure o gradiente em **Cargos → [cargo] → Cor → Gradiente**.\n\n"
            "**Como usar:**\n"
            "1. Clique no pincel da cor desejada\n"
            "2. Seu nome receberá o gradiente\n"
            "3. Clique novamente para remover"
        )

        confirm = discord.Embed(
            title=f"{E['trophy']} Painel de Cores Degradê",
            description=(
                f"Canal: {ch.mention}\n\n"
                f"{E['arrow_white']} **Enviar padrão** — envia a embed pronta\n"
                f"{E['pin']} **Personalizar embed** — edite título, descrição, cor, miniatura e banner antes de enviar"
            ),
            color=0x9B59B6,
        )
        view = PainelConfirmView(ch, ColorDegradeView, default_title, default_desc, 0x9B59B6)
        await inter.response.send_message(embed=confirm, view=view, ephemeral=True)

    @cores_group.command(name="lista", description="Lista todos os cargos de cor configurados")
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
