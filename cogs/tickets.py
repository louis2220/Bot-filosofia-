import discord
from discord import app_commands
from discord.ext import commands
import logging
from utils.helpers import embed_success, embed_error, embed_info, TICKET_COLOR
from utils.storage import Storage
from utils.emojis import E

log = logging.getLogger("sophosbot.tickets")


# ─── Views persistentes ───────────────────────────────────────────────────────

class TicketOpenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Abrir Ticket",
        style=discord.ButtonStyle.primary,
        custom_id="ticket:open",
        emoji=discord.PartialEmoji.from_str("<:1000006244:1475982552488607815>")
    )
    async def open_ticket(self, inter: discord.Interaction, button: discord.ui.Button):
        cog = inter.client.cogs.get("Tickets")
        if cog:
            await cog.create_ticket(inter)


class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Fechar",
        style=discord.ButtonStyle.danger,
        custom_id="ticket:close",
        emoji=discord.PartialEmoji.from_str("<:9848blurplemuted:1430269262332690565>")
    )
    async def close_ticket(self, inter: discord.Interaction, button: discord.ui.Button):
        cog = inter.client.cogs.get("Tickets")
        if cog:
            await cog.close_ticket(inter)

    @discord.ui.button(
        label="Adicionar",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket:add_user",
        emoji=discord.PartialEmoji.from_str("<a:51047animatedarrowwhite:1430338988765347850>")
    )
    async def add_user_btn(self, inter: discord.Interaction, button: discord.ui.Button):
        await inter.response.send_modal(AddUserModal())

    @discord.ui.button(
        label="Transcrição",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket:transcript",
        emoji=discord.PartialEmoji.from_str("<:regras:1444711583669551358>")
    )
    async def transcript_btn(self, inter: discord.Interaction, button: discord.ui.Button):
        cog = inter.client.cogs.get("Tickets")
        if cog:
            await cog.send_transcript(inter)


class AddUserModal(discord.ui.Modal, title="Adicionar usuário ao ticket"):
    user_id = discord.ui.TextInput(label="ID do usuário", placeholder="ID numérico do Discord", max_length=20)

    async def on_submit(self, inter: discord.Interaction):
        try:
            member = inter.guild.get_member(int(self.user_id.value))
            if not member:
                return await inter.response.send_message(embed=embed_error("Não encontrado", "Usuário não está no servidor."), ephemeral=True)
            await inter.channel.set_permissions(member, read_messages=True, send_messages=True)
            await inter.response.send_message(embed=embed_success("Adicionado!", f"{member.mention} adicionado ao ticket."))
        except Exception as ex:
            await inter.response.send_message(embed=embed_error("Erro", str(ex)), ephemeral=True)


class EmbedBuilderModal(discord.ui.Modal, title="Construtor de Embed — Tickets"):
    titulo    = discord.ui.TextInput(label="Título", default="Suporte — Abra um Ticket", max_length=256)
    descricao = discord.ui.TextInput(label="Descrição", style=discord.TextStyle.paragraph,
        default="Clique no botão abaixo para abrir um ticket com nossa equipe.\n\n> Descreva sua situação com detalhes.", max_length=2048)
    cor       = discord.ui.TextInput(label="Cor hex (ex: #5865F2)", default="#5865F2", max_length=9, required=False)
    banner    = discord.ui.TextInput(label="URL do banner", required=False, placeholder="https://...")
    footer    = discord.ui.TextInput(label="Rodapé", required=False, default="SophosBot • Tickets")

    async def on_submit(self, inter: discord.Interaction):
        cog = inter.client.cogs.get("Tickets")
        if cog:
            await cog.send_ticket_embed(inter, self.titulo.value, self.descricao.value,
                                        self.cor.value, self.banner.value, self.footer.value)


class EditEmbedModal(discord.ui.Modal, title="Editar Embed de Tickets"):
    titulo    = discord.ui.TextInput(label="Novo título", max_length=256)
    descricao = discord.ui.TextInput(label="Nova descrição", style=discord.TextStyle.paragraph, max_length=2048)
    cor       = discord.ui.TextInput(label="Nova cor hex", default="#5865F2", max_length=9, required=False)
    banner    = discord.ui.TextInput(label="Nova URL do banner", required=False)
    footer    = discord.ui.TextInput(label="Novo rodapé", required=False)

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
            color = int(self.cor.value.lstrip("#"), 16) if self.cor.value else 0x5865F2
        except Exception:
            color = 0x5865F2
        emb = discord.Embed(title=self.titulo.value, description=self.descricao.value, color=color)
        if self.banner.value:
            emb.set_image(url=self.banner.value)
        if self.footer.value:
            emb.set_footer(text=self.footer.value)
        await self.message.edit(embed=emb)
        await inter.response.send_message(embed=embed_success("Embed atualizada!", "Mensagem editada com sucesso."), ephemeral=True)


# ─── Cog ─────────────────────────────────────────────────────────────────────

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.storage: Storage = bot.storage
        bot.add_view(TicketOpenView())
        bot.add_view(TicketControlView())

    def _cfg(self, guild_id, key, default=None):
        return self.storage.guild_get(guild_id, "tickets_config", key) or default

    def _set(self, guild_id, key, value):
        self.storage.guild_set(guild_id, "tickets_config", key, value)

    async def create_ticket(self, inter: discord.Interaction):
        guild = inter.guild
        category_id = self._cfg(guild.id, "category")
        if not category_id:
            return await inter.response.send_message(embed=embed_error("Não configurado", "Use `/ticket setup` primeiro."), ephemeral=True)

        open_ch = self.storage.guild_get(guild.id, "tickets_open", str(inter.user.id))
        if open_ch:
            ch = guild.get_channel(open_ch)
            if ch:
                return await inter.response.send_message(embed=embed_error("Ticket já aberto", f"Você já tem um ticket: {ch.mention}"), ephemeral=True)

        category      = guild.get_channel(int(category_id))
        support_role_id = self._cfg(guild.id, "support_role")
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            inter.user:         discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me:           discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
        }
        if support_role_id:
            role = guild.get_role(int(support_role_id))
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        num = (self._cfg(guild.id, "ticket_count") or 0) + 1
        self._set(guild.id, "ticket_count", num)

        channel = await guild.create_text_channel(
            name=f"ticket-{num:04d}-{inter.user.name}",
            category=category,
            overwrites=overwrites,
            topic=f"Ticket de {inter.user} (ID: {inter.user.id})"
        )
        self.storage.guild_set(guild.id, "tickets_open",  str(inter.user.id), channel.id)
        self.storage.guild_set(guild.id, "ticket_owner",  str(channel.id), str(inter.user.id))

        emb = discord.Embed(
            title=f"{E['mail']} Ticket Aberto",
            description=(
                f"Olá {inter.user.mention}! {E['star']} Bem-vindo ao seu ticket.\n\n"
                f"{E['arrow_white']} Descreva sua situação com detalhes e nossa equipe responderá em breve.\n\n"
                f"*«A clareza é a cortesia do filósofo.» — Ortega y Gasset*"
            ),
            color=TICKET_COLOR
        )
        emb.set_footer(text=f"Ticket #{num:04d} • {inter.user}")
        await channel.send(embed=emb, view=TicketControlView())

        log_id = self._cfg(guild.id, "log_channel")
        if log_id:
            lch = guild.get_channel(int(log_id))
            if lch:
                le = discord.Embed(title=f"{E['mail']} Ticket Criado", description=f"Canal: {channel.mention}\nUsuário: {inter.user.mention}", color=0x57F287)
                await lch.send(embed=le)

        await inter.response.send_message(embed=embed_success("Ticket criado!", f"Seu ticket: {channel.mention}"), ephemeral=True)

    async def close_ticket(self, inter: discord.Interaction):
        owner_id = self.storage.guild_get(inter.guild.id, "ticket_owner", str(inter.channel.id))
        if not owner_id:
            return await inter.response.send_message(embed=embed_error("Não é um ticket", "Este canal não é um ticket."), ephemeral=True)

        support_role_id = self._cfg(inter.guild.id, "support_role")
        is_support = False
        if support_role_id:
            role = inter.guild.get_role(int(support_role_id))
            if role and role in inter.user.roles:
                is_support = True

        if str(inter.user.id) != owner_id and not is_support and not inter.user.guild_permissions.manage_channels:
            return await inter.response.send_message(embed=embed_error("Sem permissão", "Apenas o dono ou suporte pode fechar."), ephemeral=True)

        await inter.response.send_message(embed=embed_info("Fechando...", "Canal será deletado em 5 segundos."))

        log_id = self._cfg(inter.guild.id, "log_channel")
        if log_id:
            lch = inter.guild.get_channel(int(log_id))
            if lch:
                le = discord.Embed(title=f"{E['deafened']} Ticket Fechado", description=f"Canal: #{inter.channel.name}\nFechado por: {inter.user.mention}", color=0xED4245)
                await lch.send(embed=le)

        self.storage.delete("tickets_open", owner_id)
        import asyncio
        await asyncio.sleep(5)
        await inter.channel.delete(reason=f"Ticket fechado por {inter.user}")

    async def send_transcript(self, inter: discord.Interaction):
        await inter.response.defer(ephemeral=True)
        messages = []
        async for msg in inter.channel.history(limit=200, oldest_first=True):
            if not msg.author.bot:
                messages.append(f"[{msg.created_at.strftime('%d/%m/%Y %H:%M')}] {msg.author}: {msg.content}")
        content = "\n".join(messages) or "Nenhuma mensagem encontrada."
        file = discord.File(fp=__import__("io").BytesIO(content.encode()), filename=f"transcript-{inter.channel.name}.txt")
        try:
            owner_id = self.storage.guild_get(inter.guild.id, "ticket_owner", str(inter.channel.id))
            if owner_id:
                owner = inter.guild.get_member(int(owner_id))
                if owner:
                    await owner.send(f"{E['rules']} Transcrição do ticket `{inter.channel.name}`:", file=file)
        except Exception:
            pass
        await inter.followup.send(embed=embed_success("Transcrição enviada!", "Enviada ao dono do ticket via DM."), ephemeral=True)

    async def send_ticket_embed(self, inter, titulo, descricao, cor, banner, footer):
        try:
            color = int(cor.lstrip("#"), 16) if cor else 0x5865F2
        except Exception:
            color = 0x5865F2
        emb = discord.Embed(title=titulo, description=descricao, color=color)
        if banner:
            emb.set_image(url=banner)
        if footer:
            emb.set_footer(text=footer)
        ch_id = self._cfg(inter.guild.id, "panel_channel")
        ch = inter.guild.get_channel(int(ch_id)) if ch_id else inter.channel
        msg = await ch.send(embed=emb, view=TicketOpenView())
        self._set(inter.guild.id, "panel_message_id", str(msg.id))
        self._set(inter.guild.id, "panel_channel_id", str(ch.id))
        await inter.response.send_message(embed=embed_success("Painel criado!", f"Embed enviada em {ch.mention}."), ephemeral=True)

    # ─── Slash Commands ───────────────────────────────────────────────────────
    ticket_group = app_commands.Group(name="ticket", description="Sistema de tickets")

    @ticket_group.command(name="setup", description="Configura o sistema de tickets")
    @app_commands.describe(categoria="Categoria dos tickets", cargo_suporte="Cargo de suporte", canal_log="Canal de logs", canal_painel="Canal do painel")
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
            f"{E['mail']} **Painel:** {canal_painel.mention}"), ephemeral=True)

    @ticket_group.command(name="painel", description="Cria o painel de tickets com embed personalizável")
    @app_commands.default_permissions(administrator=True)
    async def ticket_painel(self, inter: discord.Interaction):
        await inter.response.send_modal(EmbedBuilderModal())

    @ticket_group.command(name="editpainel", description="Edita uma embed de ticket já publicada")
    @app_commands.describe(message_id="ID da mensagem (deixe vazio para o painel salvo)")
    @app_commands.default_permissions(administrator=True)
    async def ticket_edit(self, inter: discord.Interaction, message_id: str = None):
        try:
            if message_id:
                msg = await inter.channel.fetch_message(int(message_id))
            else:
                saved    = self._cfg(inter.guild.id, "panel_message_id")
                ch_saved = self._cfg(inter.guild.id, "panel_channel_id")
                if not saved:
                    return await inter.response.send_message(embed=embed_error("Não encontrado", "Nenhum painel salvo. Use `/ticket painel` primeiro."), ephemeral=True)
                ch  = inter.guild.get_channel(int(ch_saved)) if ch_saved else inter.channel
                msg = await ch.fetch_message(int(saved))
            await inter.response.send_modal(EditEmbedModal(msg))
        except Exception as ex:
            await inter.response.send_message(embed=embed_error("Erro", str(ex)), ephemeral=True)

    @ticket_group.command(name="fechar", description="Fecha o ticket atual")
    async def ticket_fechar(self, inter: discord.Interaction):
        await self.close_ticket(inter)

    @ticket_group.command(name="add", description="Adiciona um usuário ao ticket atual")
    @app_commands.describe(membro="Membro")
    @app_commands.default_permissions(manage_channels=True)
    async def ticket_add(self, inter: discord.Interaction, membro: discord.Member):
        await inter.channel.set_permissions(membro, read_messages=True, send_messages=True)
        await inter.response.send_message(embed=embed_success("Adicionado!", f"{membro.mention} adicionado ao ticket."))

    @ticket_group.command(name="remove", description="Remove um usuário do ticket atual")
    @app_commands.describe(membro="Membro")
    @app_commands.default_permissions(manage_channels=True)
    async def ticket_remove(self, inter: discord.Interaction, membro: discord.Member):
        await inter.channel.set_permissions(membro, overwrite=None)
        await inter.response.send_message(embed=embed_success("Removido!", f"{membro.mention} removido do ticket."))

    @ticket_group.command(name="renomear", description="Renomeia o canal do ticket atual")
    @app_commands.describe(nome="Novo nome")
    @app_commands.default_permissions(manage_channels=True)
    async def ticket_rename(self, inter: discord.Interaction, nome: str):
        await inter.channel.edit(name=nome)
        await inter.response.send_message(embed=embed_success("Renomeado!", f"Canal renomeado para `{nome}`."), ephemeral=True)

    @ticket_group.command(name="lista", description="Lista todos os tickets abertos")
    @app_commands.default_permissions(manage_channels=True)
    async def ticket_lista(self, inter: discord.Interaction):
        await inter.response.defer(ephemeral=True)
        store = self.storage.load("tickets_open")
        guild_tickets = {uid: chid for uid, chid in store.items() if inter.guild.get_channel(chid)}
        if not guild_tickets:
            return await inter.followup.send(embed=embed_info("Sem tickets", "Não há tickets ativos."), ephemeral=True)
        emb = discord.Embed(title=f"{E['mail']} Tickets Abertos", color=TICKET_COLOR)
        for uid, chid in guild_tickets.items():
            ch     = inter.guild.get_channel(chid)
            member = inter.guild.get_member(int(uid))
            if ch and member:
                emb.add_field(name=f"{E['arrow_white']} #{ch.name}", value=member.mention, inline=True)
        await inter.followup.send(embed=emb, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Tickets(bot))
