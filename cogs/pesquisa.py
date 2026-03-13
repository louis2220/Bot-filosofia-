"""
cogs/pesquisa.py
Pesquisa acadêmica em fontes filosóficas:
  - Stanford Encyclopedia of Philosophy (SEP)
  - PhilPapers
  - Open Library / Internet Archive
  - Wikipedia PT/EN
  - PhilArchive (artigos em acesso aberto)
"""

import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import asyncio
import urllib.parse
import logging
import re
from utils.helpers import PHILO_COLOR, embed_error, embed_info
from utils.emojis import E

log = logging.getLogger("filosofia.pesquisa")

# ── Constantes de URL ─────────────────────────────────────────────────────────
SEP_API        = "https://plato.stanford.edu/cgi-bin/encyclopedia/archinfo.cgi"
SEP_BASE       = "https://plato.stanford.edu/entries/"
PHILPAPERS_API = "https://philpapers.org/s/"
PHILARCHIVE    = "https://philarchive.org/rec/"
OPENLIBRARY    = "https://openlibrary.org/search.json"
WIKI_PT        = "https://pt.wikipedia.org/api/rest_v1/page/summary/"
WIKI_EN        = "https://en.wikipedia.org/api/rest_v1/page/summary/"
CROSSREF       = "https://api.crossref.org/works"


pesquisa_group = app_commands.Group(
    name="pesquisa",
    description="Pesquisa acadêmica em fontes filosóficas",
)


class Pesquisa(commands.Cog):
    """Pesquisa em bases de dados filosóficas e acadêmicas."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._session: aiohttp.ClientSession | None = None

    async def cog_load(self):
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=12),
            headers={"User-Agent": "FilosofiaBot/2.0 (Discord; academic research)"},
        )

    async def cog_unload(self):
        if self._session:
            await self._session.close()

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=12),
                headers={"User-Agent": "FilosofiaBot/2.0 (Discord; academic research)"},
            )
        return self._session

    # ─────────────────────────────────────────────────────────────────────────
    # /pesquisa sep — Stanford Encyclopedia of Philosophy
    # ─────────────────────────────────────────────────────────────────────────
    @pesquisa_group.command(
        name="sep",
        description="Busca um verbete na Stanford Encyclopedia of Philosophy (SEP)"
    )
    @app_commands.describe(termo="Termo em inglês (ex: free-will, kant, consciousness)")
    async def pesquisa_sep(self, inter: discord.Interaction, termo: str):
        await inter.response.defer()

        # Converte espaços em hífens (padrão SEP)
        slug = re.sub(r"[^a-z0-9]+", "-", termo.lower().strip()).strip("-")
        url  = f"{SEP_BASE}{slug}/"

        # Tenta buscar o head da página para verificar existência
        try:
            async with self.session.head(url, allow_redirects=True) as resp:
                exists = resp.status == 200
        except Exception:
            exists = False

        if not exists:
            # Fallback: busca via DuckDuckGo API pública
            search_url = f"https://api.duckduckgo.com/?q=site:plato.stanford.edu+{urllib.parse.quote(termo)}&format=json&no_redirect=1"
            try:
                async with self.session.get(search_url) as resp:
                    data = await resp.json(content_type=None)
                    related = data.get("RelatedTopics", [])
                    suggestions = [
                        t["FirstURL"].split("/entries/")[-1].strip("/")
                        for t in related[:5]
                        if "plato.stanford.edu/entries/" in t.get("FirstURL", "")
                    ]
            except Exception:
                suggestions = []

            emb = embed_error(
                "Verbete não encontrado",
                f"O verbete **`{slug}`** não foi localizado na SEP.\n\n"
                + (
                    f"{E['arrow_white']} **Sugestões:**\n" +
                    "\n".join(f"• [`{s}`]({SEP_BASE}{s})" for s in suggestions[:5])
                    if suggestions else
                    f"{E['bulb']} Consulte diretamente: https://plato.stanford.edu"
                )
            )
            return await inter.followup.send(embed=emb)

        emb = discord.Embed(
            title=f"{E['bulb']} SEP — {termo.title()}",
            url=url,
            color=PHILO_COLOR,
        )
        emb.description = (
            f"{E['arrow_white']} Verbete encontrado na **Stanford Encyclopedia of Philosophy**.\n\n"
            f"{E['dash']} A SEP é a maior enciclopédia de filosofia acadêmica do mundo, "
            f"com artigos escritos e revisados por especialistas.\n\n"
            f"{E['fire_blue']} [Abrir verbete completo]({url})"
        )
        emb.add_field(
            name=f"{E['pin']} Slug",
            value=f"`{slug}`",
            inline=True,
        )
        emb.add_field(
            name=f"{E['rules']} Fonte",
            value="Stanford Encyclopedia of Philosophy",
            inline=True,
        )
        emb.set_footer(text="Filosofia Bot • SEP — plato.stanford.edu")
        await inter.followup.send(embed=emb)

    # ─────────────────────────────────────────────────────────────────────────
    # /pesquisa philpapers — PhilPapers
    # ─────────────────────────────────────────────────────────────────────────
    @pesquisa_group.command(
        name="philpapers",
        description="Busca artigos e papers na base PhilPapers"
    )
    @app_commands.describe(
        termo="Termo de busca em inglês",
        max_resultados="Número de resultados (1-5, padrão 3)"
    )
    async def pesquisa_philpapers(
        self,
        inter: discord.Interaction,
        termo: str,
        max_resultados: app_commands.Range[int, 1, 5] = 3,
    ):
        await inter.response.defer()

        q = urllib.parse.quote_plus(termo)
        # PhilPapers tem API JSON não-oficial via query string
        api_url = f"https://philpapers.org/s/{q}?format=json&limit={max_resultados}"

        try:
            async with self.session.get(api_url) as resp:
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}")
                raw = await resp.text()
                # PhilPapers pode retornar HTML em vez de JSON
                if raw.strip().startswith("<"):
                    raise ValueError("HTML response — fallback")
                import json
                results = json.loads(raw)
        except Exception:
            # Fallback: link direto para busca
            search_link = f"https://philpapers.org/s/{q}"
            emb = embed_info(
                "PhilPapers — Busca",
                f"{E['arrow_blue']} A API da PhilPapers não retornou resultados JSON diretos.\n\n"
                f"{E['fire_blue']} [Clique aqui para ver resultados na PhilPapers]({search_link})\n\n"
                f"{E['bulb']} A PhilPapers indexa mais de **3 milhões** de artigos e livros de filosofia."
            )
            emb.set_footer(text="Filosofia Bot • PhilPapers")
            return await inter.followup.send(embed=emb)

        if not results:
            return await inter.followup.send(
                embed=embed_error("Sem resultados", f"Nenhum resultado para **{termo}** no PhilPapers.")
            )

        emb = discord.Embed(
            title=f"{E['bulb']} PhilPapers — {termo}",
            color=PHILO_COLOR,
            url=f"https://philpapers.org/s/{q}",
        )
        emb.set_footer(text=f"Filosofia Bot • PhilPapers · {max_resultados} resultado(s)")

        for item in results[:max_resultados]:
            title   = item.get("title", "Sem título")
            authors = ", ".join(a.get("name", "") for a in item.get("authors", []))
            year    = item.get("year", "")
            pub     = item.get("publication", {}).get("name", "")
            url_r   = item.get("url", "")
            abstract = (item.get("abstract", "") or "")[:200]
            if abstract:
                abstract = abstract + "..."

            value = ""
            if authors:
                value += f"{E['pin']} **Autor(es):** {authors}\n"
            if year:
                value += f"{E['dash']} **Ano:** {year}\n"
            if pub:
                value += f"{E['rules']} **Publicação:** {pub}\n"
            if abstract:
                value += f"\n*{abstract}*\n"
            if url_r:
                value += f"\n{E['arrow_blue']} [Ver artigo]({url_r})"

            emb.add_field(name=f"{E['fire_blue']} {title[:100]}", value=value or "—", inline=False)

        await inter.followup.send(embed=emb)

    # ─────────────────────────────────────────────────────────────────────────
    # /pesquisa livro — Open Library
    # ─────────────────────────────────────────────────────────────────────────
    @pesquisa_group.command(
        name="livro",
        description="Busca obras filosóficas na Open Library / Internet Archive"
    )
    @app_commands.describe(
        titulo="Título ou palavras-chave",
        autor="Filtrar por autor (opcional)"
    )
    async def pesquisa_livro(
        self,
        inter: discord.Interaction,
        titulo: str,
        autor: str = "",
    ):
        await inter.response.defer()

        params: dict = {
            "q": titulo + (f" author:{autor}" if autor else ""),
            "fields": "title,author_name,first_publish_year,isbn,key,language,subject",
            "limit": 5,
            "sort": "editions",
        }

        try:
            async with self.session.get(OPENLIBRARY, params=params) as resp:
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}")
                data = await resp.json()
        except Exception as ex:
            return await inter.followup.send(
                embed=embed_error("Erro na busca", f"Não foi possível consultar a Open Library.\n`{ex}`")
            )

        docs = data.get("docs", [])
        if not docs:
            return await inter.followup.send(
                embed=embed_error("Sem resultados", f"Nenhuma obra encontrada para **{titulo}**.")
            )

        emb = discord.Embed(
            title=f"{E['bulb']} Open Library — {titulo}",
            color=PHILO_COLOR,
            url=f"https://openlibrary.org/search?q={urllib.parse.quote_plus(titulo)}",
        )
        emb.set_footer(text=f"Filosofia Bot • Open Library · {data.get('numFound', '?')} resultado(s) totais")

        for doc in docs[:5]:
            t        = doc.get("title", "Sem título")
            authors  = doc.get("author_name", [])
            year     = doc.get("first_publish_year", "")
            key      = doc.get("key", "")
            langs    = doc.get("language", [])
            subjects = doc.get("subject", [])[:3]

            ol_url = f"https://openlibrary.org{key}" if key else ""

            value = ""
            if authors:
                value += f"{E['pin']} {', '.join(authors[:3])}\n"
            if year:
                value += f"{E['dash']} **Ano:** {year}\n"
            if langs:
                value += f"{E['rules']} **Idioma(s):** {', '.join(langs[:3])}\n"
            if subjects:
                value += f"{E['question']} **Temas:** {', '.join(subjects)}\n"
            if ol_url:
                value += f"\n{E['arrow_blue']} [Ver na Open Library]({ol_url})"

            emb.add_field(name=f"{E['fire_white']} {t[:80]}", value=value or "—", inline=False)

        await inter.followup.send(embed=emb)

    # ─────────────────────────────────────────────────────────────────────────
    # /pesquisa wikipedia — Wikipedia PT/EN
    # ─────────────────────────────────────────────────────────────────────────
    @pesquisa_group.command(
        name="wikipedia",
        description="Busca um verbete na Wikipedia (Português ou Inglês)"
    )
    @app_commands.describe(
        termo="Termo de pesquisa",
        idioma="Idioma da Wikipedia"
    )
    @app_commands.choices(idioma=[
        app_commands.Choice(name="Português", value="pt"),
        app_commands.Choice(name="English",   value="en"),
    ])
    async def pesquisa_wikipedia(
        self,
        inter: discord.Interaction,
        termo: str,
        idioma: str = "pt",
    ):
        await inter.response.defer()

        base = WIKI_PT if idioma == "pt" else WIKI_EN
        slug = urllib.parse.quote(termo.replace(" ", "_"))
        url  = f"{base}{slug}"

        try:
            async with self.session.get(url) as resp:
                if resp.status == 404:
                    return await inter.followup.send(
                        embed=embed_error(
                            "Não encontrado",
                            f"**{termo}** não foi localizado na Wikipedia {'PT' if idioma == 'pt' else 'EN'}.\n"
                            f"{E['bulb']} Tente `/pesquisa sep` para verbetes filosóficos aprofundados."
                        )
                    )
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}")
                data = await resp.json()
        except Exception as ex:
            return await inter.followup.send(
                embed=embed_error("Erro de conexão", str(ex))
            )

        extract   = (data.get("extract") or "Sem resumo disponível.")[:1200]
        page_url  = data.get("content_urls", {}).get("desktop", {}).get("page", "")
        thumbnail = data.get("thumbnail", {}).get("source", "")
        title_wp  = data.get("title", termo)
        desc_short = data.get("description", "")

        emb = discord.Embed(
            title=f"{E['bulb']} {title_wp}",
            description=extract + ("..." if len(data.get("extract", "")) > 1200 else ""),
            url=page_url,
            color=PHILO_COLOR,
        )
        if desc_short:
            emb.add_field(name=f"{E['dash']} Descrição rápida", value=desc_short, inline=False)
        if thumbnail:
            emb.set_thumbnail(url=thumbnail)
        emb.set_footer(
            text=f"Filosofia Bot • Wikipedia {'PT' if idioma == 'pt' else 'EN'} — "
                 "Fonte não especializada; use SEP para artigos acadêmicos."
        )
        await inter.followup.send(embed=emb)

    # ─────────────────────────────────────────────────────────────────────────
    # /pesquisa doi — Busca por DOI via CrossRef
    # ─────────────────────────────────────────────────────────────────────────
    @pesquisa_group.command(
        name="doi",
        description="Busca os metadados de um artigo pelo DOI (CrossRef)"
    )
    @app_commands.describe(doi="DOI do artigo (ex: 10.1093/mind/fzv015)")
    async def pesquisa_doi(self, inter: discord.Interaction, doi: str):
        await inter.response.defer()

        # Normaliza: remove URL prefixo se copiado da web
        doi_clean = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip())
        url = f"{CROSSREF}/{urllib.parse.quote(doi_clean)}"

        try:
            async with self.session.get(url) as resp:
                if resp.status == 404:
                    return await inter.followup.send(
                        embed=embed_error("DOI não encontrado", f"`{doi_clean}` não foi localizado no CrossRef.")
                    )
                if resp.status != 200:
                    raise ValueError(f"HTTP {resp.status}")
                data = (await resp.json()).get("message", {})
        except Exception as ex:
            return await inter.followup.send(
                embed=embed_error("Erro na consulta", str(ex))
            )

        title      = " — ".join(data.get("title", ["Sem título"]))
        authors    = data.get("author", [])
        author_str = ", ".join(
            f"{a.get('given', '')} {a.get('family', '')}".strip()
            for a in authors[:5]
        )
        journal    = " — ".join(data.get("container-title", [""]))
        year_parts = data.get("published", {}).get("date-parts", [[""]])
        year       = str(year_parts[0][0]) if year_parts and year_parts[0] else "?"
        volume     = data.get("volume", "")
        issue      = data.get("issue", "")
        pages      = data.get("page", "")
        abstract   = (data.get("abstract") or "")
        # Remove tags XML do abstract (CrossRef usa JATS)
        abstract   = re.sub(r"<[^>]+>", "", abstract)[:600]
        doi_url    = f"https://doi.org/{doi_clean}"

        emb = discord.Embed(
            title=f"{E['bulb']} {title[:200]}",
            url=doi_url,
            color=PHILO_COLOR,
        )
        if author_str:
            emb.add_field(name=f"{E['pin']} Autor(es)", value=author_str, inline=False)
        if journal:
            emb.add_field(name=f"{E['rules']} Periódico", value=journal, inline=True)
        emb.add_field(name=f"{E['dash']} Ano", value=year, inline=True)
        if volume or issue:
            emb.add_field(name="Vol./Nº", value=f"{volume}/{issue}".strip("/"), inline=True)
        if pages:
            emb.add_field(name="Páginas", value=pages, inline=True)
        if abstract:
            emb.add_field(name=f"{E['question']} Resumo", value=abstract + "...", inline=False)
        emb.add_field(name=f"{E['arrow_blue']} DOI", value=f"[{doi_clean}]({doi_url})", inline=False)
        emb.set_footer(text="Filosofia Bot • CrossRef — dados de metadados acadêmicos")

        await inter.followup.send(embed=emb)

    # ─────────────────────────────────────────────────────────────────────────
    # /pesquisa autor — Busca obras de um autor no Open Library
    # ─────────────────────────────────────────────────────────────────────────
    @pesquisa_group.command(
        name="autor",
        description="Lista obras de um filósofo/autor na Open Library"
    )
    @app_commands.describe(nome="Nome do filósofo ou autor")
    async def pesquisa_autor(self, inter: discord.Interaction, nome: str):
        await inter.response.defer()

        params = {
            "q": f"author:{nome}",
            "fields": "title,first_publish_year,key,subject",
            "limit": 8,
            "sort": "new",
        }

        try:
            async with self.session.get(OPENLIBRARY, params=params) as resp:
                data = await resp.json()
        except Exception as ex:
            return await inter.followup.send(
                embed=embed_error("Erro na busca", str(ex))
            )

        docs = data.get("docs", [])
        total = data.get("numFound", 0)

        if not docs:
            return await inter.followup.send(
                embed=embed_error("Autor não encontrado", f"Nenhuma obra encontrada para **{nome}**.")
            )

        emb = discord.Embed(
            title=f"{E['fire_blue']} Obras de {nome}",
            description=f"{E['dash']} **{total}** obra(s) indexada(s) na Open Library",
            color=PHILO_COLOR,
            url=f"https://openlibrary.org/search?author={urllib.parse.quote_plus(nome)}",
        )
        emb.set_footer(text="Filosofia Bot • Open Library")

        for doc in docs[:8]:
            t    = doc.get("title", "Sem título")
            year = doc.get("first_publish_year", "?")
            key  = doc.get("key", "")
            url_o = f"https://openlibrary.org{key}" if key else ""
            emb.add_field(
                name=f"{E['arrow_white']} {t[:60]}",
                value=f"{E['dash']} {year}" + (f"\n{E['arrow_blue']} [Open Library]({url_o})" if url_o else ""),
                inline=True,
            )

        await inter.followup.send(embed=emb)

    # ─────────────────────────────────────────────────────────────────────────
    # /pesquisa fontes — Lista as fontes disponíveis
    # ─────────────────────────────────────────────────────────────────────────
    @pesquisa_group.command(
        name="fontes",
        description="Exibe todas as bases de dados acadêmicas disponíveis"
    )
    async def pesquisa_fontes(self, inter: discord.Interaction):
        emb = discord.Embed(
            title=f"{E['trophy']} Bases de Dados Acadêmicas",
            description=(
                f"{E['arrow_blue']} O bot pesquisa nas seguintes fontes especializadas:\n\u200b"
            ),
            color=PHILO_COLOR,
        )
        fontes = [
            (
                f"{E['fire_blue']} Stanford Encyclopedia of Philosophy",
                "A maior e mais rigorosa enciclopédia de filosofia acadêmica.\n"
                "Verbetes escritos por especialistas, revisados por pares.\n"
                f"[plato.stanford.edu](https://plato.stanford.edu) · `/pesquisa sep`",
            ),
            (
                f"{E['bulb']} PhilPapers",
                "Index com mais de 3 milhões de artigos e livros de filosofia.\n"
                "Cobertura completa de periódicos filosóficos internacionais.\n"
                f"[philpapers.org](https://philpapers.org) · `/pesquisa philpapers`",
            ),
            (
                f"{E['star']} Open Library / Internet Archive",
                "Acervo digital com milhões de livros, incluindo obras clássicas em acesso livre.\n"
                f"[openlibrary.org](https://openlibrary.org) · `/pesquisa livro` · `/pesquisa autor`",
            ),
            (
                f"{E['verified']} CrossRef (DOI)",
                "Metadados de artigos científicos via DOI.\n"
                "Acesso a informações de periódicos, autores e resumos.\n"
                f"[crossref.org](https://crossref.org) · `/pesquisa doi`",
            ),
            (
                f"{E['question']} Wikipedia",
                "Enciclopédia colaborativa em Português e Inglês.\n"
                "Recomendada para consulta inicial; prefira SEP para rigor acadêmico.\n"
                f"[wikipedia.org](https://wikipedia.org) · `/pesquisa wikipedia`",
            ),
        ]
        for name, val in fontes:
            emb.add_field(name=name, value=val, inline=False)
        emb.set_footer(text="Filosofia Bot • Pesquisa Acadêmica")
        await inter.response.send_message(embed=emb)


async def setup(bot: commands.Bot):
    cog = Pesquisa(bot)
    bot.tree.add_command(pesquisa_group)
    await bot.add_cog(cog)
