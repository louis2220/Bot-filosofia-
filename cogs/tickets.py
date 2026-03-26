"""
cogs/tickets.py
Sistema de tickets completo com PostgreSQL.
Sem emojis. Estilo formal adequado a um servidor academico de filosofia.
"""

import asyncio
import io
import logging
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Modal, TextInput, Select

from utils.helpers import embed_success, embed_error, embed_info, TICKET_COLOR, PHILO_COLOR
from utils.db import Database

log = logging.getLogger("filosofia.tickets")

MAIN_COLOR = 0x8E44AD

TICKET_CATEGORIES = [
    discord.SelectOption(label="Suporte Geral",      value="suporte",    description="Duvidas gerais ou ajuda"),
    discord.SelectOption(label="Denuncia",            value="denuncia",   description="Denunciar um membro ou situacao"),
    discord.SelectOption(label="Debate Filosofico",   value="filosofia",  description="Aprofundar um tema filosofico"),
    discord.SelectOption(label="Debate Teologico",    value="teologia",   description="Questoes de teologia e fe"),
    discord.SelectOption(label="Parceria",            value="parceria",   description="Proposta de parceria ou colaboracao"),
    discord.SelectOption(label="Outros",              value="outros",     description="Outros assuntos"),
]

TICKET_LABEL_MAP = {
    "suporte":   "Suporte Geral",
    "denuncia":  "Denuncia",
    "filosofia": "Debate Filosofico",
    "teologia":  "Debate Teologico",
    "parceria":  "Parceria",
    "outros":    "Outros",
}


# ════════════════════════════════════════════════════════════════════════════
# MODALS
# ════════════════════════════════════════════════════════════════════════════

class TicketMotivoModal(Modal, title="Descreva seu ticket"):
    motivo = TextInput(
        label="Qual e o motivo do seu ticket?",
        placeholder="Descreva brevemente sua solicitacao.",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500,
    )

    def __init__(self, categoria: str):
        super().__init__()
        self.categoria = categoria

    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.cogs.get("Tickets")
        if cog:
            await cog._criar_ticket(interaction, self.categoria, self.motivo.value)


class AdicionarMembroModal(Modal, title="Adicionar membro ao ticket"):
    user_id = TextInput(
        label="ID do usuario",
        placeholder="ID numerico do Discord",
        required=True,
        max_length=20,
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            uid = int(self.user_id.value.strip())
        except ValueError:
            return await interaction.response.send_message(
                embed=embed_error("ID invalido", "Informe um ID numerico valido."), ephemeral=True)
        member = interaction.guild.get_member(uid)
        if not member:
            return await interaction.response.send_message(
                embed=embed_error("Nao encontrado", "Membro nao esta no servidor."), ephemeral=True)
        await interaction.channel.set_permissions(
            member, view_channel=True, send_messages=True, read_message_history=True)
        await interaction.response.send_message(
            embed=embed_success("Membro adicionado", f"{member.mention} foi adicionado ao ticket."),
            ephemeral=True)
        await interaction.channel.send(
            embed=discord.Embed(
                description=f"{member.mention} foi adicionado ao ticket por {interaction.user.mention}.",
                color=MAIN_COLOR))


class RemoverMembroModal(Modal, title="Remover membro do ticket"):
    user_id = TextInput(
        label="ID do usuario",
        placeholder="ID numerico do Discord",
        required=True,
        max_length=20,
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            uid = int(self.user_id.value.strip())
        except ValueError:
            return await interaction.response.send_message(
                embed=embed_error("ID invalido", "Informe um ID numerico valido."), ephemeral=True)
        member = interaction.guild.get_member(uid)
        if not member:
            return await interaction.response.send_message(
                embed=embed_error("Nao encontrado", "Membro nao esta no servidor."), ephemeral=True)
        await interaction.channel.set_permissions(member, overwrite=None)
        await interaction.response.send_message(
            embed=embed_success("Membro removido", f"{member.mention} foi removido do ticket."),
            ephemeral=True)


class RenomearCanalModal(Modal, title="Renomear canal do ticket"):
    novo_nome = TextInput(
        label="Novo nome do canal",
        placeholder="Ex: ticket-filosofia-joao",
        required=True,
        max_length=50,
    )

    async def on_submit(self, interaction: discord.Interaction):
        nome = self.novo_nome.value.strip().lower().replace(" ", "-")
        try:
            await interaction.channel.edit(name=nome)
            await interaction.response.send_message(
                embed=embed_success("Canal renomeado", f"Canal renomeado para: {nome}."), ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(embed=embed_error("Erro", str(e)), ephemeral=True)


class PainelEmbedModal(Modal, title="Configurar painel de tickets"):
    titulo    = TextInput(label="Titulo",      default="Suporte e Atendimento", max_length=256)
    descricao = TextInput(
        label="Descricao", style=discord.TextStyle.paragraph, max_length=2048,
        default=(
            "Selecione a categoria que melhor descreve sua solicitacao.\n\n"
            "Categorias disponiveis:\n"
            "Suporte Geral, Denuncia, Debate Filosofico, Debate Teologico, Parceria, Outros.\n\n"
            "Aguarde o atendimento da equipe apos abrir o ticket."
        )
    )
    cor    = TextInput(label="Cor hex (ex: #8E44AD)", default="#8E44AD", max_length=9, required=False)
    banner = TextInput(label="URL do banner (opcional)", required=False, placeholder="https://...")
    footer = TextInput(label="Rodape", required=False, default="Filosofia Bot — Atendimento")

    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.cogs.get("Tickets")
        if cog:
            await cog._enviar_painel(
                interaction, self.titulo.value, self.descricao.value,
                self.cor.value, self.banner.value, self.footer.value)


class EditarEmbedModal(Modal, title="Editar painel de tickets"):
    titulo    = TextInput(label="Novo titulo",    max_length=256)
    descricao = TextInput(label="Nova descricao", style=discord.TextStyle.paragraph, max_length=2048)
    cor    = TextInput(label="Nova cor hex",      default="#8E44AD", max_length=9, required=False)
    banner = TextInput(label="Nova URL do banner", required=False)
    footer = TextInput(label="Novo rodape",        required=False)

    def __init__(self, message: discord.Message):
        super().__init__()
        self.message = message
        if message.embeds:
            emb = message.embeds[0]
            self.titulo.default    = emb.title or ""
            self.descricao.default = emb.description or ""
            if emb.footer:
                self.footer.default = emb.footer.text or ""

    async def on_submit(self, interaction: discord.Interaction):
        try:
            color = int(self.cor.value.lstrip("#"), 16) if self.cor.value else MAIN_COLOR
        except Exception:
            color = MAIN_COLOR
        emb = discord.Embed(title=self.titulo.value, description=self.descricao.value, color=color)
        if self.banner.value:
            emb.set_image(url=self.banner.value)
        if self.footer.value:
            emb.set_footer(text=self.footer.value)
        await self.message.edit(embed=emb)
        await interaction.response.send_message(
            embed=embed_success("Painel atualizado", "A embed foi editada com sucesso."), ephemeral=True)


# ════════════════════════════════════════════════════════════════════════════
# SELECT MENU
# ════════════════════════════════════════════════════════════════════════════

class TicketCategorySelect(Select):
    def __init__(self):
        super().__init__(
            placeholder="Selecione o motivo do seu ticket...",
            options=TICKET_CATEGORIES,
            min_values=1,
            max_values=1,
            custom_id="ticket_category_select",
        )

    async def callback(self, interaction: discord.Interaction):
        categoria = self.values[0]
        cog = interaction.client.cogs.get("Tickets")
        if not cog:
            return
        ticket_aberto = await Database.get_open_ticket_by_user(interaction.guild.id, interaction.user.id)
        if ticket_aberto:
            canal = interaction.guild.get_channel(ticket_aberto["channel_id"])
            if canal:
                return await interaction.response.send_message(
                    embed=embed_error(
                        "Ticket ja aberto",
                        f"Voce ja possui um ticket aberto: {canal.mention}\nFeche-o antes de abrir outro."),
                    ephemeral=True)
        cfg_cat = await Database.guild_get(interaction.guild.id, "tickets_config", "ticket_category_id")
        if not cfg_cat:
            return await interaction.response.send_message(
                embed=embed_error("Nao configurado", "O sistema de tickets nao esta configurado. Use /ticket setup."),
                ephemeral=True)
        await interaction.response.send_modal(TicketMotivoModal(categoria))


class TicketSelectView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketCategorySelect())


# ════════════════════════════════════════════════════════════════════════════
# PAINEL ADMIN DO TICKET
# ════════════════════════════════════════════════════════════════════════════

class TicketAdminView(View):
    def __init__(self, opener_id: int):
        super().__init__(timeout=None)
        self.opener_id = opener_id

    async def _is_staff(self, interaction: discord.Interaction) -> bool:
        staff_ids = await Database.guild_get(interaction.guild.id, "tickets_config", "staff_role_ids") or []
        user_role_ids = {r.id for r in interaction.user.roles}
        return bool(user_role_ids & set(staff_ids)) or interaction.user.guild_permissions.administrator

    @discord.ui.button(label="Adicionar membro", style=discord.ButtonStyle.primary, row=0)
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._is_staff(interaction):
            return await interaction.response.send_message(
                embed=embed_error("Sem permissao", "Apenas a equipe pode usar esta acao."), ephemeral=True)
        await interaction.response.send_modal(AdicionarMembroModal())

    @discord.ui.button(label="Remover membro", style=discord.ButtonStyle.secondary, row=0)
    async def remove_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._is_staff(interaction):
            return await interaction.response.send_message(
                embed=embed_error("Sem permissao", "Apenas a equipe pode usar esta acao."), ephemeral=True)
        await interaction.response.send_modal(RemoverMembroModal())

    @discord.ui.button(label="Renomear canal", style=discord.ButtonStyle.secondary, row=0)
    async def renomear(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._is_staff(interaction):
            return await interaction.response.send_message(
                embed=embed_error("Sem permissao", "Apenas a equipe pode usar esta acao."), ephemeral=True)
        await interaction.response.send_modal(RenomearCanalModal())

    @discord.ui.button(label="Gerar transcricao", style=discord.ButtonStyle.success, row=1)
    async def transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._is_staff(interaction):
            return await interaction.response.send_message(
                embed=embed_error("Sem permissao", "Apenas a equipe pode usar esta acao."), ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        linhas = []
        async for msg in interaction.channel.history(limit=300, oldest_first=True):
            ts = msg.created_at.strftime("%d/%m/%Y %H:%M")
            conteudo = msg.content or "[embed ou anexo]"
            linhas.append(f"[{ts}] {msg.author} ({msg.author.id}): {conteudo}")
        texto = "\n".join(linhas) or "Nenhuma mensagem encontrada."
        arquivo = discord.File(
            fp=io.BytesIO(texto.encode("utf-8")),
            filename=f"transcricao-{interaction.channel.name}.txt",
        )
        await interaction.followup.send(
            embed=embed_success("Transcricao gerada", f"Log do canal: {interaction.channel.name}"),
            file=arquivo,
            ephemeral=True,
        )

    @discord.ui.button(label="Fechar silenciosamente", style=discord.ButtonStyle.danger, row=1)
    async def fechar_silencioso(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._is_staff(interaction):
            return await interaction.response.send_message(
                embed=embed_error("Sem permissao", "Apenas a equipe pode usar esta acao."), ephemeral=True)
        await interaction.response.send_message(
            embed=embed_info("Encerrando ticket", "Canal sera removido em 3 segundos."))
        await Database.close_ticket(interaction.channel.id)
        await asyncio.sleep(3)
        try:
            await interaction.channel.delete()
        except discord.HTTPException:
            pass


# ════════════════════════════════════════════════════════════════════════════
# VIEW PRINCIPAL DO TICKET
# ════════════════════════════════════════════════════════════════════════════

class TicketMainView(View):
    def __init__(self, opener_id: int):
        super().__init__(timeout=None)
        self.opener_id = opener_id

    async def _is_staff(self, interaction: discord.Interaction) -> bool:
        staff_ids = await Database.guild_get(interaction.guild.id, "tickets_config", "staff_role_ids") or []
        user_role_ids = {r.id for r in interaction.user.roles}
        return bool(user_role_ids & set(staff_ids)) or interaction.user.guild_permissions.administrator

    @discord.ui.button(label="Atender", style=discord.ButtonStyle.success,
                       custom_id="ticket_atender", row=0)
    async def atender(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._is_staff(interaction):
            return await interaction.response.send_message(
                embed=embed_error("Sem permissao", "Apenas a equipe pode assumir tickets."), ephemeral=True)
        await Database.set_attendant(interaction.channel.id, interaction.user.id)
        emb = discord.Embed(
            title="Ticket em atendimento",
            description=(
                f"Atendente: {interaction.user.mention}\n\n"
                f"Prezado usuario, estou aqui para auxiliar. Como posso ajuda-lo?"
            ),
            color=MAIN_COLOR,
        )
        emb.set_thumbnail(url=interaction.user.display_avatar.url)
        emb.timestamp = discord.utils.utcnow()
        await interaction.response.send_message(embed=emb)

    @discord.ui.button(label="Painel de gestao", style=discord.ButtonStyle.primary,
                       custom_id="ticket_admin_panel", row=0)
    async def painel_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._is_staff(interaction):
            return await interaction.response.send_message(
                embed=embed_error("Sem permissao", "Apenas a equipe pode acessar o painel de gestao."),
                ephemeral=True)
        emb = discord.Embed(
            title="Painel de gestao do ticket",
            description=(
                "Acoes disponiveis para a equipe:\n\n"
                "Adicionar membro: concede acesso ao canal.\n"
                "Remover membro: revoga o acesso.\n"
                "Renomear canal: altera o nome do ticket.\n"
                "Gerar transcricao: exporta o historico em arquivo .txt.\n"
                "Fechar silenciosamente: encerra sem aviso ao usuario."
            ),
            color=MAIN_COLOR,
        )
        emb.timestamp = discord.utils.utcnow()
        await interaction.response.send_message(
            embed=emb, view=TicketAdminView(self.opener_id), ephemeral=True)

    @discord.ui.button(label="Fechar ticket", style=discord.ButtonStyle.danger,
                       custom_id="ticket_fechar", row=1)
    async def fechar(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_staff = await self._is_staff(interaction)
        is_owner = interaction.user.id == self.opener_id
        if not (is_staff or is_owner):
            return await interaction.response.send_message(
                embed=embed_error("Sem permissao", "Apenas a equipe ou quem abriu o ticket pode fecha-lo."),
                ephemeral=True)
        await interaction.response.send_message(
            embed=embed_info("Encerrando ticket", "Canal sera removido em 5 segundos."))
        cog = interaction.client.cogs.get("Tickets")
        if cog:
            await cog._log_ticket(interaction.guild,
                f"Ticket encerrado", f"Canal: {interaction.channel.name}\nEncerrado por: {interaction.user.mention}")
        await Database.close_ticket(interaction.channel.id)
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Ticket encerrado por {interaction.user}")
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Notificar equipe", style=discord.ButtonStyle.secondary,
                       custom_id="ticket_notificar", row=1)
    async def notificar(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket = await Database.get_ticket(interaction.channel.id)
        if ticket and ticket["attendant_id"]:
            atendente = interaction.guild.get_member(ticket["attendant_id"])
            if atendente:
                return await interaction.response.send_message(
                    content=atendente.mention,
                    embed=discord.Embed(
                        description=f"{interaction.user.mention} aguarda atendimento neste ticket.",
                        color=MAIN_COLOR))
        staff_ids = await Database.guild_get(interaction.guild.id, "tickets_config", "staff_role_ids") or []
        staff_roles = [interaction.guild.get_role(rid) for rid in staff_ids if interaction.guild.get_role(rid)]
        if staff_roles:
            mentions = " ".join(r.mention for r in staff_roles)
            await interaction.response.send_message(
                content=mentions,
                embed=discord.Embed(
                    description=f"{interaction.user.mention} aguarda atendimento neste ticket.",
                    color=MAIN_COLOR))
        else:
            await interaction.response.send_message(
                embed=embed_error("Sem equipe configurada", "Use /ticket setup para configurar os cargos de equipe."),
                ephemeral=True)


# ════════════════════════════════════════════════════════════════════════════
# COG PRINCIPAL
# ════════════════════════════════════════════════════════════════════════════

class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(TicketSelectView())
        bot.add_view(TicketMainView(opener_id=0))

    async def _log_ticket(self, guild: discord.Guild, titulo: str, descricao: str):
        ch_id = await Database.guild_get(guild.id, "tickets_config", "log_channel_id")
        if not ch_id:
            return
        ch = guild.get_channel(int(ch_id))
        if ch:
            emb = discord.Embed(title=titulo, description=descricao, color=MAIN_COLOR,
                                timestamp=discord.utils.utcnow())
            try:
                await ch.send(embed=emb)
            except Exception:
                pass

    async def _criar_ticket(self, interaction: discord.Interaction, categoria: str, motivo: str):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        category_id  = await Database.guild_get(guild.id, "tickets_config", "ticket_category_id")
        category     = guild.get_channel(int(category_id)) if category_id else None
        staff_ids    = await Database.guild_get(guild.id, "tickets_config", "staff_role_ids") or []
        staff_roles  = [guild.get_role(rid) for rid in staff_ids if guild.get_role(rid)]
        label        = TICKET_LABEL_MAP.get(categoria, "Ticket")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user:   discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                read_message_history=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                manage_channels=True, manage_messages=True, read_message_history=True),
        }
        for role in staff_roles:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                read_message_history=True, manage_messages=True)

        nome = f"ticket-{interaction.user.name}"[:50].lower().replace(" ", "-")
        try:
            channel = await guild.create_text_channel(
                name=nome,
                category=category if isinstance(category, discord.CategoryChannel) else None,
                overwrites=overwrites,
                reason=f"Ticket aberto por {interaction.user} — {label}",
            )
        except discord.Forbidden:
            return await interaction.followup.send(
                embed=embed_error("Sem permissao", "Nao foi possivel criar o canal. Verifique as permissoes do bot."),
                ephemeral=True)

        await Database.open_ticket(guild.id, channel.id, interaction.user.id, categoria, motivo)

        banner_url = await Database.guild_get(guild.id, "tickets_config", "ticket_banner_url")

        emb = discord.Embed(
            title=label,
            description=(
                f"Solicitante: {interaction.user.mention}\n"
                f"Categoria: {label}\n"
                f"Descricao: {motivo}\n\n"
                f"Prezado(a) {interaction.user.mention}, sua solicitacao foi registrada.\n"
                f"Um membro da equipe ira atende-lo em breve. Por favor, aguarde."
            ),
            color=MAIN_COLOR,
        )
        emb.set_thumbnail(url=interaction.user.display_avatar.url)
        emb.set_footer(text=f"{guild.name}   ID: {interaction.user.id}")
        emb.timestamp = discord.utils.utcnow()
        if banner_url:
            emb.set_image(url=banner_url)

        staff_ping = " ".join(r.mention for r in staff_roles) if staff_roles else ""
        await channel.send(
            content=f"{interaction.user.mention} {staff_ping}".strip(),
            embed=emb,
            view=TicketMainView(opener_id=interaction.user.id),
        )

        await interaction.followup.send(
            embed=embed_success("Ticket aberto", f"Seu ticket foi aberto em {channel.mention}."),
            ephemeral=True)
        await self._log_ticket(guild, "Ticket aberto",
            f"Solicitante: {interaction.user.mention}\nCategoria: {label}\nCanal: {channel.mention}")

    async def _enviar_painel(self, interaction, titulo, descricao, cor, banner, footer):
        try:
            color = int(cor.lstrip("#"), 16) if cor else MAIN_COLOR
        except Exception:
            color = MAIN_COLOR
        emb = discord.Embed(title=titulo, description=descricao, color=color)
        if banner:
            emb.set_image(url=banner)
        if footer:
            emb.set_footer(text=footer)
        ch_id = await Database.guild_get(interaction.guild.id, "tickets_config", "panel_channel_id")
        ch = interaction.guild.get_channel(int(ch_id)) if ch_id else interaction.channel
        msg = await ch.send(embed=emb, view=TicketSelectView())
        await Database.guild_set(interaction.guild.id, "tickets_config", "panel_message_id", str(msg.id))
        await Database.guild_set(interaction.guild.id, "tickets_config", "panel_channel_id", str(ch.id))
        await interaction.response.send_message(
            embed=embed_success("Painel publicado", f"Painel de tickets publicado em {ch.mention}."),
            ephemeral=True)

    # ════════════════════════════════════════════════════════════════════════
    # SLASH COMMANDS
    # ════════════════════════════════════════════════════════════════════════
    ticket_group = app_commands.Group(name="ticket", description="Sistema de tickets")

    @ticket_group.command(name="setup", description="Configura o sistema de tickets")
    @app_commands.describe(
        categoria="Categoria onde os canais de ticket serao criados",
        cargo_staff="Cargo principal da equipe (obrigatorio)",
        cargo_staff_2="Segundo cargo de equipe (opcional)",
        cargo_staff_3="Terceiro cargo de equipe (opcional)",
        canal_log="Canal para logs dos tickets (opcional)",
        banner_url="URL do banner exibido dentro do ticket (opcional)",
        canal_painel="Canal onde o painel sera publicado",
    )
    @app_commands.default_permissions(administrator=True)
    async def ticket_setup(
        self,
        inter: discord.Interaction,
        categoria: discord.CategoryChannel,
        cargo_staff: discord.Role,
        canal_painel: discord.TextChannel,
        cargo_staff_2: discord.Role = None,
        cargo_staff_3: discord.Role = None,
        canal_log: discord.TextChannel = None,
        banner_url: str = None,
    ):
        cargos = [cargo_staff]
        for c in [cargo_staff_2, cargo_staff_3]:
            if c and c.id not in {x.id for x in cargos}:
                cargos.append(c)

        await Database.guild_set(inter.guild.id, "tickets_config", "ticket_category_id", str(categoria.id))
        await Database.guild_set(inter.guild.id, "tickets_config", "staff_role_ids",     [c.id for c in cargos])
        await Database.guild_set(inter.guild.id, "tickets_config", "panel_channel_id",   str(canal_painel.id))
        if canal_log:
            await Database.guild_set(inter.guild.id, "tickets_config", "log_channel_id", str(canal_log.id))
        if banner_url:
            await Database.guild_set(inter.guild.id, "tickets_config", "ticket_banner_url", banner_url)

        cargos_texto = ", ".join(c.mention for c in cargos)
        await inter.response.send_message(
            embed=embed_success(
                "Tickets configurados",
                f"Categoria: {categoria.mention}\n"
                f"Equipe: {cargos_texto}\n"
                f"Canal do painel: {canal_painel.mention}\n"
                f"Canal de log: {canal_log.mention if canal_log else 'Nao definido'}\n"
                f"Banner: {'Configurado' if banner_url else 'Nao definido'}\n\n"
                f"Use /ticket painel para publicar o painel no canal configurado."
            ),
            ephemeral=True)

    @ticket_group.command(name="painel", description="Publica o painel de abertura de tickets")
    @app_commands.default_permissions(administrator=True)
    async def ticket_painel(self, inter: discord.Interaction):
        await inter.response.send_modal(PainelEmbedModal())

    @ticket_group.command(name="editpainel", description="Edita o painel ja publicado")
    @app_commands.describe(message_id="ID da mensagem (vazio para o painel salvo)")
    @app_commands.default_permissions(administrator=True)
    async def ticket_editpainel(self, inter: discord.Interaction, message_id: str = None):
        try:
            if message_id:
                msg = await inter.channel.fetch_message(int(message_id))
            else:
                saved   = await Database.guild_get(inter.guild.id, "tickets_config", "panel_message_id")
                ch_id   = await Database.guild_get(inter.guild.id, "tickets_config", "panel_channel_id")
                if not saved:
                    return await inter.response.send_message(
                        embed=embed_error("Nao encontrado", "Use /ticket painel primeiro."), ephemeral=True)
                ch  = inter.guild.get_channel(int(ch_id)) if ch_id else inter.channel
                msg = await ch.fetch_message(int(saved))
            await inter.response.send_modal(EditarEmbedModal(msg))
        except Exception as ex:
            await inter.response.send_message(embed=embed_error("Erro", str(ex)), ephemeral=True)

    @ticket_group.command(name="fechar", description="Fecha o ticket atual")
    @app_commands.default_permissions(manage_channels=True)
    async def ticket_fechar(self, inter: discord.Interaction):
        ticket = await Database.get_ticket(inter.channel.id)
        if not ticket:
            return await inter.response.send_message(
                embed=embed_error("Nao e um ticket", "Este canal nao e um ticket ativo."), ephemeral=True)
        await inter.response.send_message(
            embed=embed_info("Encerrando ticket", "Canal sera removido em 5 segundos."))
        await self._log_ticket(inter.guild, "Ticket encerrado",
            f"Canal: {inter.channel.name}\nEncerrado por: {inter.user.mention}")
        await Database.close_ticket(inter.channel.id)
        await asyncio.sleep(5)
        try:
            await inter.channel.delete(reason=f"Ticket encerrado por {inter.user}")
        except discord.HTTPException:
            pass

    @ticket_group.command(name="lista", description="Lista todos os tickets abertos")
    @app_commands.default_permissions(manage_channels=True)
    async def ticket_lista(self, inter: discord.Interaction):
        tickets = await Database.list_open_tickets(inter.guild.id)
        if not tickets:
            return await inter.response.send_message(
                embed=embed_info("Sem tickets", "Nao ha tickets abertos no momento."), ephemeral=True)
        emb = discord.Embed(title="Tickets abertos", color=MAIN_COLOR)
        for t in tickets:
            ch     = inter.guild.get_channel(t["channel_id"])
            member = inter.guild.get_member(t["user_id"])
            label  = TICKET_LABEL_MAP.get(t["category"], t["category"])
            emb.add_field(
                name=f"#{ch.name if ch else t['channel_id']}",
                value=f"Solicitante: {member.mention if member else t['user_id']}\nCategoria: {label}",
                inline=True,
            )
        await inter.response.send_message(embed=emb, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
