"""
cogs/academia.py
Sistema de cargos acadêmicos com formulário filosófico, aprovação manual e cargo "Pendente".
"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from utils.helpers import embed_success, embed_error, embed_info, PHILO_COLOR
from utils.storage import Storage
from utils.emojis import E

log = logging.getLogger("filosofia.academia")

REQUIRES_REVIEW = {"mestrado", "doutorado", "pos_doutorado"}

LEVEL_LABELS = {
    "profissional":  "Profissional",
    "graduacao":     "Graduação+",
    "mestrado":      "Mestrado",
    "doutorado":     "Doutorado",
    "pos_doutorado": "Pós-doutorado",
}

LEVEL_EMOJIS = {
    "profissional":  E["n1"],
    "graduacao":     E["n2"],
    "mestrado":      E["n3"],
    "doutorado":     E["n4"],
    "pos_doutorado": E["n5"],
}


# ── Modal de candidatura ──────────────────────────────────────────────────────

class PhilosophyApplicationModal(discord.ui.Modal):
    area = discord.ui.TextInput(
        label="Qual é sua área de pesquisa ou especialização?",
        style=discord.TextStyle.paragraph,
        placeholder="Ex: Filosofia da Mente, Metaética, Lógica, Epistemologia...",
        max_length=600,
    )
    formacao = discord.ui.TextInput(
        label="Qual é sua formação acadêmica?",
        style=discord.TextStyle.paragraph,
        placeholder="Você pode omitir detalhes identificáveis, se preferir.",
        max_length=600,
    )
    obras = discord.ui.TextInput(
        label="Quais obras/autores você estuda recentemente?",
        style=discord.TextStyle.paragraph,
        placeholder="Comente o que achou interessante nelas.",
        max_length=600,
    )

    def __init__(self, level_key: str):
        super().__init__(title=f"Candidatura — {LEVEL_LABELS[level_key]}")
        self.level_key = level_key

    async def on_submit(self, inter: discord.Interaction):
        cog = inter.client.cogs.get("Academia")
        if cog:
            await cog.handle_application(inter, self.level_key, {
                "area":     self.area.value,
                "formacao": self.formacao.value,
                "obras":    self.obras.value,
            })


# ── Select de nível ───────────────────────────────────────────────────────────

class AcademicLevelSelect(discord.ui.Select):
    def __init__(self, storage: Storage, guild_id: int):
        options = []
        for key, label in LEVEL_LABELS.items():
            desc = "Requer formulário de avaliação" if key in REQUIRES_REVIEW else "Atribuído automaticamente"
            emoji_map = {"profissional": "1️⃣", "graduacao": "2️⃣", "mestrado": "3️⃣", "doutorado": "4️⃣", "pos_doutorado": "5️⃣"}
            options.append(discord.SelectOption(label=label, value=key, description=desc, emoji=emoji_map[key]))
        super().__init__(
            placeholder="Selecione seu nível acadêmico...",
            min_values=1, max_values=1,
            options=options,
            custom_id="academia:level_select",
        )
        self.storage  = storage
        self.guild_id = guild_id

    async def callback(self, inter: discord.Interaction):
        key = self.values[0]
        cog = inter.client.cogs.get("Academia")
        if not cog:
            return
        if key in REQUIRES_REVIEW:
            await inter.response.send_modal(PhilosophyApplicationModal(key))
        else:
            await inter.response.defer(ephemeral=True)
            await cog.assign_direct_role(inter, key)


class ManageRolesView(discord.ui.View):
    """View persistente — botão 'Gerenciar cargos'."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Gerenciar cargos",
        style=discord.ButtonStyle.primary,
        custom_id="academia:manage",
        emoji=discord.PartialEmoji.from_str("<a:32877animatedarrowbluelite:1430339008537428009>"),
    )
    async def manage_roles(self, inter: discord.Interaction, button: discord.ui.Button):
        cog = inter.client.cogs.get("Academia")
        if not cog:
            return
        has_any = any(
            cog.storage.guild_get(inter.guild.id, "academia_config", f"role_{k}")
            for k in LEVEL_LABELS
        )
        if not has_any:
            return await inter.response.send_message(
                embed=embed_error("Não configurado", "Os cargos acadêmicos ainda não foram configurados. Peça a um administrador para usar `/academia setup`."),
                ephemeral=True,
            )
        view = discord.ui.View(timeout=60)
        view.add_item(AcademicLevelSelect(cog.storage, inter.guild.id))
        emb = discord.Embed(
            title=f"{E['trophy']} Selecionar Nível Acadêmico",
            description=(
                f"{E['arrow_blue']} Selecione seu nível no menu abaixo.\n\n"
                f"{E['n1']} **Profissional** — atribuído automaticamente\n"
                f"{E['n2']} **Graduação+** — atribuído automaticamente\n"
                f"{E['n3']} **Mestrado** — requer formulário de avaliação\n"
                f"{E['n4']} **Doutorado** — requer formulário de avaliação\n"
                f"{E['n5']} **Pós-doutorado** — requer formulário de avaliação"
            ),
            color=PHILO_COLOR,
        )
        await inter.response.send_message(embed=emb, view=view, ephemeral=True)


# ── Botões de revisão ─────────────────────────────────────────────────────────

class ReviewView(discord.ui.View):
    def __init__(self, applicant_id: int, level_key: str):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id
        self.level_key    = level_key

        approve_btn = discord.ui.Button(
            label="Aprovar", style=discord.ButtonStyle.success,
            custom_id=f"academia:approve:{applicant_id}:{level_key}",
            emoji=discord.PartialEmoji.from_str("<a:9582dsicordveriyblack:1430269158024810598>"),
        )
        reject_btn = discord.ui.Button(
            label="Rejeitar", style=discord.ButtonStyle.danger,
            custom_id=f"academia:reject:{applicant_id}:{level_key}",
            emoji=discord.PartialEmoji.from_str("<:9848blurplemuted:1430269262332690565>"),
        )
        approve_btn.callback = self._approve
        reject_btn.callback  = self._reject
        self.add_item(approve_btn)
        self.add_item(reject_btn)

    async def _approve(self, inter: discord.Interaction):
        cog = inter.client.cogs.get("Academia")
        if cog:
            await cog.approve_application(inter, self.applicant_id, self.level_key)

    async def _reject(self, inter: discord.Interaction):
        cog = inter.client.cogs.get("Academia")
        if cog:
            await cog.reject_application(inter, self.applicant_id, self.level_key)


# ── Cog principal ─────────────────────────────────────────────────────────────

class Academia(commands.Cog):
    """Sistema de cargos acadêmicos com formulário e aprovação."""

    def __init__(self, bot: commands.Bot):
        self.bot     = bot
        self.storage: Storage = bot.storage
        bot.add_view(ManageRolesView())
        self._restore_review_views()

    def _restore_review_views(self):
        pending = self.storage.load_all("academia_pending")
        for key in pending:
            try:
                uid, level = key.split(":", 1)
                self.bot.add_view(ReviewView(int(uid), level))
            except Exception:
                pass

    def _cfg(self, gid: int, key: str, default=None):
        return self.storage.guild_get(gid, "academia_config", key) or default

    def _set(self, gid: int, key: str, value):
        self.storage.guild_set(gid, "academia_config", key, value)

    def _all_academic_role_ids(self, guild_id: int) -> set[int]:
        ids: set[int] = set()
        for key in LEVEL_LABELS:
            rid = self._cfg(guild_id, f"role_{key}")
            if rid:
                ids.add(int(rid))
        pending_rid = self._cfg(guild_id, "role_pending")
        if pending_rid:
            ids.add(int(pending_rid))
        return ids

    async def assign_direct_role(self, inter: discord.Interaction, level_key: str):
        guild   = inter.guild
        role_id = self._cfg(guild.id, f"role_{level_key}")
        if not role_id:
            return await inter.followup.send(
                embed=embed_error("Cargo não configurado", f"O cargo para **{LEVEL_LABELS[level_key]}** não foi configurado."),
                ephemeral=True,
            )
        role = guild.get_role(int(role_id))
        if not role:
            return await inter.followup.send(embed=embed_error("Cargo não encontrado", "O cargo configurado não existe mais."), ephemeral=True)
        member = inter.user
        ids    = self._all_academic_role_ids(guild.id)
        to_remove = [r for r in member.roles if r.id in ids]
        if to_remove:
            await member.remove_roles(*to_remove, reason="Atualização de nível acadêmico")
        await member.add_roles(role, reason=f"Nível acadêmico: {LEVEL_LABELS[level_key]}")
        await inter.followup.send(
            embed=embed_success("Cargo atribuído!", f"{E['arrow_blue']} Você recebeu o cargo {role.mention}."),
            ephemeral=True,
        )

    async def handle_application(self, inter: discord.Interaction, level_key: str, answers: dict):
        guild = inter.guild
        await inter.response.defer(ephemeral=True)

        pending_rid = self._cfg(guild.id, "role_pending")
        if pending_rid:
            pending_role = guild.get_role(int(pending_rid))
            if pending_role and pending_role not in inter.user.roles:
                await inter.user.add_roles(pending_role, reason="Candidatura acadêmica pendente")

        key = f"{inter.user.id}:{level_key}"
        self.storage.set("academia_pending", key, {
            "guild_id": guild.id,
            "user_id":  inter.user.id,
            "level":    level_key,
            "answers":  answers,
        })

        review_ch_id = self._cfg(guild.id, "review_channel")
        if review_ch_id:
            review_ch = guild.get_channel(int(review_ch_id))
            if review_ch:
                emb = discord.Embed(
                    title=f"{E['bulb']} Nova Candidatura — {LEVEL_LABELS[level_key]}",
                    color=PHILO_COLOR,
                )
                emb.set_author(name=str(inter.user), icon_url=inter.user.display_avatar.url)
                emb.add_field(name=f"{E['arrow_white']} Usuário",   value=f"{inter.user.mention} (`{inter.user.id}`)", inline=True)
                emb.add_field(name=f"{E['trophy']} Nível",          value=LEVEL_LABELS[level_key], inline=True)
                emb.add_field(name=f"{E['n1']} Área de pesquisa",   value=answers["area"],    inline=False)
                emb.add_field(name=f"{E['n2']} Formação",           value=answers["formacao"], inline=False)
                emb.add_field(name=f"{E['n3']} Obras recentes",     value=answers["obras"],   inline=False)
                emb.set_footer(text=f"ID da candidatura: {key}")
                view = ReviewView(inter.user.id, level_key)
                self.bot.add_view(view)
                await review_ch.send(embed=emb, view=view)

        await inter.followup.send(
            embed=embed_info(
                "Candidatura enviada!",
                f"{E['loading']} Sua candidatura para **{LEVEL_LABELS[level_key]}** foi enviada para análise.\n\n"
                f"Você recebeu o cargo **Pendente** enquanto aguarda avaliação.",
            ),
            ephemeral=True,
        )

    async def approve_application(self, inter: discord.Interaction, applicant_id: int, level_key: str):
        await inter.response.defer()
        guild = inter.guild
        key   = f"{applicant_id}:{level_key}"
        data  = self.storage.get("academia_pending", key)
        if not data:
            return await inter.followup.send(embed=embed_error("Não encontrado", "Candidatura não localizada."), ephemeral=True)

        member = guild.get_member(applicant_id)
        if not member:
            return await inter.followup.send(embed=embed_error("Usuário não encontrado", "O usuário saiu do servidor."), ephemeral=True)

        role_id = self._cfg(guild.id, f"role_{level_key}")
        if not role_id:
            return await inter.followup.send(embed=embed_error("Cargo não configurado"), ephemeral=True)
        role = guild.get_role(int(role_id))
        if not role:
            return await inter.followup.send(embed=embed_error("Cargo não existe"), ephemeral=True)

        ids = self._all_academic_role_ids(guild.id)
        to_remove = [r for r in member.roles if r.id in ids]
        if to_remove:
            await member.remove_roles(*to_remove, reason="Aprovação acadêmica")
        await member.add_roles(role, reason=f"Aprovado por {inter.user}: {LEVEL_LABELS[level_key]}")
        self.storage.delete("academia_pending", key)

        try:
            emb_dm = discord.Embed(
                title=f"{E['verified']} Candidatura aprovada!",
                description=f"Sua candidatura para **{LEVEL_LABELS[level_key]}** em **{guild.name}** foi aprovada.\n\nVocê recebeu o cargo {role.mention}.",
                color=0x57F287,
            )
            await member.send(embed=emb_dm)
        except Exception:
            pass

        await inter.message.edit(
            embed=discord.Embed(
                title=f"{E['verified']} Aprovado — {LEVEL_LABELS[level_key]}",
                description=f"{E['arrow_white']} **Usuário:** {member.mention}\n{E['pin']} **Aprovado por:** {inter.user.mention}",
                color=0x57F287,
            ),
            view=None,
        )
        await inter.followup.send(embed=embed_success("Aprovado!", f"{member.mention} recebeu o cargo {role.mention}."), ephemeral=True)

    async def reject_application(self, inter: discord.Interaction, applicant_id: int, level_key: str):
        await inter.response.defer()
        guild  = inter.guild
        key    = f"{applicant_id}:{level_key}"
        data   = self.storage.get("academia_pending", key)
        if not data:
            return await inter.followup.send(embed=embed_error("Não encontrado", "Candidatura não localizada."), ephemeral=True)

        member = guild.get_member(applicant_id)
        if member:
            pending_rid = self._cfg(guild.id, "role_pending")
            if pending_rid:
                pr = guild.get_role(int(pending_rid))
                if pr and pr in member.roles:
                    await member.remove_roles(pr, reason="Candidatura rejeitada")
            try:
                emb_dm = discord.Embed(
                    title=f"{E['exclaim']} Candidatura não aprovada",
                    description=f"Sua candidatura para **{LEVEL_LABELS[level_key]}** em **{guild.name}** não foi aprovada desta vez.\n\nSe tiver dúvidas, entre em contato com a equipe do servidor.",
                    color=0xED4245,
                )
                await member.send(embed=emb_dm)
            except Exception:
                pass

        self.storage.delete("academia_pending", key)
        await inter.message.edit(
            embed=discord.Embed(
                title=f"{E['exclaim']} Rejeitado — {LEVEL_LABELS[level_key]}",
                description=(
                    f"{E['arrow_white']} **Usuário:** {member.mention if member else f'ID {applicant_id}'}\n"
                    f"{E['pin']} **Rejeitado por:** {inter.user.mention}"
                ),
                color=0xED4245,
            ),
            view=None,
        )
        await inter.followup.send(embed=embed_success("Rejeitado.", "Candidatura rejeitada e usuário notificado."), ephemeral=True)

    # ── Slash commands ────────────────────────────────────────────────────────
    academia_group = app_commands.Group(name="academia", description="Sistema de cargos acadêmicos")

    @academia_group.command(name="setup", description="Configura os cargos do sistema acadêmico")
    @app_commands.describe(
        profissional="Cargo para Profissional",
        graduacao="Cargo para Graduação+",
        mestrado="Cargo para Mestrado",
        doutorado="Cargo para Doutorado",
        pos_doutorado="Cargo para Pós-doutorado",
        pendente="Cargo temporário enquanto aguarda aprovação",
        canal_revisao="Canal onde as candidaturas serão analisadas pelos moderadores"
    )
    @app_commands.default_permissions(administrator=True)
    async def academia_setup(
        self, inter: discord.Interaction,
        profissional: discord.Role, graduacao: discord.Role,
        mestrado: discord.Role, doutorado: discord.Role,
        pos_doutorado: discord.Role, pendente: discord.Role,
        canal_revisao: discord.TextChannel,
    ):
        gid = inter.guild.id
        self._set(gid, "role_profissional",  str(profissional.id))
        self._set(gid, "role_graduacao",     str(graduacao.id))
        self._set(gid, "role_mestrado",      str(mestrado.id))
        self._set(gid, "role_doutorado",     str(doutorado.id))
        self._set(gid, "role_pos_doutorado", str(pos_doutorado.id))
        self._set(gid, "role_pending",       str(pendente.id))
        self._set(gid, "review_channel",     str(canal_revisao.id))

        await inter.response.send_message(
            embed=embed_success(
                "Academia configurada!",
                f"{E['n1']} Profissional → {profissional.mention}\n"
                f"{E['n2']} Graduação+ → {graduacao.mention}\n"
                f"{E['n3']} Mestrado → {mestrado.mention}\n"
                f"{E['n4']} Doutorado → {doutorado.mention}\n"
                f"{E['n5']} Pós-doutorado → {pos_doutorado.mention}\n"
                f"{E['loading']} Pendente → {pendente.mention}\n"
                f"{E['rules']} Canal de revisão → {canal_revisao.mention}",
            ),
            ephemeral=True,
        )

    @academia_group.command(name="painel", description="Envia o painel de seleção de cargos acadêmicos em um canal")
    @app_commands.describe(
        canal="Canal onde enviar o painel",
        titulo="Título da embed (padrão: 'Cargos Acadêmicos')",
        descricao="Descrição da embed"
    )
    @app_commands.default_permissions(administrator=True)
    async def academia_painel(
        self, inter: discord.Interaction,
        canal: discord.TextChannel,
        titulo: str = "Cargos Acadêmicos",
        descricao: str = "Clique abaixo para selecionar seu nível acadêmico e receber o cargo correspondente.",
    ):
        emb = discord.Embed(title=f"{E['trophy']} {titulo}", description=descricao, color=PHILO_COLOR)
        emb.set_footer(text="Filosofia Bot • Academia")
        await canal.send(embed=emb, view=ManageRolesView())
        await inter.response.send_message(
            embed=embed_success("Painel enviado!", f"Painel acadêmico enviado em {canal.mention}."),
            ephemeral=True,
        )

    @academia_group.command(name="pendentes", description="Lista todas as candidaturas pendentes de análise")
    @app_commands.default_permissions(manage_guild=True)
    async def academia_pendentes(self, inter: discord.Interaction):
        pending = self.storage.load_all("academia_pending")
        guild_pending = {k: v for k, v in pending.items() if v.get("guild_id") == inter.guild.id}
        if not guild_pending:
            return await inter.response.send_message(
                embed=embed_info("Sem pendências", "Não há candidaturas aguardando análise."),
                ephemeral=True,
            )
        emb = discord.Embed(title=f"{E['loading']} Candidaturas Pendentes", color=PHILO_COLOR)
        for key, data in guild_pending.items():
            member = inter.guild.get_member(data["user_id"])
            emb.add_field(
                name=f"{E['arrow_white']} {member or data['user_id']}",
                value=f"{E['trophy']} **Nível:** {LEVEL_LABELS.get(data['level'], data['level'])}",
                inline=False,
            )
        await inter.response.send_message(embed=emb, ephemeral=True)

    @academia_group.command(name="remover_cargo", description="Remove todos os cargos acadêmicos de um membro")
    @app_commands.describe(membro="Membro alvo")
    @app_commands.default_permissions(manage_roles=True)
    async def academia_remove(self, inter: discord.Interaction, membro: discord.Member):
        await inter.response.defer(ephemeral=True)
        ids = self._all_academic_role_ids(inter.guild.id)
        to_remove = [r for r in membro.roles if r.id in ids]
        if to_remove:
            await membro.remove_roles(*to_remove, reason=f"Remoção por {inter.user}")
        await inter.followup.send(
            embed=embed_success("Cargos removidos!", f"Cargos acadêmicos de {membro.mention} removidos."),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Academia(bot))
