import discord
from discord import app_commands
from discord.ext import commands
import re
import logging
from utils.helpers import embed_success, embed_error, embed_info
from utils.storage import Storage
from utils.emojis import E

log = logging.getLogger("sophosbot.automod")

PHISH_DOMAINS = {
    "discordnitro.gift", "discord-nitro.com", "steamcommunity-trade.com",
    "dlscord.com", "dlscord.gift", "discordapp.io", "discord.vip",
    "free-nitro.ru", "nitro-discord.ru", "discord-gift.co"
}

RULE_TYPES = {
    "palavra":    "Palavra exata",
    "substring":  "Contém texto",
    "regex":      "Expressão regular",
}

ACTIONS = {
    "delete":  "Deletar",
    "warn":    "Avisar",
    "timeout": "Silenciar (10min)",
    "kick":    "Expulsar",
    "ban":     "Banir",
}


class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.storage: Storage = bot.storage

    def _rules(self, guild_id):
        return self.storage.guild_get(guild_id, "automod", "rules") or []

    def _save_rules(self, guild_id, rules):
        self.storage.guild_set(guild_id, "automod", "rules", rules)

    def _exempt_roles(self, guild_id):
        return self.storage.guild_get(guild_id, "automod", "exempt_roles") or []

    def _log_channel(self, guild):
        ch_id = self.storage.guild_get(guild.id, "automod", "log_channel")
        return guild.get_channel(int(ch_id)) if ch_id else None

    def _is_exempt(self, member, guild_id):
        if member.guild_permissions.administrator:
            return True
        return any(str(r.id) in self._exempt_roles(guild_id) for r in member.roles)

    def _check_phish(self, content):
        for domain in PHISH_DOMAINS:
            if domain.lower() in content.lower():
                return True
        for url in re.findall(r'https?://([^\s/]+)', content):
            if any(ph in url.lower() for ph in PHISH_DOMAINS):
                return True
        return False

    def _match_rules(self, content, rules):
        matched = []
        lower = content.lower()
        for rule in rules:
            t, pattern = rule.get("type"), rule.get("pattern", "")
            try:
                if t == "substring" and pattern.lower() in lower:
                    matched.append(rule)
                elif t == "palavra" and re.search(r'\b' + re.escape(pattern.lower()) + r'\b', lower):
                    matched.append(rule)
                elif t == "regex" and re.search(pattern, content, re.IGNORECASE):
                    matched.append(rule)
            except Exception:
                pass
        return matched

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        if self._is_exempt(message.author, message.guild.id):
            return

        content = message.content

        # Phishing — ban imediato
        if self._check_phish(content):
            try:
                await message.delete()
                await message.author.send(f"{E['fire_blue']} Você foi banido por enviar links de phishing.")
                await message.guild.ban(message.author, reason="[AutoMod] Phishing", delete_message_days=1)
                lch = self._log_channel(message.guild)
                if lch:
                    e = discord.Embed(title=f"{E['fire_blue']} Phishing Detectado", color=0xED4245)
                    e.add_field(name=f"{E['arrow_white']} Usuário", value=f"{message.author.mention} (`{message.author.id}`)")
                    e.add_field(name="Canal", value=message.channel.mention)
                    e.add_field(name="Conteúdo", value=content[:300], inline=False)
                    await lch.send(embed=e)
            except Exception as ex:
                log.warning(f"Phishing handler falhou: {ex}")
            return

        matched = self._match_rules(content, self._rules(message.guild.id))
        if not matched:
            return

        for rule in matched:
            action = rule.get("action", "delete")
            reason = f"[AutoMod] Padrão: {rule['pattern']}"
            try:
                if action in ("delete", "warn", "timeout", "kick", "ban"):
                    await message.delete()

                if action == "warn":
                    warns = self.storage.guild_get(message.guild.id, "warns", str(message.author.id)) or []
                    warns.append({"motivo": reason, "moderador": str(self.bot.user.id)})
                    self.storage.guild_set(message.guild.id, "warns", str(message.author.id), warns)
                    try:
                        await message.author.send(f"{E['warning']} Aviso automático em **{message.guild.name}**: {reason}")
                    except Exception:
                        pass
                elif action == "timeout":
                    from datetime import timedelta
                    await message.author.timeout(discord.utils.utcnow() + timedelta(minutes=10), reason=reason)
                elif action == "kick":
                    await message.guild.kick(message.author, reason=reason)
                elif action == "ban":
                    await message.guild.ban(message.author, reason=reason, delete_message_days=1)

                lch = self._log_channel(message.guild)
                if lch:
                    e = discord.Embed(title=f"{E['exclaim']} AutoMod — {ACTIONS.get(action, action)}", color=0xFEE75C)
                    e.add_field(name=f"{E['arrow_white']} Usuário", value=f"{message.author.mention} (`{message.author.id}`)")
                    e.add_field(name="Canal", value=message.channel.mention)
                    e.add_field(name=f"{E['rules']} Padrão", value=f"`{rule['pattern']}`")
                    e.add_field(name="Conteúdo", value=content[:300], inline=False)
                    await lch.send(embed=e)
            except Exception as ex:
                log.warning(f"AutoMod ação '{action}' falhou: {ex}")

    # ─── Slash commands ───────────────────────────────────────────────────────
    automod_group = app_commands.Group(name="automod", description="Gerenciar o AutoMod do servidor")

    @automod_group.command(name="listar", description="Lista todas as regras do AutoMod")
    @app_commands.default_permissions(manage_guild=True)
    async def automod_list(self, inter: discord.Interaction):
        rules = self._rules(inter.guild.id)
        if not rules:
            return await inter.response.send_message(embed=embed_info("Sem regras", "Nenhuma regra configurada."), ephemeral=True)
        e = discord.Embed(title=f"{E['rules']} Regras do AutoMod", color=0xFEE75C)
        for i, rule in enumerate(rules):
            e.add_field(
                name=f"{E['arrow_white']} #{i} — {RULE_TYPES.get(rule['type'], rule['type'])}",
                value=f"{E['dash']} Padrão: `{rule['pattern']}`\n{E['exclaim']} Ação: **{ACTIONS.get(rule['action'], rule['action'])}**",
                inline=False
            )
        await inter.response.send_message(embed=e, ephemeral=True)

    @automod_group.command(name="adicionar", description="Adiciona uma regra ao AutoMod")
    @app_commands.describe(tipo="Tipo de correspondência", padrao="Texto ou regex a detectar", acao="Ação a tomar")
    @app_commands.choices(
        tipo=[
            app_commands.Choice(name="Palavra exata", value="palavra"),
            app_commands.Choice(name="Contém texto", value="substring"),
            app_commands.Choice(name="Regex", value="regex"),
        ],
        acao=[
            app_commands.Choice(name="Deletar mensagem", value="delete"),
            app_commands.Choice(name="Deletar e avisar", value="warn"),
            app_commands.Choice(name="Silenciar 10min", value="timeout"),
            app_commands.Choice(name="Expulsar", value="kick"),
            app_commands.Choice(name="Banir", value="ban"),
        ]
    )
    @app_commands.default_permissions(manage_guild=True)
    async def automod_add(self, inter: discord.Interaction, tipo: str, padrao: str, acao: str):
        if tipo == "regex":
            try:
                re.compile(padrao)
            except re.error as ex:
                return await inter.response.send_message(embed=embed_error("Regex inválido", str(ex)), ephemeral=True)
        rules = self._rules(inter.guild.id)
        rules.append({"type": tipo, "pattern": padrao, "action": acao})
        self._save_rules(inter.guild.id, rules)
        await inter.response.send_message(embed=embed_success("Regra adicionada!", f"{E['rules']} **Tipo:** {RULE_TYPES[tipo]}\n{E['dash']} **Padrão:** `{padrao}`\n{E['exclaim']} **Ação:** {ACTIONS[acao]}"), ephemeral=True)

    @automod_group.command(name="remover", description="Remove uma regra do AutoMod pelo índice")
    @app_commands.describe(indice="Índice (use /automod listar para ver)")
    @app_commands.default_permissions(manage_guild=True)
    async def automod_remove(self, inter: discord.Interaction, indice: int):
        rules = self._rules(inter.guild.id)
        if indice < 0 or indice >= len(rules):
            return await inter.response.send_message(embed=embed_error("Índice inválido", f"Use 0–{len(rules)-1}."), ephemeral=True)
        removed = rules.pop(indice)
        self._save_rules(inter.guild.id, rules)
        await inter.response.send_message(embed=embed_success("Removida!", f"Regra `{removed['pattern']}` removida."), ephemeral=True)

    @automod_group.command(name="isentar_cargo", description="Adiciona um cargo à isenção do AutoMod")
    @app_commands.describe(cargo="Cargo a isentar")
    @app_commands.default_permissions(administrator=True)
    async def automod_exempt_add(self, inter: discord.Interaction, cargo: discord.Role):
        exempt = self._exempt_roles(inter.guild.id)
        if str(cargo.id) not in exempt:
            exempt.append(str(cargo.id))
            self.storage.guild_set(inter.guild.id, "automod", "exempt_roles", exempt)
        await inter.response.send_message(embed=embed_success("Cargo isento!", f"{cargo.mention} está isento do AutoMod."), ephemeral=True)

    @automod_group.command(name="remover_isencao", description="Remove a isenção de um cargo")
    @app_commands.describe(cargo="Cargo")
    @app_commands.default_permissions(administrator=True)
    async def automod_exempt_remove(self, inter: discord.Interaction, cargo: discord.Role):
        exempt = [x for x in self._exempt_roles(inter.guild.id) if x != str(cargo.id)]
        self.storage.guild_set(inter.guild.id, "automod", "exempt_roles", exempt)
        await inter.response.send_message(embed=embed_success("Isenção removida!", f"{cargo.mention} não está mais isento."), ephemeral=True)

    @automod_group.command(name="canal_log", description="Define o canal de logs do AutoMod")
    @app_commands.describe(canal="Canal de logs")
    @app_commands.default_permissions(administrator=True)
    async def automod_log(self, inter: discord.Interaction, canal: discord.TextChannel):
        self.storage.guild_set(inter.guild.id, "automod", "log_channel", str(canal.id))
        await inter.response.send_message(embed=embed_success("Log configurado!", f"Logs do AutoMod em {canal.mention}."), ephemeral=True)

    @automod_group.command(name="phishing_check", description="Verifica se um domínio está na lista de phishing")
    @app_commands.describe(url="URL ou domínio")
    @app_commands.default_permissions(manage_guild=True)
    async def phish_check(self, inter: discord.Interaction, url: str):
        if self._check_phish(url):
            await inter.response.send_message(embed=embed_error("Phishing detectado!", f"`{url}` está na lista negra."), ephemeral=True)
        else:
            await inter.response.send_message(embed=embed_success("Domínio seguro", f"`{url}` não está na lista negra."), ephemeral=True)


async def setup(bot):
    await bot.add_cog(AutoMod(bot))
