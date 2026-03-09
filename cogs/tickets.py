"""
cogs/tickets.py
Sistema de tickets completo:
 - Embed de painel totalmente configurável (título, descrição, cor, banner, footer, servidor)
 - Select menu com categorias configuráveis (até 6) usando emojis numéricos personalizados
 - Modal "Descreva seu ticket" ao selecionar categoria
 - Embed interna do ticket com categoria, motivo e avatar do usuário
 - Painel Admin: botões Atender · Painel Admin · Fechar · Notificar Atendente
 - Todos os outros recursos: add/remove user, rename, transcript, lista
"""

import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import io
import logging
from utils.helpers import embed_success, embed_error, embed_info, TICKET_COLOR, PHILO_COLOR
from utils.storage import Storage
from utils.emojis import E

log = logging.getLogger("sophosbot.tickets")

# ─── Categorias padrão ────────────────────────────────────────────────────────
DEFAULT_CATEGORIES = [
    {"key": "suporte",   "label": "Suporte Geral",    "desc": "Dúvidas gerais ou ajuda",          "emoji": E["n1"]},
    {"key": "denuncia",  "label": "Denúncias",         "desc": "Denunciar um membro ou situação",   "emoji": E["n2"]},
    {"key": "filosofia", "label": "Debate Filosófico", "desc": "Aprofundar um tema filosófico",     "emoji": E["n3"]},
    {"key": "teologia",  "label": "Debate Teológico",  "desc": "Questões de teologia e fé",         "emoji": E["n4"]},
    {"key": "parceria",  "label": "Parceria",          "desc": "Proposta de parceria ou patrocínio","emoji": E["n5"]},
    {"key": "outros",    "label": "Outros",             "desc": "Outros assuntos",                   "emoji": E["n6"]},
]

# ─── Ícones por categoria ─────────────────────────────────────────────────────
CATEGORY_ICON = {
    "suporte":   E["star"],
    "denuncia":  E["warning"],
    "filosofia": E["fire_blue"],
    "teologia":  E["verified"],
    "parceria":  E["trophy"],
    "outros":    E["arrow_white"],
}


# ════════════════════════════════════════════════════════════════════════════════
# MODALS
# ════════════════════════════════════════════════════════════════════════════════

class TicketDescriptionModal(discord.ui.Modal, title="Descreva seu ticket"):
    motivo = discord.ui.TextInput(
        label="Qual é o motivo do seu ticket?",
        style=discord.TextStyle.paragraph,
        placeholder="Explique brevemente o que você precisa...",
        max_length=500
    )

    def __init__(self, category_key: str, category_label: str):
        super().__init__()
        self.category_key   = category_key
        self.category_label = category_label

    async def on_submit(self, inter: discord.Interaction):
        cog = inter.client.cogs.get("Tickets")
        if cog:
            await cog.create_ticket(inter, self.category_key, self.category_label, self.motivo.value)


class AddUserModal(discord.ui.Modal, title="Adicionar usuário ao ticket"):
    user_id = discord.ui.TextInput(label="ID do usuário", placeholder="ID numérico do Discord", max_length=20)

    async def on_submit(self, inter: discord.Interaction):
        try:
            member = inter.guild.get_member(int(self.user_id.value))
            if not member:
                return await inter.response.send_message(
                    embed=embed_error("Não encontrado", "Usuário não está no servidor."), ephemeral=True)
            await inter.channel.set_permissions(member, read_messages=True, send_messages=True)
            await inter.response.send_message(
                embed=embed_success("Adicionado!", f"{member.mention} adicionado ao ticket."))
        except Exception as ex:
            await inter.response.send_message(embed=embed_error("Erro", str(ex)), ephemeral=True)


class EmbedBuilderModal(discord.ui.Modal, title="Configurar Painel de Tickets"):
    titulo    = discord.ui.TextInput(label="Título",      default="Precisa de ajuda?",  max_length=256)
    descricao = discord.ui.TextInput(
        label="Descrição", style=discord.TextStyle.paragraph, max_length=2048,
        default=(
            "Abra um ticket escolhendo a opção que mais se encaixa no seu caso.\n\n"
            "**Categorias disponíveis:**\n"
            "» Suporte Geral\n» Denúncias\n» Debate Filosófico\n» Debate Teológico\n» Parceria\n» Outros\n\n"
            "Selecione abaixo e aguarde nossa equipe!"
        )
    )
    cor    = discord.ui.TextInput(label="Cor hex (ex: #9B59B6)", default="#9B59B6", max_length=9, required=False)
    banner = discord.ui.TextInput(label="URL do banner (imagem)",  required=False, placeholder="https://...")
    footer = discord.ui.TextInput(label="Rodapé", required=False, default="SophosBot • Tickets")

    async def on_submit(self, inter: discord.Interaction):
        cog = inter.client.cogs.get("Tickets")
        if cog:
            await cog.send_ticket_embed(inter, self.titulo.value, self.descricao.value,
                                        self.cor.value, self.banner.value, self.footer.value)


class EditEmbedModal(discord.ui.Modal, title="Editar Painel de Tickets"):
    titulo    = discord.ui.TextInput(label="Título",      max_length=256)
    descricao = discord.ui.TextInput(label="Descrição",   style=discord.TextStyle.paragraph, max_length=2048)
    cor    = discord.ui.TextInput(label="Cor hex",        default="#9B59B6", max_length=9, required=False)
    banner = discord.ui.TextInput(label="URL do banner",  required=False)
    footer = discord.ui.TextInput(label="Rodapé",         required=False)

    def __init__(self, message: discord.Message):
        super().__init__()
        self.message = message
        if message.embeds:
            emb = message.embeds[0]
            self.titulo.default    = emb.title or ""
            self.descricao.default = emb.description or ""
            if emb.footer:
                self.footer.default = emb.footer.text or ""

    async def on_submit(self, inter: discord.Interaction):
        try:
            color = int(self.cor.value.lstrip("#"), 16) if self.cor.value else PHILO_COLOR
        except Exception:
            color = PHILO_COLOR
        emb = discord.Embed(title=self.titulo.value, description=self.descricao.value, color=color)
        if self.banner.value:
            emb.set_image(url=self.banner.value)
        if self.footer.value:
            emb.set_footer(text=self.footer.value)
        await self.message.edit(embed=emb)
        await inter.response.send_message(
            embed=embed_success("Painel atualizado!", "A embed foi editada com sucesso."), ephemeral=True)


# ════════════════════════════════════════════════════════════════════════════════
# SELECT MENU — Categorias
# ════════════════════════════════════════════════════════════════════════════════

class CategorySelect(discord.ui.Select):
    def __init__(self, categories: list):
        # Monta as opções usando os emojis numéricos personalizados
        # Os emojis personalizados no Select precisam ser PartialEmoji ou só o nome
        # Para emojis customizados em Select, passamos como emoji= no SelectOption
        options = []
        for cat in categories:
            # Extrai o ID do emoji customizado para usar no SelectOption
            # Formato: <:nome:id> ou <a:nome:id>
            emoji_str = cat["emoji"]
            options.append(discord.SelectOption(
                label=cat["label"],
                value=cat["key"],
                description=cat["desc"],
            ))
        super().__init__(
            placeholder="Selecione o motivo do seu ticket...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket:category_select"
        )
        self.categories = {c["key"]: c for c in categories}

    async def callback(self, inter: discord.Interaction):
        key = self.values[0]
        cat = self.categories.get(key, {})
        label = cat.get("label", key)
        await inter.response.send_modal(TicketDescriptionModal(key, label))


class TicketOpenView(discord.ui.View):
    def __init__(self, categories: list = None):
        super().__init__(timeout=None)
        cats = categories or DEFAULT_CATEGORIES
        self.add_item(CategorySelect(cats))


# ════════════════════════════════════════════════════════════════════════════════
# PAINEL ADMIN — View interna do ticket
# ════════════════════════════════════════════════════════════════════════════════

class TicketAdminPanelModal(discord.ui.Modal, title="Painel Admin — Ticket"):
    acao = discord.ui.TextInput(
        label="Ação / Nota para o ticket",
        style=discord.TextStyle.paragraph,
        placeholder="Registre uma ação, nota interna ou informação relevante...",
        max_length=500
    )

    async def on_submit(self, inter: discord.Interaction):
        emb = discord.Embed(
            title=f"{E['pin']} Nota Admin",
            description=self.acao.value,
            color=0x5865F2
        )
        emb.set_footer(text=f"Por {inter.user} • {discord.utils.utcnow().strftime('%d/%m/%Y %H:%M')}")
        await inter.channel.send(embed=emb)
        await inter.response.send_message(
            embed=embed_success("Nota registrada!", "A nota foi postada no ticket."), ephemeral=True)


class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # ── Atender ──────────────────────────────────────────────────────────────
    @discord.ui.button(
        label="Atender",
        style=discord.ButtonStyle.success,
        custom_id="ticket:atender",
        emoji=discord.PartialEmoji.from_str("<a:4455lightbluefire:1430338771236294767>")
    )
    async def atender(self, inter: discord.Interaction, button: discord.ui.Button):
        cog = inter.client.cogs.get("Tickets")
        if not cog:
            return
        owner_id = cog.storage.guild_get(inter.guild.id, "ticket_owner", str(inter.channel.id))
        if not owner_id:
            return await inter.response.send_message(
                embed=embed_error("Não é um ticket"), ephemeral=True)

        # Salva quem está atendendo
        cog.storage.guild_set(inter.guild.id, "ticket_attendant", str(inter.channel.id), str(inter.user.id))

        emb = discord.Embed(
            title=f"{E['verified']} Ticket em Atendimento",
            description=f"{inter.user.mention} está atendendo este ticket.",
            color=0x57F287
        )
        # Desabilita o botão atender após assumir
        button.disabled = True
        button.label    = f"Atendido por {inter.user.display_name}"
        await inter.message.edit(view=self)
        await inter.channel.send(embed=emb)
        await inter.response.send_message(
            embed=embed_success("Você assumiu o ticket!", "O usuário será notificado."), ephemeral=True)

    # ── Painel Admin ──────────────────────────────────────────────────────────
    @discord.ui.button(
        label="Painel Admin",
        style=discord.ButtonStyle.primary,
        custom_id="ticket:admin_panel",
        emoji=discord.PartialEmoji.from_str("<:w_p:1445474432893063299>")
    )
    async def admin_panel(self, inter: discord.Interaction, button: discord.ui.Button):
        cog = inter.client.cogs.get("Tickets")
        if not cog:
            return
        support_role_id = cog._cfg(inter.guild.id, "support_role")
        is_staff = inter.user.guild_permissions.manage_channels
        if support_role_id:
            role = inter.guild.get_role(int(support_role_id))
            if role and role in inter.user.roles:
                is_staff = True
        if not is_staff:
            return await inter.response.send_message(
                embed=embed_error("Sem permissão", "Apenas a staff pode usar o Painel Admin."), ephemeral=True)
        await inter.response.send_modal(TicketAdminPanelModal())

    # ── Fechar ────────────────────────────────────────────────────────────────
    @discord.ui.button(
        label="Fechar",
        style=discord.ButtonStyle.danger,
        custom_id="ticket:close",
        emoji=discord.PartialEmoji.from_str("<a:i_exclamation:1446591025622679644>")
    )
    async def close_ticket(self, inter: discord.Interaction, button: discord.ui.Button):
        cog = inter.client.cogs.get("Tickets")
        if cog:
            await cog.close_ticket(inter)

    # ── Notificar Atendente ───────────────────────────────────────────────────
    @discord.ui.button(
        label="Notificar Atendente",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket:notify",
        emoji=discord.PartialEmoji.from_str("<a:w_001:1445474007712403669>")
    )
    async def notify_attendant(self, inter: discord.Interaction, button: discord.ui.Button):
        cog = inter.client.cogs.get("Tickets")
        if not cog:
            return
        attendant_id = cog.storage.guild_get(inter.guild.id, "ticket_attendant", str(inter.channel.id))
        owner_id     = cog.storage.guild_get(inter.guild.id, "ticket_owner",     str(inter.channel.id))

        # Só o dono do ticket pode notificar
        if str(inter.user.id) != owner_id:
            return await inter.response.send_message(
                embed=embed_error("Sem permissão", "Apenas o dono do ticket pode notificar o atendente."),
                ephemeral=True)

        if attendant_id:
            attendant = inter.guild.get_member(int(attendant_id))
            if attendant:
                await inter.channel.send(f"{E['loading']} {attendant.mention}, o usuário está aguardando atendimento!")
                return await inter.response.send_message(
                    embed=embed_success("Notificado!", f"{attendant.mention} foi mencionado."), ephemeral=True)

        # Se não há atendente, menciona o cargo de suporte
        support_role_id = cog._cfg(inter.guild.id, "support_role")
        if support_role_id:
            role = inter.guild.get_role(int(support_role_id))
            if role:
                await inter.channel.send(f"{E['loading']} {role.mention}, o usuário está aguardando atendimento!")
                return await inter.response.send_message(
                    embed=embed_success("Equipe notificada!", f"{role.mention} foi mencionado."), ephemeral=True)

        await inter.response.send_message(
            embed=embed_error("Nenhum atendente", "Nenhum atendente assumiu este ticket ainda."), ephemeral=True)


# ════════════════════════════════════════════════════════════════════════════════
# COG PRINCIPAL
# ════════════════════════════════════════════════════════════════════════════════

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot     = bot
        self.storage: Storage = bot.storage
        # Registrar views persistentes com categorias padrão
        bot.add_view(TicketOpenView(DEFAULT_CATEGORIES))
        bot.add_view(TicketControlView())

    def _cfg(self, guild_id, key, default=None):
        return self.storage.guild_get(guild_id, "tickets_config", key) or default

    def _set(self, guild_id, key, value):
        self.storage.guild_set(guild_id, "tickets_config", key, value)

    def _get_categories(self, guild_id) -> list:
        custom = self._cfg(guild_id, "categories")
        return custom if custom else DEFAULT_CATEGORIES

    # ── Criar ticket ──────────────────────────────────────────────────────────
    async def create_ticket(self, inter: discord.Interaction,
                             category_key: str, category_label: str, motivo: str):
        await inter.response.defer(ephemeral=True)
        guild = inter.guild

        category_id = self._cfg(guild.id, "category")
        if not category_id:
            return await inter.followup.send(
                embed=embed_error("Não configurado", "Use `/ticket setup` primeiro."), ephemeral=True)

        # Verificar ticket já aberto
        open_ch = self.storage.guild_get(guild.id, "tickets_open", str(inter.user.id))
        if open_ch:
            ch = guild.get_channel(open_ch)
            if ch:
                return await inter.followup.send(
                    embed=embed_error("Ticket já aberto", f"Você já tem um ticket aberto: {ch.mention}"),
                    ephemeral=True)

        category        = guild.get_channel(int(category_id))
        support_role_id = self._cfg(guild.id, "support_role")
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            inter.user:         discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me:           discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
        }
        if support_role_id:
            role = guild.get_role(int(support_role_id))
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        num = (self._cfg(guild.id, "ticket_count") or 0) + 1
        self._set(guild.id, "ticket_count", num)

        channel_name = f"ticket-{num:04d}-{inter.user.name[:15]}"
        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"[{category_label}] Ticket de {inter.user} (ID: {inter.user.id})"
        )

        self.storage.guild_set(guild.id, "tickets_open",     str(inter.user.id), channel.id)
        self.storage.guild_set(guild.id, "ticket_owner",     str(channel.id),    str(inter.user.id))
        self.storage.guild_set(guild.id, "ticket_category",  str(channel.id),    category_label)
        self.storage.guild_set(guild.id, "ticket_motivo",    str(channel.id),    motivo)

        # ── Embed interna do ticket ──────────────────────────────────────────
        icon = CATEGORY_ICON.get(category_key, E["arrow_white"])
        server_name = guild.name

        emb = discord.Embed(
            title=f"{icon} {category_label}",
            color=PHILO_COLOR
        )
        emb.add_field(name=f"{E['pin']} Aberto por",     value=inter.user.mention,  inline=True)
        emb.add_field(name=f"{E['rules']} Categoria",    value=category_label,      inline=True)
        emb.add_field(name=f"{E['fire_blue']} Motivo",   value=motivo,              inline=False)
        emb.add_field(
            name=f"{E['arrow_blue']}",
            value=f"Olá, {inter.user.mention}! Me diga mais detalhes enquanto aguarda a equipe responsável.\n\n{E['loading']} Nossa equipe irá te atender em breve",
            inline=False
        )
        emb.set_thumbnail(url=inter.user.display_avatar.url)
        emb.set_footer(text=f"{server_name} • ID do usuário: {inter.user.id} | Hoje às {discord.utils.utcnow().strftime('%H:%M')}")

        # Menção ao cargo de suporte
        mention_text = ""
        if support_role_id:
            mention_text = f"<@&{support_role_id}>"

        await channel.send(content=f"{inter.user.mention}{' · ' + mention_text if mention_text else ''}",
                           embed=emb, view=TicketControlView())

        # ── Log ──────────────────────────────────────────────────────────────
        log_id = self._cfg(guild.id, "log_channel")
        if log_id:
            lch = guild.get_channel(int(log_id))
            if lch:
                le = discord.Embed(
                    title=f"{E['mail']} Ticket Criado — #{num:04d}",
                    color=0x57F287
                )
                le.add_field(name=f"{E['arrow_white']} Usuário",   value=f"{inter.user.mention} (`{inter.user.id}`)", inline=True)
                le.add_field(name=f"{E['rules']} Categoria",       value=category_label, inline=True)
                le.add_field(name="Canal",                         value=channel.mention, inline=True)
                le.set_footer(text=discord.utils.utcnow().strftime('%d/%m/%Y %H:%M'))
                await lch.send(embed=le)

        await inter.followup.send(
            embed=embed_success("Ticket criado!", f"Seu ticket foi aberto em {channel.mention}"),
            ephemeral=True)

    # ── Fechar ticket ─────────────────────────────────────────────────────────
    async def close_ticket(self, inter: discord.Interaction):
        owner_id = self.storage.guild_get(inter.guild.id, "ticket_owner", str(inter.channel.id))
        if not owner_id:
            return await inter.response.send_message(
                embed=embed_error("Não é um ticket", "Este canal não é um ticket."), ephemeral=True)

        support_role_id = self._cfg(inter.guild.id, "support_role")
        is_support = inter.user.guild_permissions.manage_channels
        if support_role_id:
            role = inter.guild.get_role(int(support_role_id))
            if role and role in inter.user.roles:
                is_support = True

        if str(inter.user.id) != owner_id and not is_support:
            return await inter.response.send_message(
                embed=embed_error("Sem permissão", "Apenas o dono do ticket ou a staff pode fechar."),
                ephemeral=True)

        await inter.response.send_message(
            embed=embed_info("Fechando ticket...", "O canal será deletado em 5 segundos."))

        # Log de fechamento
        log_id = self._cfg(inter.guild.id, "log_channel")
        if log_id:
            lch = inter.guild.get_channel(int(log_id))
            if lch:
                category_label = self.storage.guild_get(inter.guild.id, "ticket_category", str(inter.channel.id)) or "—"
                le = discord.Embed(
                    title=f"{E['deafened']} Ticket Fechado",
                    color=0xED4245
                )
                le.add_field(name="Canal",                    value=f"#{inter.channel.name}", inline=True)
                le.add_field(name=f"{E['rules']} Categoria",  value=category_label, inline=True)
                le.add_field(name=f"{E['pin']} Fechado por",  value=inter.user.mention, inline=True)
                le.set_footer(text=discord.utils.utcnow().strftime('%d/%m/%Y %H:%M'))
                await lch.send(embed=le)

        # Limpar dados
        self.storage.delete("tickets_open",     owner_id)
        self.storage.guild_set(inter.guild.id, "ticket_owner",     str(inter.channel.id), None)
        self.storage.guild_set(inter.guild.id, "ticket_attendant", str(inter.channel.id), None)

        await asyncio.sleep(5)
        try:
            await inter.channel.delete(reason=f"Ticket fechado por {inter.user}")
        except Exception:
            pass

    # ── Transcrição ───────────────────────────────────────────────────────────
    async def send_transcript(self, inter: discord.Interaction):
        await inter.response.defer(ephemeral=True)
        messages = []
        async for msg in inter.channel.history(limit=300, oldest_first=True):
            if not msg.author.bot:
                messages.append(f"[{msg.created_at.strftime('%d/%m/%Y %H:%M')}] {msg.author}: {msg.content}")
        content = "\n".join(messages) or "Nenhuma mensagem de usuário encontrada."
        file = discord.File(fp=io.BytesIO(content.encode()), filename=f"transcript-{inter.channel.name}.txt")
        try:
            owner_id = self.storage.guild_get(inter.guild.id, "ticket_owner", str(inter.channel.id))
            if owner_id:
                owner = inter.guild.get_member(int(owner_id))
                if owner:
                    await owner.send(f"{E['rules']} Transcrição do ticket `{inter.channel.name}`:", file=file)
        except Exception:
            pass
        await inter.followup.send(
            embed=embed_success("Transcrição enviada!", "Arquivo enviado ao dono do ticket via DM."),
            ephemeral=True)

    # ── Enviar painel ─────────────────────────────────────────────────────────
    async def send_ticket_embed(self, inter, titulo, descricao, cor, banner, footer):
        try:
            color = int(cor.lstrip("#"), 16) if cor else PHILO_COLOR
        except Exception:
            color = PHILO_COLOR

        emb = discord.Embed(title=titulo, description=descricao, color=color)
        if banner:
            emb.set_image(url=banner)
        if footer:
            emb.set_footer(text=footer)

        ch_id = self._cfg(inter.guild.id, "panel_channel")
        ch    = inter.guild.get_channel(int(ch_id)) if ch_id else inter.channel
        cats  = self._get_categories(inter.guild.id)
        msg   = await ch.send(embed=emb, view=TicketOpenView(cats))

        self._set(inter.guild.id, "panel_message_id",  str(msg.id))
        self._set(inter.guild.id, "panel_channel_id",  str(ch.id))

        await inter.response.send_message(
            embed=embed_success("Painel criado!", f"Embed enviada em {ch.mention}."), ephemeral=True)

    # ════════════════════════════════════════════════════════════════════════════
    # SLASH COMMANDS
    # ════════════════════════════════════════════════════════════════════════════
    ticket_group = app_commands.Group(name="ticket", description="Sistema de tickets")

    @ticket_group.command(name="setup", description="Configura o sistema de tickets")
    @app_commands.describe(
        categoria="Categoria onde os tickets serão criados",
        cargo_suporte="Cargo da equipe de suporte",
        canal_log="Canal de logs dos tickets",
        canal_painel="Canal onde o painel será enviado"
    )
    @app_commands.default_permissions(administrator=True)
    async def ticket_setup(self, inter: discord.Interaction,
                           categoria: discord.CategoryChannel,
                           cargo_suporte: discord.Role,
                           canal_log: discord.TextChannel,
                           canal_painel: discord.TextChannel):
        self._set(inter.guild.id, "category",      str(categoria.id))
        self._set(inter.guild.id, "support_role",  str(cargo_suporte.id))
        self._set(inter.guild.id, "log_channel",   str(canal_log.id))
        self._set(inter.guild.id, "panel_channel", str(canal_painel.id))
        await inter.response.send_message(embed=embed_success("Sistema configurado!",
            f"{E['arrow_white']} **Categoria:** {categoria.mention}\n"
            f"{E['pin']} **Suporte:** {cargo_suporte.mention}\n"
            f"{E['rules']} **Log:** {canal_log.mention}\n"
            f"{E['mail']} **Painel:** {canal_painel.mention}"
        ), ephemeral=True)

    @ticket_group.command(name="painel", description="Cria/edita o painel de abertura de tickets")
    @app_commands.default_permissions(administrator=True)
    async def ticket_painel(self, inter: discord.Interaction):
        await inter.response.send_modal(EmbedBuilderModal())

    @ticket_group.command(name="editpainel", description="Edita o painel de tickets já publicado")
    @app_commands.describe(message_id="ID da mensagem (deixe vazio para o painel salvo)")
    @app_commands.default_permissions(administrator=True)
    async def ticket_edit(self, inter: discord.Interaction, message_id: str = None):
        try:
            if message_id:
                msg = await inter.channel.fetch_message(int(message_id))
            else:
                saved   = self._cfg(inter.guild.id, "panel_message_id")
                ch_id   = self._cfg(inter.guild.id, "panel_channel_id")
                if not saved:
                    return await inter.response.send_message(
                        embed=embed_error("Não encontrado", "Use `/ticket painel` primeiro."), ephemeral=True)
                ch  = inter.guild.get_channel(int(ch_id)) if ch_id else inter.channel
                msg = await ch.fetch_message(int(saved))
            await inter.response.send_modal(EditEmbedModal(msg))
        except Exception as ex:
            await inter.response.send_message(embed=embed_error("Erro", str(ex)), ephemeral=True)

    @ticket_group.command(name="fechar", description="Fecha o ticket atual")
    async def ticket_fechar(self, inter: discord.Interaction):
        await self.close_ticket(inter)

    @ticket_group.command(name="transcript", description="Gera a transcrição do ticket atual")
    @app_commands.default_permissions(manage_channels=True)
    async def ticket_transcript(self, inter: discord.Interaction):
        await self.send_transcript(inter)

    @ticket_group.command(name="add", description="Adiciona um usuário ao ticket atual")
    @app_commands.describe(membro="Membro a adicionar")
    @app_commands.default_permissions(manage_channels=True)
    async def ticket_add(self, inter: discord.Interaction, membro: discord.Member):
        await inter.channel.set_permissions(membro, read_messages=True, send_messages=True)
        await inter.response.send_message(embed=embed_success("Adicionado!", f"{membro.mention} adicionado ao ticket."))

    @ticket_group.command(name="remove", description="Remove um usuário do ticket atual")
    @app_commands.describe(membro="Membro a remover")
    @app_commands.default_permissions(manage_channels=True)
    async def ticket_remove(self, inter: discord.Interaction, membro: discord.Member):
        await inter.channel.set_permissions(membro, overwrite=None)
        await inter.response.send_message(embed=embed_success("Removido!", f"{membro.mention} removido do ticket."))

    @ticket_group.command(name="renomear", description="Renomeia o canal do ticket atual")
    @app_commands.describe(nome="Novo nome do canal")
    @app_commands.default_permissions(manage_channels=True)
    async def ticket_rename(self, inter: discord.Interaction, nome: str):
        await inter.channel.edit(name=nome)
        await inter.response.send_message(
            embed=embed_success("Renomeado!", f"Canal renomeado para `{nome}`."), ephemeral=True)

    @ticket_group.command(name="lista", description="Lista todos os tickets abertos")
    @app_commands.default_permissions(manage_channels=True)
    async def ticket_lista(self, inter: discord.Interaction):
        await inter.response.defer(ephemeral=True)
        store = self.storage.load("tickets_open")
        guild_tickets = {uid: chid for uid, chid in store.items() if inter.guild.get_channel(chid)}
        if not guild_tickets:
            return await inter.followup.send(
                embed=embed_info("Sem tickets", "Não há tickets ativos no momento."), ephemeral=True)
        emb = discord.Embed(title=f"{E['mail']} Tickets Abertos", color=TICKET_COLOR)
        for uid, chid in guild_tickets.items():
            ch     = inter.guild.get_channel(chid)
            member = inter.guild.get_member(int(uid))
            if ch and member:
                cat = self.storage.guild_get(inter.guild.id, "ticket_category", str(chid)) or "—"
                emb.add_field(
                    name=f"{E['arrow_white']} #{ch.name}",
                    value=f"{member.mention} · {cat}",
                    inline=True
                )
        await inter.followup.send(embed=emb, ephemeral=True)

    @ticket_group.command(name="categoria_add", description="Adiciona uma categoria personalizada ao painel")
    @app_commands.describe(
        chave="Identificador único (sem espaços, ex: vip)",
        nome="Nome exibido no menu",
        descricao="Descrição curta"
    )
    @app_commands.default_permissions(administrator=True)
    async def ticket_cat_add(self, inter: discord.Interaction, chave: str, nome: str, descricao: str):
        cats = self._cfg(inter.guild.id, "categories") or list(DEFAULT_CATEGORIES)
        if len(cats) >= 6:
            return await inter.response.send_message(
                embed=embed_error("Limite atingido", "O Discord permite no máximo 6 opções no select menu."),
                ephemeral=True)
        # Emoji numérico baseado na posição
        num_emojis = [E["n1"], E["n2"], E["n3"], E["n4"], E["n5"], E["n6"]]
        emoji = num_emojis[len(cats)] if len(cats) < len(num_emojis) else E["arrow_white"]
        cats.append({"key": chave, "label": nome, "desc": descricao, "emoji": emoji})
        self._set(inter.guild.id, "categories", cats)
        await inter.response.send_message(
            embed=embed_success("Categoria adicionada!", f"**{nome}** adicionada. Use `/ticket painel` para atualizar o painel."),
            ephemeral=True)

    @ticket_group.command(name="categoria_reset", description="Restaura as categorias padrão")
    @app_commands.default_permissions(administrator=True)
    async def ticket_cat_reset(self, inter: discord.Interaction):
        self._set(inter.guild.id, "categories", None)
        await inter.response.send_message(
            embed=embed_success("Categorias restauradas!", "As categorias voltaram ao padrão. Use `/ticket painel` para atualizar."),
            ephemeral=True)


async def setup(bot):
    await bot.add_cog(Tickets(bot))
