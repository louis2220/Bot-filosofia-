"""
cogs/academia.py — Sistema de cargos acadêmicos do Servidor Filosofia.
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

# Títulos do modal — MÁXIMO 45 CARACTERES (limite do Discord)
MODAL_TITLES = {
    "mestrado":      "Candidatura — Mestrado",
    "doutorado":     "Candidatura — Doutorado",
    "pos_doutorado": "Candidatura — Pós-doutorado",
}
# Verificação em tempo de importação
for k, t in MODAL_TITLES.items():
    assert len(t) <= 45, f"Título do modal '{t}' tem {len(t)} chars (máx 45)"


# ═══════════════════════════════════════════════════════════
# MODAL
# ═══════════════════════════════════════════════════════════

class PhilosophyApplicationModal(discord.ui.Modal):
    area = discord.ui.TextInput(
        label="Área de pesquisa ou especialização",   # ≤ 45 chars
        style=discord.TextStyle.paragraph,
        placeholder="Ex: Filosofia da Mente, Metaética, Lógica...",
        max_length=600,
    )
    formacao = discord.ui.TextInput(
        label="Formação acadêmica",                   # ≤ 45 chars
        style=discord.TextStyle.paragraph,
        placeholder="Pode omitir detalhes que te identifiquem.",
        max_length=600,
        required=False,
    )
    obras = discord.ui.TextInput(
        label="Obras/autores estudados recentemente", # ≤ 45 chars
        style=discord.TextStyle.paragraph,
        placeholder="Comente o que achou interessante.",
        max_length=600,
    )

    def __init__(self, level_key: str):
        super().__init__(title=MODAL_TITLES[level_key])
        self.level_key = level_key

    async def on_submit(self, inter: discord.Interaction):
        # Responde imediatamente — evita timeout de 3s
        await inter.response.send_message(
            embed=embed_info(
                "Candidatura enviada!",
                f"{E['loading']} Sua candidatura para **{LEVEL_LABELS[self.level_key]}** "
                f"foi enviada para análise.\n\nVocê receberá o cargo **Pendente** em breve."
            ),
            ephemeral=True,
        )
        # Processa em segundo plano (sem segurar a interação)
        cog = inter.client.cogs.get("Academia")
        if cog:
            await cog.handle_application(inter, self.level_key, {
                "area":     self.area.value,
                "formacao": self.formacao.value,
                "obras":    self.obras.value,
            })


# ═══════════════════════════════════════════════════════════
# SELECT MENU
# ═══════════════════════════════════════════════════════════

class AcademicLevelSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Selecione seu nível acadêmico...",
            min_values=1,
            max_values=1,
            custom_id="academia:level_select",
            options=[
                discord.SelectOption(label="Profissional",  value="profissional",  description="Atribuído automaticamente",      emoji="1️⃣"),
                discord.SelectOption(label="Graduação+",    value="graduacao",     description="Atribuído automaticamente",      emoji="2️⃣"),
                discord.SelectOption(label="Mestrado",      value="mestrado",      description="Requer formulário de avaliação", emoji="3️⃣"),
                discord.SelectOption(label="Doutorado",     value="doutorado",     description="Requer formulário de avaliação", emoji="4️⃣"),
                discord.SelectOption(label="Pós-doutorado", value="pos_doutorado", description="Requer formulário de avaliação", emoji="5️⃣"),
            ],
        )

    async def callback(self, inter: discord.Interaction):
        key = self.values[0]
        cog = inter.client.cogs.get("Academia")
        if not cog:
            return
        if key in REQUIRES_REVIEW:
            # send_modal é a única resposta permitida aqui — não defer antes
            await inter.response.send_modal(PhilosophyApplicationModal(key))
        else:
            await inter.response.defer(ephemeral=True)
            await cog.assign_direct_role(inter, key)


# ═══════════════════════════════════════════════════════════
# BOTÃO PRINCIPAL
# ═══════════════════════════════════════════════════════════

class ManageRolesView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Gerenciar cargos",
        style=discord.ButtonStyle.primary,
        custom_id="academia:manage",
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
                embed=embed_error("Não configurado",
                    "Os cargos ainda não foram configurados. Use `/academia setup`."),
                ephemeral=True,
            )
        view = discord.ui.View(timeout=120)
        view.add_item(AcademicLevelSelect())
        await inter.response.send_message(
            content="Selecione seu nível acadêmico:",
            view=view,
            ephemeral=True,
        )


# ═══════════════════════════════════════════════════════════
# BOTÕES DE REVISÃO
# ═══════════════════════════════════════════════════════════

class ReviewView(discord.ui.View):
    def __init__(self, applicant_id: int, level_key: str):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id
        self.level_key    = level_key

        approve_btn = discord.ui.Button(
            label="✅ Aprovar", style=discord.ButtonStyle.success,
            custom_id=f"academia:approve:{applicant_id}:{level_key}",
        )
        reject_btn = discord.ui.Button(
            label="❌ Rejeitar", style=discord.ButtonStyle.danger,
            custom_id=f"academia:reject:{applicant_id}:{level_key}",
        )
        approve_btn.callback = self._approve
        reject_btn.callback  = self._reject
        self.add_item(approve_btn)
        self.add_item(reject_btn)

    def _disable(self):
        for item in self.children:
            item.disabled = True

    async def _approve(self, inter: discord.Interaction):
        cog = inter.client.cogs.get("Academia")
        if cog:
            await cog.approve_application(inter, self.applicant_id, self.level_key)

    async def _reject(self, inter: discord.Interaction):
        cog = inter.client.cogs.get("Academia")
        if cog:
            await cog.reject_application(inter, self.applicant_id, self.level_key)


# ═══════════════════════════════════════════════════════════
# COG
# ═══════════════════════════════════════════════════════════

class Academia(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot     = bot
        self.storage: Storage = bot.storage
        bot.add_view(ManageRolesView())
        self._restore_review_views()

    def _restore_review_views(self):
        for key in self.storage.load_all("academia_pending"):
            try:
                uid, level = key.split(":", 1)
                self.bot.add_view(ReviewView(int(uid), level))
            except Exception:
                pass

    def _cfg(self, gid, key, default=None):
        return self.storage.guild_get(gid, "academia_config", key) or default

    def _set(self, gid, key, value):
        self.storage.guild_set(gid, "academia_config", key, value)

    def _all_role_ids(self, guild_id) -> set:
        ids = set()
        for k in list(LEVEL_LABELS) + ["pending"]:
            rid = self._cfg(guild_id, f"role_{k}")
            if rid:
                ids.add(int(rid.strip('"')))
        return ids

    async def assign_direct_role(self, inter: discord.Interaction, level_key: str):
        guild   = inter.guild
        role_id = self._cfg(guild.id, f"role_{level_key}")
        if not role_id:
            return await inter.followup.send(
                embed=embed_error("Cargo não configurado",
                    f"O cargo para **{LEVEL_LABELS[level_key]}** não foi configurado."),
                ephemeral=True,
            )
        role = guild.get_role(int(role_id.strip('"')))
        if not role:
            return await inter.followup.send(
                embed=embed_error("Cargo não encontrado", "O cargo configurado não existe mais."),
                ephemeral=True,
            )
        to_remove = [r for r in inter.user.roles if r.id in self._all_role_ids(guild.id)]
        if to_remove:
            await inter.user.remove_roles(*to_remove, reason="Atualização de nível acadêmico")
        await inter.user.add_roles(role, reason=f"Nível acadêmico: {LEVEL_LABELS[level_key]}")
        await inter.followup.send(
            embed=embed_success("Cargo atribuído!", f"Você recebeu o cargo {role.mention}."),
            ephemeral=True,
        )

    async def handle_application(self, inter: discord.Interaction, level_key: str, answers: dict):
        # A interação já foi respondida no on_submit — só executa a lógica
        guild = inter.guild

        pending_rid = self._cfg(guild.id, "role_pending")
        if pending_rid:
            pr = guild.get_role(int(pending_rid.strip('"')))
            if pr and pr not in inter.user.roles:
                await inter.user.add_roles(pr, reason="Candidatura acadêmica pendente")

        key = f"{inter.user.id}:{level_key}"
        self.storage.set("academia_pending", key, {
            "guild_id": guild.id,
            "user_id":  inter.user.id,
            "level":    level_key,
            "answers":  answers,
        })

        review_ch_id = self._cfg(guild.id, "review_channel")
        if not review_ch_id:
            return
        review_ch = guild.get_channel(int(review_ch_id.strip('"')))
        if not review_ch:
            return

        emb = discord.Embed(
            title=f"{E['bulb']} Nova Candidatura — {LEVEL_LABELS[level_key]}",
            color=PHILO_COLOR,
        )
        emb.set_author(name=str(inter.user), icon_url=inter.user.display_avatar.url)
        emb.add_field(name="Usuário",          value=f"{inter.user.mention} (`{inter.user.id}`)", inline=False)
        emb.add_field(name="Nível solicitado", value=LEVEL_LABELS[level_key], inline=False)
        emb.add_field(name="Área de pesquisa", value=answers["area"] or "*(não respondido)*",    inline=False)
        emb.add_field(name="Formação",         value=answers["formacao"] or "*(não respondido)*", inline=False)
        emb.add_field(name="Obras recentes",   value=answers["obras"] or "*(não respondido)*",   inline=False)
        emb.set_footer(text=f"ID: {key}")
        view = ReviewView(inter.user.id, level_key)
        self.bot.add_view(view)
        await review_ch.send(embed=emb, view=view)

    async def approve_application(self, inter: discord.Interaction, applicant_id: int, level_key: str):
        await inter.response.defer()
        guild  = inter.guild
        key    = f"{applicant_id}:{level_key}"
        data   = self.storage.get("academia_pending", key)
        if not data:
            return await inter.followup.send(embed=embed_error("Candidatura não encontrada."), ephemeral=True)

        member = guild.get_member(applicant_id)
        if not member:
            return await inter.followup.send(embed=embed_error("Usuário saiu do servidor."), ephemeral=True)

        role_id = self._cfg(guild.id, f"role_{level_key}")
        if not role_id:
            return await inter.followup.send(embed=embed_error("Cargo não configurado."), ephemeral=True)
        role = guild.get_role(int(role_id.strip('"')))
        if not role:
            return await inter.followup.send(embed=embed_error("Cargo não existe mais."), ephemeral=True)

        to_remove = [r for r in member.roles if r.id in self._all_role_ids(guild.id)]
        if to_remove:
            await member.remove_roles(*to_remove, reason="Aprovação acadêmica")
        await member.add_roles(role, reason=f"Aprovado por {inter.user}")
        self.storage.delete("academia_pending", key)



        emb = inter.message.embeds[0]
        emb.color = 0x57F287
        emb.set_footer(text=f"✅ APROVADO por {inter.user} | ID: {applicant_id}")
        view = ReviewView(applicant_id, level_key)
        view._disable()
        await inter.message.edit(embed=emb, view=view)
        await inter.followup.send(
            embed=embed_success("Aprovado!", f"{member.mention} recebeu o cargo {role.mention}."),
            ephemeral=True,
        )

    async def reject_application(self, inter: discord.Interaction, applicant_id: int, level_key: str):
        await inter.response.defer()
        guild  = inter.guild
        key    = f"{applicant_id}:{level_key}"
        data   = self.storage.get("academia_pending", key)
        if not data:
            return await inter.followup.send(embed=embed_error("Candidatura não encontrada."), ephemeral=True)

        member = guild.get_member(applicant_id)
        if member:
            pending_rid = self._cfg(guild.id, "role_pending")
            if pending_rid:
                pr = guild.get_role(int(pending_rid.strip('"')))
                if pr and pr in member.roles:
                    await member.remove_roles(pr, reason="Candidatura rejeitada")


        self.storage.delete("academia_pending", key)
        emb = inter.message.embeds[0]
        emb.color = 0xED4245
        emb.set_footer(text=f"❌ REJEITADO por {inter.user} | ID: {applicant_id}")
        view = ReviewView(applicant_id, level_key)
        view._disable()
        await inter.message.edit(embed=emb, view=view)
        await inter.followup.send(
            embed=embed_success("Rejeitado.", "Candidatura rejeitada e usuário notificado."),
            ephemeral=True,
        )

    # ── Slash commands ─────────────────────────────────────────────────────
    academia_group = app_commands.Group(name="academia", description="Sistema de cargos acadêmicos")

    @academia_group.command(name="setup", description="Configura os cargos do sistema acadêmico")
    @app_commands.describe(
        profissional="Cargo para Profissional", graduacao="Cargo para Graduação+",
        mestrado="Cargo para Mestrado", doutorado="Cargo para Doutorado",
        pos_doutorado="Cargo para Pós-doutorado", pendente="Cargo temporário (aguardando aprovação)",
        canal_revisao="Canal onde as candidaturas serão analisadas",
    )
    @app_commands.default_permissions(administrator=True)
    async def academia_setup(self, inter: discord.Interaction,
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
        await inter.response.send_message(embed=embed_success("Academia configurada!",
            f"1️⃣ Profissional → {profissional.mention}\n"
            f"2️⃣ Graduação+ → {graduacao.mention}\n"
            f"3️⃣ Mestrado → {mestrado.mention}\n"
            f"4️⃣ Doutorado → {doutorado.mention}\n"
            f"5️⃣ Pós-doutorado → {pos_doutorado.mention}\n"
            f"⏳ Pendente → {pendente.mention}\n"
            f"📨 Canal de revisão → {canal_revisao.mention}",
        ), ephemeral=True)

    @academia_group.command(name="painel", description="Envia o botão 'Gerenciar cargos' no canal")
    @app_commands.describe(canal="Canal onde enviar")
    @app_commands.default_permissions(administrator=True)
    async def academia_painel(self, inter: discord.Interaction, canal: discord.TextChannel):
        await canal.send(view=ManageRolesView())
        await inter.response.send_message(
            embed=embed_success("Painel enviado!", f"Botão enviado em {canal.mention}."),
            ephemeral=True,
        )

    @academia_group.command(name="pendentes", description="Lista as candidaturas pendentes")
    @app_commands.default_permissions(manage_guild=True)
    async def academia_pendentes(self, inter: discord.Interaction):
        pending = {k: v for k, v in self.storage.load_all("academia_pending").items()
                   if v.get("guild_id") == inter.guild.id}
        if not pending:
            return await inter.response.send_message(
                embed=embed_info("Sem pendências", "Nenhuma candidatura aguardando análise."),
                ephemeral=True,
            )
        emb = discord.Embed(title=f"{E['loading']} Candidaturas Pendentes", color=PHILO_COLOR)
        for key, data in pending.items():
            member = inter.guild.get_member(data["user_id"])
            emb.add_field(
                name=f"{E['arrow_white']} {member or data['user_id']}",
                value=f"Nível: **{LEVEL_LABELS.get(data['level'], data['level'])}**",
                inline=False,
            )
        await inter.response.send_message(embed=emb, ephemeral=True)

    @academia_group.command(name="remover_cargo", description="Remove cargos acadêmicos de um membro")
    @app_commands.describe(membro="Membro alvo")
    @app_commands.default_permissions(manage_roles=True)
    async def academia_remove(self, inter: discord.Interaction, membro: discord.Member):
        await inter.response.defer(ephemeral=True)
        to_remove = [r for r in membro.roles if r.id in self._all_role_ids(inter.guild.id)]
        if to_remove:
            await membro.remove_roles(*to_remove, reason=f"Remoção por {inter.user}")
        await inter.followup.send(
            embed=embed_success("Cargos removidos!", f"Cargos acadêmicos de {membro.mention} removidos."),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Academia(bot))
