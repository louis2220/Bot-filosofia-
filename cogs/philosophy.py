import discord
from discord import app_commands
from discord.ext import commands
import random
import aiohttp
import logging
from utils.helpers import PHILO_COLOR, embed_error, embed_info
from utils.emojis import E

log = logging.getLogger("sophosbot.philosophy")

QUOTES = [
    ("Sócrates", "Só sei que nada sei."),
    ("Platão", "A injustiça resulta em discórdia entre os homens."),
    ("Aristóteles", "A excelência não é um ato, mas um hábito."),
    ("Descartes", "Penso, logo existo."),
    ("Kant", "Age apenas segundo uma máxima tal que possas ao mesmo tempo querer que ela se torne lei universal."),
    ("Nietzsche", "Aquilo que não me mata, me fortalece."),
    ("Schopenhauer", "A vida oscila como um pêndulo entre a dor e o tédio."),
    ("Hegel", "A realidade é racional e o racional é real."),
    ("Marx", "A religião é o ópio do povo."),
    ("Heidegger", "A linguagem é a morada do ser."),
    ("Sartre", "A existência precede a essência."),
    ("Camus", "Há apenas uma questão filosófica verdadeiramente séria, e esta é o suicídio."),
    ("Simone de Beauvoir", "Não se nasce mulher, torna-se."),
    ("Wittgenstein", "Sobre o que não se pode falar, deve-se calar."),
    ("Pascal", "O coração tem razões que a própria razão desconhece."),
    ("Spinoza", "Deus é a causa imanente de todas as coisas."),
    ("Heráclito", "Não se pode banhar no mesmo rio duas vezes."),
    ("Epicuro", "A morte não é nada para nós — quando estamos, ela não está; quando ela está, nós não estamos."),
    ("Marco Aurélio", "Você tem poder sobre sua mente, não sobre eventos externos. Perceba isso, e encontrará força."),
    ("Santo Agostinho", "Nosso coração está inquieto até que encontre repouso em Ti."),
    ("São Tomás de Aquino", "A graça não destrói a natureza, mas a aperfeiçoa."),
    ("Kierkegaard", "A ansiedade é a vertigem da liberdade."),
    ("Hannah Arendt", "O mal banal é praticado por aqueles que simplesmente não pensam."),
    ("Foucault", "Onde há poder, há resistência."),
    ("Ortega y Gasset", "A clareza é a cortesia do filósofo."),
    ("Husserl", "Voltemos às coisas mesmas!"),
    ("Leibniz", "Vivemos no melhor dos mundos possíveis."),
]

THEOLOGIANS = [
    ("Santo Agostinho", "354–430", "Pai da teologia ocidental. *Confissões* e *A Cidade de Deus* são suas obras centrais."),
    ("São Tomás de Aquino", "1225–1274", "Maior teólogo escolástico. *Summa Theologiae* e as *Cinco Vias* para demonstrar a existência de Deus."),
    ("Martinho Lutero", "1483–1546", "Iniciou a Reforma Protestante com as 95 Teses contra as indulgências."),
    ("João Calvino", "1509–1564", "Desenvolveu o calvinismo, enfatizando soberania divina e predestinação."),
    ("Karl Barth", "1886–1968", "Pai da teologia neo-ortodoxa. Escreveu a monumental *Dogmática da Igreja*."),
    ("Paul Tillich", "1886–1965", "Uniu existencialismo e teologia. *Deus como Ser-em-si*."),
    ("Dietrich Bonhoeffer", "1906–1945", "Martirizado pelos nazistas. *Cristo para outros* e *Graça barata vs. graça cara*."),
    ("Hans Urs von Balthasar", "1905–1988", "Trilogia teológica: estética, dramática e lógica."),
    ("Teilhard de Chardin", "1881–1955", "Unificou evolução e teologia no conceito do *Ponto Ômega*."),
    ("Leonardo Boff", "1938–", "Um dos fundadores da Teologia da Libertação latino-americana."),
]

PHILOSOPHERS = [
    ("Sócrates", "469–399 a.C.", "Método da *maiêutica*. Não deixou escritos — tudo veio de Platão."),
    ("Platão", "428–348 a.C.", "Teoria das Ideias. O mundo sensível é sombra do mundo inteligível. Obras: *A República*, *O Banquete*."),
    ("Aristóteles", "384–322 a.C.", "Lógica formal, metafísica, ética das virtudes. Obras: *Ética a Nicômaco*, *Metafísica*."),
    ("Immanuel Kant", "1724–1804", "A razão estrutura a experiência. Imperativo categórico. Obras: *Crítica da Razão Pura*."),
    ("G.W.F. Hegel", "1770–1831", "Dialética do Espírito Absoluto. Obras: *Fenomenologia do Espírito*."),
    ("Friedrich Nietzsche", "1844–1900", "Morte de Deus, Vontade de Poder, Super-Homem. Obras: *Assim Falou Zaratustra*."),
    ("Karl Marx", "1818–1883", "Materialismo histórico, luta de classes. Obras: *O Capital*."),
    ("Martin Heidegger", "1889–1976", "Ontologia fundamental — a questão do ser. Obras: *Ser e Tempo*."),
    ("Jean-Paul Sartre", "1905–1980", "Existencialismo: liberdade radical. Obras: *O Ser e o Nada*."),
    ("Albert Camus", "1913–1960", "Absurdismo: criar sentido diante do silêncio. Obras: *O Mito de Sísifo*."),
    ("Simone de Beauvoir", "1908–1986", "Existencialismo feminista. Obra: *O Segundo Sexo*."),
    ("Ludwig Wittgenstein", "1889–1951", "Tractatus (limites da linguagem) e Investigações (jogos de linguagem)."),
    ("Michel Foucault", "1926–1984", "Arqueologia do saber, genealogia do poder. Obras: *Vigiar e Punir*."),
    ("Baruch Spinoza", "1632–1677", "Panteísmo racional: Deus=Natureza. Obras: *Ética*."),
    ("David Hume", "1711–1776", "Ceticismo empírico. Causalidade é hábito. Obras: *Tratado da Natureza Humana*."),
]

PHILOSOPHICAL_QUESTIONS = [
    f"{E['question']} **Existe livre-arbítrio ou somos determinados?**\nSchopenhauer: queremos o que somos. Kant: a razão nos liberta.",
    f"{E['question']} **O que é a realidade?**\nÉ o que percebemos (idealismo) ou existe independente de nós (realismo)?",
    f"{E['question']} **O problema do mal e a existência de Deus**\nSe Deus é bom e onipotente, por que existe o sofrimento?",
    f"{E['question']} **A vida tem sentido?**\nCamus: o absurdo é a tensão entre nossa busca por sentido e o silêncio do universo.",
    f"{E['question']} **Quem sou eu?**\nHume não encontrou nenhum 'eu' além de feixes de percepções.",
    f"{E['question']} **O que é a justiça?**\nPlatão: harmonia. Rawls: véu da ignorância. Nietzsche: construção do poder.",
    f"{E['question']} **Existe algo além da morte?**\nEpicuro: nada. Platão: alma imortal. Heidegger: ser-para-a-morte revela a autenticidade.",
    f"{E['question']} **A técnica é boa ou má?**\nHeidegger via a técnica moderna como esquecimento do ser.",
]

PARADOXES = [
    ("Paradoxo de Zenão", "Se Aquiles der à tartaruga uma vantagem, nunca a alcançará — há infinitos intervalos intermediários."),
    ("Paradoxo do Mentiroso", "«Esta frase é falsa.» Se verdadeira, é falsa. Se falsa, é verdadeira."),
    ("Barco de Teseu", "Substituindo cada peça, o objeto ainda é o mesmo? Questiona identidade ao longo do tempo."),
    ("Dilema do Bonde", "Desviaria para matar 1 e salvar 5? Utilitarismo vs. deontologia em sua forma mais brutal."),
    ("Paradoxo de Epicuro", "Deus quer prevenir o mal mas não pode? Não é onipotente. Pode mas não quer? Não é bom."),
    ("Quarto Chinês de Searle", "Uma máquina segue regras sem compreender o significado. Pode IA ter mente real?"),
    ("Navalha de Occam", "Não multiplique entidades além do necessário. Princípio de parcimônia da ciência."),
]

SCHOOLS = {
    "estoicismo": {
        "nome": "Estoicismo", "periodo": "~300 a.C. — séc. III d.C.", "fundador": "Zenão de Cítio",
        "ideia": "A virtude é o único bem verdadeiro. Aceita o que não podes controlar.",
        "nomes": "Epicteto, Marco Aurélio, Sêneca",
        "frase": f"{E['fire_white']} *«Não somos perturbados pelas coisas, mas pelas opiniões que temos sobre elas.»* — Epicteto",
    },
    "existencialismo": {
        "nome": "Existencialismo", "periodo": "séc. XIX–XX", "fundador": "Søren Kierkegaard",
        "ideia": "A existência precede a essência — somos lançados no mundo sem natureza prévia.",
        "nomes": "Sartre, Camus, Heidegger, de Beauvoir",
        "frase": f"{E['fire_blue']} *«O homem está condenado a ser livre.»* — Sartre",
    },
    "platonismo": {
        "nome": "Platonismo", "periodo": "séc. IV a.C. em diante", "fundador": "Platão",
        "ideia": "Existe um mundo das Ideias perfeitas do qual o sensível é sombra.",
        "nomes": "Platão, Plotino, Agostinho",
        "frase": f"{E['bulb']} *«A opinião é o irmão bastardo da ciência.»* — Platão",
    },
    "epicurismo": {
        "nome": "Epicurismo", "periodo": "~307 a.C. em diante", "fundador": "Epicuro",
        "ideia": "O fim da filosofia é a *ataraxia* e a *aponia*. Prazer moderado como base da boa vida.",
        "nomes": "Epicuro, Lucrécio",
        "frase": f"{E['star']} *«O maior fruto da sabedoria é a amizade.»* — Epicuro",
    },
    "kantianismo": {
        "nome": "Kantianismo", "periodo": "séc. XVIII–XIX", "fundador": "Immanuel Kant",
        "ideia": "A razão estrutura a experiência. Age de modo que tua máxima possa ser lei universal.",
        "nomes": "Kant, Fichte, Schelling",
        "frase": f"{E['verified']} *«O céu estrelado acima de mim e a lei moral dentro de mim.»* — Kant",
    },
    "marxismo": {
        "nome": "Marxismo", "periodo": "séc. XIX–XX", "fundador": "Karl Marx",
        "ideia": "A história é movida pela luta de classes. O capitalismo aliena o trabalhador.",
        "nomes": "Marx, Engels, Gramsci, Althusser",
        "frase": f"{E['arrow_white']} *«Os filósofos interpretaram o mundo; o que importa é transformá-lo.»* — Marx",
    },
    "fenomenologia": {
        "nome": "Fenomenologia", "periodo": "séc. XX", "fundador": "Edmund Husserl",
        "ideia": "Filosofia deve partir das coisas como aparecem à consciência, sem pressupostos.",
        "nomes": "Husserl, Heidegger, Merleau-Ponty, Sartre",
        "frase": f"{E['question']} *«Voltemos às coisas mesmas!»* — Husserl",
    },
}

CONCEITOS = {
    "maiêutica": ("Maiêutica", "Arte socrática de 'dar à luz' ideias por meio do diálogo questionador.", "Sócrates"),
    "epoché":    ("Epoché", "Suspensão do julgamento. Em Husserl, 'colocar o mundo entre parênteses'.", "Pirro / Husserl"),
    "dasein":    ("Dasein", "Heidegger: 'ser-aí'. O ente que interroga o próprio ser, sempre 'jogado' num mundo histórico.", "Heidegger"),
    "phronesis": ("Phrónesis", "Prudência prática aristotélica. Saber agir bem no momento e contexto certos.", "Aristóteles"),
    "kenose":    ("Kênose", "Esvaziamento de Cristo ao se tornar humano (Fil 2:7). Central na teologia de Balthasar.", "Teologia Cristã"),
    "catarse":   ("Catarse", "Purificação das emoções que a tragédia provoca. Em Freud, liberação terapêutica.", "Aristóteles / Freud"),
    "logos":     ("Lógos", "Razão, palavra. Em Heráclito: princípio ordenador do cosmos. Em João 1:1: o Cristo preexistente.", "Heráclito / João"),
    "aporia":    ("Aporia", "Impasse filosófico. Diálogos platônicos terminam em aporia para estimular reflexão.", "Platão"),
    "alienacao": ("Alienação", "O trabalhador torna-se estranho ao produto de seu trabalho sob o capitalismo.", "Marx / Hegel"),
    "niilismo":  ("Niilismo", "Negação de qualquer valor ou sentido. Nietzsche o diagnosticou e propôs a transvaloração dos valores.", "Nietzsche"),
    "soterologia": ("Soteriologia", "Estudo teológico da salvação: como ocorre, quem pode ser salvo, papel de Cristo.", "Teologia"),
    "escatologia": ("Escatologia", "Estudo das 'últimas coisas': morte, juízo, fim dos tempos.", "Teologia / Filosofia"),
    "hermeneutica": ("Hermenêutica", "Arte da interpretação. Compreender é sempre interpretar dentro de um horizonte histórico.", "Gadamer / Ricoeur"),
    "teleologia": ("Teleologia", "Explicação pelas causas finais. Aristóteles via fins em toda a natureza.", "Aristóteles"),
}


class Philosophy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="citacao", description="Exibe uma citação filosófica aleatória ou por autor")
    @app_commands.describe(autor="Filósofo (opcional)")
    async def citacao(self, inter: discord.Interaction, autor: str = None):
        pool = [(a, q) for a, q in QUOTES if autor.lower() in a.lower()] if autor else QUOTES
        if not pool:
            return await inter.response.send_message(embed=embed_error("Não encontrado", f"Sem citações de '{autor}'."), ephemeral=True)
        a, q = random.choice(pool)
        e = discord.Embed(description=f"*«{q}»*", color=PHILO_COLOR)
        e.set_author(name=f"{E['fire_white']} {a}")
        e.set_footer(text="SophosBot • Filosofia")
        await inter.response.send_message(embed=e)

    @app_commands.command(name="filosofo", description="Informações sobre um filósofo")
    @app_commands.describe(nome="Nome do filósofo")
    async def filosofo(self, inter: discord.Interaction, nome: str):
        matches = [(n, p, d) for n, p, d in PHILOSOPHERS if nome.lower() in n.lower()]
        if not matches:
            return await inter.response.send_message(embed=embed_error("Não encontrado",
                "Tente: Platão, Aristóteles, Kant, Nietzsche, Sartre, Camus, Heidegger, Marx, Wittgenstein, Foucault..."), ephemeral=True)
        n, p, d = matches[0]
        e = discord.Embed(title=f"{E['bulb']} {n}", description=d, color=PHILO_COLOR)
        e.add_field(name=f"{E['dash']} Período", value=p)
        e.set_footer(text="SophosBot • /filosofo")
        await inter.response.send_message(embed=e)

    @app_commands.command(name="teologo", description="Informações sobre um teólogo")
    @app_commands.describe(nome="Nome do teólogo")
    async def teologo(self, inter: discord.Interaction, nome: str):
        matches = [(n, p, d) for n, p, d in THEOLOGIANS if nome.lower() in n.lower()]
        if not matches:
            return await inter.response.send_message(embed=embed_error("Não encontrado",
                "Tente: Agostinho, Aquino, Lutero, Calvino, Barth, Tillich, Bonhoeffer, Balthasar, Chardin, Boff..."), ephemeral=True)
        n, p, d = matches[0]
        e = discord.Embed(title=f"{E['star']} {n}", description=d, color=0xF39C12)
        e.add_field(name=f"{E['dash']} Período", value=p)
        e.set_footer(text="SophosBot • /teologo")
        await inter.response.send_message(embed=e)

    @app_commands.command(name="escola", description="Explica uma corrente filosófica")
    @app_commands.choices(nome=[
        app_commands.Choice(name="Estoicismo",    value="estoicismo"),
        app_commands.Choice(name="Existencialismo", value="existencialismo"),
        app_commands.Choice(name="Platonismo",    value="platonismo"),
        app_commands.Choice(name="Epicurismo",    value="epicurismo"),
        app_commands.Choice(name="Kantianismo",   value="kantianismo"),
        app_commands.Choice(name="Marxismo",      value="marxismo"),
        app_commands.Choice(name="Fenomenologia", value="fenomenologia"),
    ])
    async def escola(self, inter: discord.Interaction, nome: str):
        s = SCHOOLS.get(nome)
        if not s:
            return await inter.response.send_message(embed=embed_error("Não encontrado"), ephemeral=True)
        e = discord.Embed(title=f"{E['fire_blue']} {s['nome']}", color=PHILO_COLOR)
        e.add_field(name=f"{E['dash']} Período",        value=s["periodo"],  inline=True)
        e.add_field(name=f"{E['pin']} Fundador",         value=s["fundador"], inline=True)
        e.add_field(name=f"{E['bulb']} Ideia Central",   value=s["ideia"],    inline=False)
        e.add_field(name=f"{E['arrow_white']} Nomes",    value=s["nomes"],    inline=False)
        e.add_field(name=f"{E['star']} Frase Marcante",  value=s["frase"],    inline=False)
        e.set_footer(text="SophosBot • /escola")
        await inter.response.send_message(embed=e)

    @app_commands.command(name="questao", description="Propõe uma grande questão filosófica para debate")
    async def questao(self, inter: discord.Interaction):
        q = random.choice(PHILOSOPHICAL_QUESTIONS)
        e = discord.Embed(title=f"{E['question']} Questão Filosófica", description=q, color=PHILO_COLOR)
        e.set_footer(text="SophosBot • Debate — /questao")
        await inter.response.send_message(embed=e)

    @app_commands.command(name="paradoxo", description="Apresenta um paradoxo clássico")
    async def paradoxo(self, inter: discord.Interaction):
        nome, desc = random.choice(PARADOXES)
        e = discord.Embed(title=f"{E['circle']} {nome}", description=desc, color=PHILO_COLOR)
        e.set_footer(text="SophosBot • Paradoxos — /paradoxo")
        await inter.response.send_message(embed=e)

    @app_commands.command(name="dilema", description="Apresenta um dilema ético clássico")
    async def dilema(self, inter: discord.Interaction):
        dilemas = [
            ("O Bonde (Trolley Problem)", f"Um bonde descontrolado vai matar 5 pessoas. Você pode desviá-lo, mas matará 1.\n\n{E['arrow_white']} **Utilitarismo:** Desvia.\n{E['rules']} **Deontologia:** Não instrumentalizes uma vida."),
            ("O Véu da Ignorância", f"Antes de nascer, você não sabe quem será. Que sociedade escolheria?\n\n{E['bulb']} **Rawls:** Aquela que maximize as condições do pior situado."),
            ("A Caverna de Platão", f"Prisioneiros veem sombras e creem ser a realidade. Um liberto vê o sol — ao retornar, ninguém acredita nele.\n\n{E['question']} Somos nós os prisioneiros?"),
            ("O Demônio de Descartes", f"Um gênio maligno pode nos enganar sobre TUDO. Como saber que o mundo é real?\n\n{E['verified']} **Descartes:** *Cogito, ergo sum* — ao duvidar, provo que existo."),
        ]
        nome, desc = random.choice(dilemas)
        e = discord.Embed(title=f"{E['warning']} Dilema: {nome}", description=desc, color=PHILO_COLOR)
        e.set_footer(text="SophosBot • Dilemas — /dilema")
        await inter.response.send_message(embed=e)

    @app_commands.command(name="conceito", description="Explica um conceito filosófico ou teológico")
    @app_commands.describe(termo="Ex: maiêutica, epoché, dasein, niilismo, kênose...")
    async def conceito(self, inter: discord.Interaction, termo: str):
        key_norm = termo.lower().replace("ê","e").replace("ô","o").replace("ã","a").replace("ç","c").replace("é","e").replace("ó","o")
        match = None
        for k, v in CONCEITOS.items():
            if k in key_norm or key_norm in k:
                match = v
                break
        if not match:
            return await inter.response.send_message(embed=embed_error("Conceito não encontrado",
                "Tente: maiêutica, epoché, dasein, phronesis, kênose, catarse, logos, aporia, alienação, niilismo, soteriologia, escatologia, hermenêutica, teleologia..."), ephemeral=True)
        nome_c, desc_c, ref_c = match
        e = discord.Embed(title=f"{E['bulb']} {nome_c}", description=desc_c, color=PHILO_COLOR)
        e.add_field(name=f"{E['pin']} Referência", value=ref_c)
        e.set_footer(text="SophosBot • Conceitos — /conceito")
        await inter.response.send_message(embed=e)

    @app_commands.command(name="debater", description="Cria uma embed de debate filosófico no canal")
    @app_commands.describe(tema="Tema do debate")
    @app_commands.default_permissions(manage_messages=True)
    async def debater(self, inter: discord.Interaction, tema: str):
        e = discord.Embed(
            title=f"{E['fire_blue']} Debate Filosófico: {tema}",
            description=(
                f"O tema em questão é: **{tema}**\n\n"
                f"{E['arrow_white']} Apresente seus argumentos com rigor e respeito.\n"
                f"{E['rules']} Referências a autores e obras são bem-vindas.\n\n"
                f"*«O filósofo não é aquele que vence o debate, mas aquele que ilumina a questão.»*"
            ),
            color=PHILO_COLOR
        )
        e.set_footer(text=f"Debate proposto por {inter.user} • SophosBot")
        await inter.channel.send(embed=e)
        await inter.response.send_message(embed=discord.Embed(description=f"{E['verified']} Debate criado!", color=0x57F287), ephemeral=True)

    @app_commands.command(name="buscar", description="Busca um filósofo/teólogo/obra na Wikipedia PT")
    @app_commands.describe(termo="Termo de pesquisa")
    async def buscar(self, inter: discord.Interaction, termo: str):
        await inter.response.defer()
        url = f"https://pt.wikipedia.org/api/rest_v1/page/summary/{termo.replace(' ', '_')}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status != 200:
                        return await inter.followup.send(embed=embed_error("Não encontrado", f"Nada para '{termo}' na Wikipedia."))
                    data = await resp.json()
                    extract   = data.get("extract", "Sem resumo.")[:1024]
                    page_url  = data.get("content_urls", {}).get("desktop", {}).get("page", "")
                    thumbnail = data.get("thumbnail", {}).get("source", "")
                    e = discord.Embed(title=f"{E['bulb']} {data.get('title', termo)}", description=extract, url=page_url, color=PHILO_COLOR)
                    if thumbnail:
                        e.set_thumbnail(url=thumbnail)
                    e.set_footer(text="Fonte: Wikipedia PT • SophosBot")
                    await inter.followup.send(embed=e)
        except Exception as ex:
            await inter.followup.send(embed=embed_error("Erro de conexão", str(ex)))

    @app_commands.command(name="sophos", description="Sobre o SophosBot")
    async def sophos(self, inter: discord.Interaction):
        e = discord.Embed(
            title=f"{E['fire_blue']} SophosBot — Filosofia & Teologia",
            description=(
                f"**Sophos** (σοφός) = *sábio*.\n\n"
                f"{E['arrow_blue']} **Filosofia**\n"
                f"`/citacao` · `/filosofo` · `/teologo` · `/escola` · `/questao` · `/paradoxo` · `/dilema` · `/conceito` · `/debater` · `/buscar`\n\n"
                f"{E['fire_white']} **Moderação**\n"
                f"`/ban` · `/kick` · `/timeout` · `/warn` · `/purge` · `/lock` · `/unlock`\n\n"
                f"{E['mail']} **Tickets**\n"
                f"`/ticket setup` · `/ticket painel` · `/ticket editpainel`\n\n"
                f"{E['trophy']} **Academia**\n"
                f"`/academia setup` · `/academia painel`\n\n"
                f"{E['rules']} **AutoMod**\n"
                f"`/automod adicionar` · `/automod listar`\n\n"
                f"*«Conhece-te a ti mesmo.» — Delfos*"
            ),
            color=PHILO_COLOR
        )
        e.set_footer(text="SophosBot • Filosofia, Teologia & Moderação")
        await inter.response.send_message(embed=e)


async def setup(bot):
    await bot.add_cog(Philosophy(bot))
