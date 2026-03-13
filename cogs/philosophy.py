"""
cogs/philosophy.py
Conteúdo filosófico: citações, filósofos, escolas, correntes, conceitos, dilemas, paradoxos.
Teologia removida conforme solicitado.
"""

import discord
from discord import app_commands
from discord.ext import commands
import random
import logging
from utils.helpers import PHILO_COLOR, embed_error, embed_info
from utils.emojis import E

log = logging.getLogger("filosofia.philosophy")

# ── Citações ──────────────────────────────────────────────────────────────────
QUOTES: list[tuple[str, str]] = [
    ("Sócrates",           "Só sei que nada sei."),
    ("Platão",             "A injustiça resulta em discórdia entre os homens."),
    ("Aristóteles",        "A excelência não é um ato, mas um hábito."),
    ("Descartes",          "Penso, logo existo."),
    ("Kant",               "Age apenas segundo uma máxima tal que possas ao mesmo tempo querer que ela se torne lei universal."),
    ("Nietzsche",          "Aquilo que não me mata, me fortalece."),
    ("Schopenhauer",       "A vida oscila como um pêndulo entre a dor e o tédio."),
    ("Hegel",              "A realidade é racional e o racional é real."),
    ("Marx",               "Os filósofos interpretaram o mundo de diferentes maneiras; o que importa é transformá-lo."),
    ("Heidegger",          "A linguagem é a morada do ser."),
    ("Sartre",             "A existência precede a essência."),
    ("Camus",              "Há apenas uma questão filosófica verdadeiramente séria, e esta é o suicídio."),
    ("Simone de Beauvoir", "Não se nasce mulher, torna-se."),
    ("Wittgenstein",       "Sobre o que não se pode falar, deve-se calar."),
    ("Pascal",             "O coração tem razões que a própria razão desconhece."),
    ("Spinoza",            "Deus é a causa imanente de todas as coisas."),
    ("Heráclito",          "Não se pode banhar no mesmo rio duas vezes."),
    ("Epicuro",            "A morte não é nada para nós — quando estamos, ela não está; quando ela está, nós não estamos."),
    ("Marco Aurélio",      "Você tem poder sobre sua mente, não sobre eventos externos. Perceba isso, e encontrará força."),
    ("Kierkegaard",        "A ansiedade é a vertigem da liberdade."),
    ("Hannah Arendt",      "O mal banal é praticado por aqueles que simplesmente não pensam."),
    ("Foucault",           "Onde há poder, há resistência."),
    ("Husserl",            "Voltemos às coisas mesmas!"),
    ("Leibniz",            "Vivemos no melhor dos mundos possíveis."),
    ("Platão",             "A opinião é o irmão bastardo da ciência."),
    ("Aristóteles",        "O homem é, por natureza, um animal político."),
    ("Rawls",              "As desigualdades só são justificáveis quando beneficiam os menos favorecidos."),
    ("Adorno",             "Escrever poesia após Auschwitz é um ato bárbaro."),
    ("Deleuze",            "A filosofia é a arte de formar, de inventar, de fabricar conceitos."),
    ("Habermas",           "A racionalidade comunicativa é a base da emancipação humana."),
    ("Merleau-Ponty",      "A consciência é originalmente não um 'eu penso que', mas um 'eu posso'."),
    ("Schopenhauer",       "O talento acerta um alvo que ninguém mais pode atingir; o gênio atinge um alvo que ninguém mais pode ver."),
    ("Nietzsche",          "Sem música, a vida seria um erro."),
    ("Russell",            "O problema da humanidade é que os estúpidos estão cheios de certezas, e os inteligentes, de dúvidas."),
    ("Seneca",             "Não é porque as coisas são difíceis que não ousamos; é porque não ousamos que são difíceis."),
]

# ── Filósofos ─────────────────────────────────────────────────────────────────
PHILOSOPHERS: list[tuple[str, str, str]] = [
    ("Sócrates",           "469–399 a.C.", f"Método da *maiêutica*: o diálogo como parturição da verdade. Não deixou escritos — tudo chegou por meio de Platão. Condenado à morte por impiedade e corrupção da juventude ateniense.\n{E['arrow_blue']} SEP: [`socrates`](https://plato.stanford.edu/entries/socrates/)"),
    ("Platão",             "428–348 a.C.", f"Teoria das Ideias: o mundo sensível é sombra do mundo inteligível. Fundou a Academia. Obras: *A República*, *O Banquete*, *Fédon*, *Mênon*.\n{E['arrow_blue']} SEP: [`plato`](https://plato.stanford.edu/entries/plato/)"),
    ("Aristóteles",        "384–322 a.C.", f"Lógica formal, metafísica, ética das virtudes, biologia. Preceptor de Alexandre. Obras: *Ética a Nicômaco*, *Metafísica*, *Política*, *Organon*.\n{E['arrow_blue']} SEP: [`aristotle`](https://plato.stanford.edu/entries/aristotle/)"),
    ("Immanuel Kant",      "1724–1804",   f"Revolução copernicana na filosofia: a razão estrutura a experiência. Imperativo categórico, críticas ao conhecimento, moral e juízo. Obras: *Crítica da Razão Pura*, *Fundamentação da Metafísica dos Costumes*.\n{E['arrow_blue']} SEP: [`kant`](https://plato.stanford.edu/entries/kant/)"),
    ("G.W.F. Hegel",       "1770–1831",   f"Dialética do Espírito Absoluto: tese–antítese–síntese. A história como automovimento da razão. Obras: *Fenomenologia do Espírito*, *Ciência da Lógica*.\n{E['arrow_blue']} SEP: [`hegel`](https://plato.stanford.edu/entries/hegel/)"),
    ("Friedrich Nietzsche","1844–1900",   f"Morte de Deus, Vontade de Poder, Eterno Retorno, Super-Homem, Transvaloração dos Valores. Obras: *Assim Falou Zaratustra*, *Além do Bem e do Mal*, *Genealogia da Moral*.\n{E['arrow_blue']} SEP: [`nietzsche`](https://plato.stanford.edu/entries/nietzsche/)"),
    ("Karl Marx",          "1818–1883",   f"Materialismo histórico e dialético, luta de classes, mais-valia, alienação. Com Engels: *Manifesto Comunista*. Obras: *O Capital*, *Manuscritos Econômico-Filosóficos*.\n{E['arrow_blue']} SEP: [`marx`](https://plato.stanford.edu/entries/marx/)"),
    ("Martin Heidegger",   "1889–1976",   f"Ontologia fundamental: a questão do ser. Dasein, ser-no-mundo, autenticidade. Crítica à técnica moderna. Obras: *Ser e Tempo*, *A Origem da Obra de Arte*.\n{E['arrow_blue']} SEP: [`heidegger`](https://plato.stanford.edu/entries/heidegger/)"),
    ("Jean-Paul Sartre",   "1905–1980",   f"Existencialismo ateu: a existência precede a essência. Liberdade radical e responsabilidade. Obras: *O Ser e o Nada*, *O Existencialismo é um Humanismo*.\n{E['arrow_blue']} SEP: [`sartre`](https://plato.stanford.edu/entries/sartre/)"),
    ("Albert Camus",       "1913–1960",   f"Absurdismo: criar sentido diante do silêncio do universo. Revolta como resposta ao absurdo. Obras: *O Mito de Sísifo*, *O Homem Revoltado*.\n{E['arrow_blue']} SEP: [`camus`](https://plato.stanford.edu/entries/camus/)"),
    ("Simone de Beauvoir", "1908–1986",   f"Existencialismo feminista. Gênero como construção histórica. Obras: *O Segundo Sexo*, *A Ética da Ambiguidade*.\n{E['arrow_blue']} SEP: [`beauvoir`](https://plato.stanford.edu/entries/beauvoir/)"),
    ("Ludwig Wittgenstein","1889–1951",   f"*Tractatus*: os limites da linguagem são os limites do mundo. *Investigações*: significado como uso, jogos de linguagem. Dois períodos radicalmente distintos.\n{E['arrow_blue']} SEP: [`wittgenstein`](https://plato.stanford.edu/entries/wittgenstein/)"),
    ("Michel Foucault",    "1926–1984",   f"Arqueologia do saber, genealogia do poder, biopoder. A verdade como produção histórica de práticas discursivas. Obras: *As Palavras e as Coisas*, *Vigiar e Punir*.\n{E['arrow_blue']} SEP: [`foucault`](https://plato.stanford.edu/entries/foucault/)"),
    ("Baruch Spinoza",     "1632–1677",   f"Panteísmo racional: Deus = Natureza (*Deus sive Natura*). Monismo de substância, imanência, liberdade como compreensão das causas. Obras: *Ética*, *Tratado Teológico-Político*.\n{E['arrow_blue']} SEP: [`spinoza`](https://plato.stanford.edu/entries/spinoza/)"),
    ("David Hume",         "1711–1776",   f"Empirismo cético. Causalidade como hábito mental, não necessidade racional. Crítica à metafísica e à teologia natural. Obras: *Tratado da Natureza Humana*, *Investigação sobre o Entendimento Humano*.\n{E['arrow_blue']} SEP: [`hume`](https://plato.stanford.edu/entries/hume/)"),
    ("Hannah Arendt",      "1906–1975",   f"Condição humana, política, totalitarismo, banalidade do mal. Distinção entre labor, trabalho e ação. Obras: *As Origens do Totalitarismo*, *A Condição Humana*.\n{E['arrow_blue']} SEP: [`arendt`](https://plato.stanford.edu/entries/arendt/)"),
    ("John Rawls",         "1921–2002",   f"Teoria da justiça como equidade. Véu da ignorância, princípios de justiça. Obras: *Uma Teoria da Justiça*, *Liberalismo Político*.\n{E['arrow_blue']} SEP: [`rawls`](https://plato.stanford.edu/entries/rawls/)"),
    ("Edmund Husserl",     "1859–1938",   f"Fundador da fenomenologia. Intencionalidade da consciência, redução fenomenológica, epoché. Obras: *Investigações Lógicas*, *Ideias para uma Fenomenologia Pura*.\n{E['arrow_blue']} SEP: [`husserl`](https://plato.stanford.edu/entries/husserl/)"),
]

# ── Escolas filosóficas ───────────────────────────────────────────────────────
SCHOOLS: dict[str, dict] = {
    "estoicismo": {
        "nome": "Estoicismo", "periodo": "~300 a.C. — séc. III d.C.", "fundador": "Zenão de Cítio",
        "ideia": "A virtude é o único bem verdadeiro. Aceite o que não pode controlar; controle o que está ao seu alcance — os julgamentos e impulsos.",
        "nomes": "Zenão, Cleantes, Crisipo, Epicteto, Marco Aurélio, Sêneca",
        "frase": f"*«Não somos perturbados pelas coisas, mas pelas opiniões que temos sobre elas.»* — Epicteto",
        "sep": "https://plato.stanford.edu/entries/stoicism/",
    },
    "existencialismo": {
        "nome": "Existencialismo", "periodo": "séc. XIX–XX", "fundador": "Søren Kierkegaard",
        "ideia": "A existência precede a essência: somos lançados no mundo sem natureza prévia e nos construímos pela liberdade radical.",
        "nomes": "Kierkegaard, Sartre, Camus, Heidegger, Simone de Beauvoir, Merleau-Ponty",
        "frase": f"*«O homem está condenado a ser livre.»* — Sartre",
        "sep": "https://plato.stanford.edu/entries/existentialism/",
    },
    "platonismo": {
        "nome": "Platonismo", "periodo": "séc. IV a.C. em diante", "fundador": "Platão",
        "ideia": "Existe um mundo de Ideias/Formas perfeitas e eternas, do qual o mundo sensível é apenas sombra imperfeita.",
        "nomes": "Platão, Plotino, Jâmblico, Proclo, Agostinho",
        "frase": f"*«A opinião é o irmão bastardo da ciência.»* — Platão",
        "sep": "https://plato.stanford.edu/entries/platonism/",
    },
    "epicurismo": {
        "nome": "Epicurismo", "periodo": "~307 a.C. em diante", "fundador": "Epicuro",
        "ideia": "O fim da filosofia é a *ataraxia* (tranquilidade da alma) e a *aponia* (ausência de dor). O prazer moderado como base da boa vida.",
        "nomes": "Epicuro, Metrodoro, Lucrécio",
        "frase": f"*«O maior fruto da sabedoria é a amizade.»* — Epicuro",
        "sep": "https://plato.stanford.edu/entries/epicurus/",
    },
    "kantianismo": {
        "nome": "Kantianismo", "periodo": "séc. XVIII–XIX", "fundador": "Immanuel Kant",
        "ideia": "A razão pura estrutura a experiência possível. A moral é autônoma: o imperativo categórico obriga por si mesmo, sem fundamento externo.",
        "nomes": "Kant, Fichte, Schelling, Hegel (herdeiros críticos)",
        "frase": f"*«O céu estrelado acima de mim e a lei moral dentro de mim.»* — Kant",
        "sep": "https://plato.stanford.edu/entries/kant/",
    },
    "marxismo": {
        "nome": "Marxismo", "periodo": "séc. XIX–XX", "fundador": "Karl Marx",
        "ideia": "A história é movida pela luta de classes e pelas relações de produção. O capitalismo aliena o trabalhador do produto de seu trabalho.",
        "nomes": "Marx, Engels, Gramsci, Althusser, Lukács, Walter Benjamin",
        "frase": f"*«Os filósofos apenas interpretaram o mundo; o que importa é transformá-lo.»* — Marx",
        "sep": "https://plato.stanford.edu/entries/marx/",
    },
    "fenomenologia": {
        "nome": "Fenomenologia", "periodo": "séc. XX", "fundador": "Edmund Husserl",
        "ideia": "A filosofia deve partir das coisas como aparecem à consciência, sem pressupostos naturalistas. A intencionalidade é a estrutura fundamental da mente.",
        "nomes": "Husserl, Heidegger, Merleau-Ponty, Sartre, Levinas",
        "frase": f"*«Voltemos às coisas mesmas!»* — Husserl",
        "sep": "https://plato.stanford.edu/entries/phenomenology/",
    },
    "pragmatismo": {
        "nome": "Pragmatismo", "periodo": "séc. XIX–XX", "fundador": "Charles Sanders Peirce",
        "ideia": "O significado de um conceito reside em suas consequências práticas. A verdade é o que funciona — o que resiste ao teste da experiência.",
        "nomes": "Peirce, William James, John Dewey, Richard Rorty",
        "frase": f"*«A verdade é o que é bom na linha da crença.»* — William James",
        "sep": "https://plato.stanford.edu/entries/pragmatism/",
    },
    "analitica": {
        "nome": "Filosofia Analítica", "periodo": "séc. XX–XXI", "fundador": "Gottlob Frege / Bertrand Russell",
        "ideia": "Rigor lógico-linguístico na análise filosófica. Os problemas filosóficos são frequentemente confusões linguísticas a serem dissolvidas.",
        "nomes": "Frege, Russell, Moore, Wittgenstein, Quine, Kripke, Parfit",
        "frase": f"*«A essência da filosofia é a análise lógica da linguagem.»* — Russell",
        "sep": "https://plato.stanford.edu/entries/analysis/",
    },
    "frankfurt": {
        "nome": "Escola de Frankfurt (Teoria Crítica)", "periodo": "séc. XX–XXI", "fundador": "Max Horkheimer",
        "ideia": "Crítica imanente à razão instrumental e à sociedade capitalista. A teoria deve ser crítica, reflexiva e orientada para a emancipação.",
        "nomes": "Horkheimer, Adorno, Marcuse, Benjamin, Habermas, Honneth",
        "frase": f"*«O todo é o falso.»* — Adorno",
        "sep": "https://plato.stanford.edu/entries/critical-theory/",
    },
}

# ── Conceitos ─────────────────────────────────────────────────────────────────
CONCEITOS: dict[str, tuple[str, str, str, str]] = {
    "maieutica":     ("Maiêutica",      "Arte socrática de 'dar à luz' ideias por meio do diálogo questionador. O filósofo como parteiro do pensamento.", "Sócrates", "https://plato.stanford.edu/entries/socratic-method/"),
    "epoche":        ("Epoché",         "Suspensão do julgamento. Em Husserl: 'colocar o mundo entre parênteses' para analisar a experiência pura.", "Pirro / Husserl", "https://plato.stanford.edu/entries/phenomenology/"),
    "dasein":        ("Dasein",         "Heidegger: 'ser-aí'. O ente que interroga o próprio ser, sempre 'jogado' num mundo histórico e finito.", "Heidegger", "https://plato.stanford.edu/entries/heidegger/"),
    "phronesis":     ("Phrónesis",      "Prudência prática aristotélica. Saber agir bem no momento e contexto certos, diferente do conhecimento teórico (episteme).", "Aristóteles", "https://plato.stanford.edu/entries/aristotle-ethics/"),
    "catarse":       ("Catarse",        "Purificação das emoções provocada pela tragédia. Em Freud: liberação terapêutica de conteúdos reprimidos.", "Aristóteles / Freud", ""),
    "logos":         ("Lógos",          "Razão, palavra, discurso. Em Heráclito: princípio ordenador do cosmos. Em Platão: razão universal. Na teologia cristã: o Cristo preexistente (Jo 1:1).", "Heráclito / Platão", ""),
    "aporia":        ("Aporia",         "Impasse filosófico, beco sem saída argumentativo. Os diálogos platônicos terminam em aporia para estimular a continuação da busca.", "Platão", ""),
    "alienacao":     ("Alienação",      "O trabalhador torna-se estranho ao produto de seu trabalho sob o capitalismo. Em Hegel: o Espírito que se exterioriza e se reencontra.", "Marx / Hegel", "https://plato.stanford.edu/entries/alienation/"),
    "niilismo":      ("Niilismo",       "Negação de qualquer valor ou sentido objetivo. Nietzsche o diagnosticou como a crise do Ocidente após a 'morte de Deus' e propôs a transvaloração.", "Nietzsche", "https://plato.stanford.edu/entries/nihilism/"),
    "hermeneutica":  ("Hermenêutica",   "Arte e teoria da interpretação. Compreender é sempre interpretar dentro de um horizonte histórico — a 'fusão de horizontes' de Gadamer.", "Gadamer / Ricoeur", "https://plato.stanford.edu/entries/hermeneutics/"),
    "teleologia":    ("Teleologia",     "Explicação pelas causas finais (o *telos*). Aristóteles via fins em toda a natureza. Kant questiona se podemos conhecer fins na natureza.", "Aristóteles / Kant", "https://plato.stanford.edu/entries/teleology-biology/"),
    "dialética":     ("Dialética",      "Em Platão: método de investigação pelo diálogo. Em Hegel: movimento tese–antítese–síntese do Espírito. Em Marx: materialismo dialético.", "Platão / Hegel / Marx", ""),
    "imperativo":    ("Imperativo Categórico", "Princípio moral kantiano: 'Age apenas segundo uma máxima tal que possas querer que ela se torne lei universal'. Obriga incondicionalmente.", "Kant", "https://plato.stanford.edu/entries/kant-moral/"),
    "intencionalidade": ("Intencionalidade", "Propriedade da consciência de sempre ser *sobre* algo — a consciência é sempre consciência *de* alguma coisa. Estrutura fundamental da mente.", "Brentano / Husserl", "https://plato.stanford.edu/entries/intentionality/"),
    "ontologia":     ("Ontologia",      "Estudo do ser enquanto ser. O que existe? Quais são as categorias fundamentais da realidade? Ramo central da metafísica.", "Aristóteles / Heidegger", "https://plato.stanford.edu/entries/metaphysics/"),
    "epistemologia": ("Epistemologia",  "Teoria do conhecimento. O que podemos conhecer? Como? Com que certeza? Inclui debates sobre justificação, verdade e ceticismo.", "Múltiplos", "https://plato.stanford.edu/entries/epistemology/"),
    "utilitarismo":  ("Utilitarismo",   "A ação moralmente correta é a que maximiza a utilidade (felicidade/prazer) para o maior número. Cálculo felicífico.", "Bentham / Mill / Singer", "https://plato.stanford.edu/entries/utilitarianism-history/"),
    "ceticismo":     ("Ceticismo",      "Postura de suspensão do julgamento sobre afirmações de conhecimento. Pyrro: *ataraxia* pela epoché. Hume: ceticismo moderado.", "Pirro / Descartes / Hume", "https://plato.stanford.edu/entries/skepticism/"),
}

# ── Paradoxos ─────────────────────────────────────────────────────────────────
PARADOXES: list[tuple[str, str]] = [
    ("Paradoxo de Zenão", "Se Aquiles der à tartaruga uma vantagem, nunca a alcançará — há infinitos intervalos intermediários a percorrer. Questiona a divisibilidade do espaço e do tempo."),
    ("Paradoxo do Mentiroso", "«Esta frase é falsa.» — Se verdadeira, é falsa. Se falsa, é verdadeira. Ameaça à consistência lógica das linguagens autorreferenciais."),
    ("Barco de Teseu",    "Substituindo cada peça gradualmente, o objeto ainda é o mesmo? Questiona identidade numérica ao longo do tempo e a essência dos compostos."),
    ("Dilema do Bonde",   "Um bonde descontrolado vai matar 5 pessoas. Você pode desviá-lo, matando 1. Utilitarismo vs. deontologia em sua forma mais brutal."),
    ("Paradoxo de Epicuro", "Deus quer prevenir o mal mas não pode? Não é onipotente. Pode mas não quer? Não é bom. Pode e quer? De onde vem o mal? Não existe? Então por que chamá-lo Deus?"),
    ("Quarto Chinês de Searle", "Uma máquina segue regras sintáticas sem compreender semântica. Pode a IA ter genuína compreensão ou apenas simular?"),
    ("Navalha de Occam",  "Não multiplique entidades além do necessário — entre explicações equivalentes, prefira a mais simples. Princípio de parcimônia da ciência."),
    ("Problema do Mal",   "Se Deus é onipotente, onisciente e sumamente bom, por que existe o sofrimento inocente? Leibniz: melhor dos mundos. Hick: teodiceia da alma."),
    ("Paradoxo da Tolerância", "Uma sociedade que tolera tudo se torna incapaz de se defender de movimentos intolerantes. Popper: a tolerância deve ser intolerante com a intolerância."),
    ("Paradoxo da Análise", "Analisar 'X é X' é trivialmente verdadeiro mas não informativo; analisar com conteúdo novo pode ser falso. Como a análise filosófica é possível?"),
]

# ── Questões filosóficas ──────────────────────────────────────────────────────
PHILOSOPHICAL_QUESTIONS: list[str] = [
    f"{E['question']} **Existe livre-arbítrio ou somos determinados?**\nSchopenhauer: queremos o que somos. Kant: a razão nos liberta. Compatibilistas: liberdade e determinismo coexistem.",
    f"{E['question']} **O que é a realidade?**\nÉ o que percebemos (*idealismo*) ou existe independente de nós (*realismo*)? Berkeley: *esse est percipi*.",
    f"{E['question']} **A vida tem sentido?**\nCamus: o absurdo é a tensão entre nossa busca por sentido e o silêncio do universo. Criar sentido é o ato de rebeldia.",
    f"{E['question']} **Quem sou eu?**\nHume não encontrou nenhum 'eu' além de feixes de percepções. Locke: a identidade pessoal é memória. Parfit: somos menos do que pensamos.",
    f"{E['question']} **O que é a justiça?**\nPlatão: harmonia das partes. Rawls: véu da ignorância. Nietzsche: construção do poder. Marx: emancipação das classes.",
    f"{E['question']} **Existe algo além da morte?**\nEpicuro: nada. Platão: alma imortal. Heidegger: ser-para-a-morte revela a autenticidade. Parfit: nossa identidade já se dissolve agora.",
    f"{E['question']} **A técnica é boa ou má?**\nHeidegger: a técnica moderna é um modo de revelar o ser como recurso (*Gestell*) que obscurece outras formas de revelação.",
    f"{E['question']} **Podemos conhecer as coisas em si mesmas?**\nKant: só acessamos fenômenos, nunca o nômeno. Hegel: o em-si se torna para-nós no processo histórico.",
    f"{E['question']} **A moral é objetiva ou relativa?**\nMoore: bom é indefinível mas real (intuicionismo). Mackie: não há fatos morais (erro). Railton: naturalismo moral.",
    f"{E['question']} **O que é o tempo?**\nAgostinho: o tempo é no espírito. Kant: forma a priori da intuição. Heidegger: o ser é essencialmente temporal. McTaggart: o tempo é irreal.",
]


class Philosophy(commands.Cog):
    """Conteúdo filosófico: citações, filósofos, escolas, conceitos, dilemas e debates."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /citacao ──────────────────────────────────────────────────────────────
    @app_commands.command(name="citacao", description="Exibe uma citação filosófica aleatória ou filtra por filósofo")
    @app_commands.describe(autor="Nome do filósofo (opcional — deixe vazio para aleatório)")
    async def citacao(self, inter: discord.Interaction, autor: str = ""):
        pool = [(a, q) for a, q in QUOTES if autor.lower() in a.lower()] if autor else list(QUOTES)
        if not pool:
            return await inter.response.send_message(
                embed=embed_error("Autor não encontrado", f"Não há citações registradas de **{autor}**."),
                ephemeral=True,
            )
        a, q = random.choice(pool)
        emb = discord.Embed(description=f"*«{q}»*", color=PHILO_COLOR)
        emb.set_author(name=f"{E['fire_white']} {a}")
        emb.set_footer(text="Filosofia Bot • /citacao")
        await inter.response.send_message(embed=emb)

    # ── /filosofo ─────────────────────────────────────────────────────────────
    @app_commands.command(name="filosofo", description="Informações sobre um filósofo")
    @app_commands.describe(nome="Nome do filósofo")
    async def filosofo(self, inter: discord.Interaction, nome: str):
        matches = [(n, p, d) for n, p, d in PHILOSOPHERS if nome.lower() in n.lower()]
        if not matches:
            return await inter.response.send_message(
                embed=embed_error(
                    "Filósofo não encontrado",
                    f"Tente: Sócrates, Platão, Aristóteles, Kant, Hegel, Nietzsche, Marx, Heidegger, "
                    f"Sartre, Camus, Beauvoir, Wittgenstein, Foucault, Spinoza, Hume, Arendt, Rawls, Husserl..."
                ),
                ephemeral=True,
            )
        n, p, d = matches[0]
        emb = discord.Embed(title=f"{E['bulb']} {n}", description=d, color=PHILO_COLOR)
        emb.add_field(name=f"{E['dash']} Período", value=p, inline=True)
        emb.set_footer(text="Filosofia Bot • /filosofo · Use /pesquisa sep para aprofundar")
        await inter.response.send_message(embed=emb)

    # ── /escola ───────────────────────────────────────────────────────────────
    @app_commands.command(name="escola", description="Explica uma corrente ou escola filosófica")
    @app_commands.choices(nome=[
        app_commands.Choice(name="Estoicismo",               value="estoicismo"),
        app_commands.Choice(name="Existencialismo",          value="existencialismo"),
        app_commands.Choice(name="Platonismo",               value="platonismo"),
        app_commands.Choice(name="Epicurismo",               value="epicurismo"),
        app_commands.Choice(name="Kantianismo",              value="kantianismo"),
        app_commands.Choice(name="Marxismo",                 value="marxismo"),
        app_commands.Choice(name="Fenomenologia",            value="fenomenologia"),
        app_commands.Choice(name="Pragmatismo",              value="pragmatismo"),
        app_commands.Choice(name="Filosofia Analítica",      value="analitica"),
        app_commands.Choice(name="Escola de Frankfurt",      value="frankfurt"),
    ])
    async def escola(self, inter: discord.Interaction, nome: str):
        s = SCHOOLS.get(nome)
        if not s:
            return await inter.response.send_message(embed=embed_error("Não encontrado"), ephemeral=True)
        emb = discord.Embed(title=f"{E['fire_blue']} {s['nome']}", color=PHILO_COLOR)
        emb.add_field(name=f"{E['dash']} Período",           value=s["periodo"],   inline=True)
        emb.add_field(name=f"{E['pin']} Fundador",           value=s["fundador"],  inline=True)
        emb.add_field(name=f"{E['bulb']} Ideia Central",     value=s["ideia"],     inline=False)
        emb.add_field(name=f"{E['arrow_white']} Principais Nomes", value=s["nomes"], inline=False)
        emb.add_field(name=f"{E['fire_white']} Frase Marcante",    value=f"*{s['frase']}*", inline=False)
        if s.get("sep"):
            emb.add_field(name=f"{E['arrow_blue']} SEP", value=f"[Ver verbete completo]({s['sep']})", inline=False)
        emb.set_footer(text="Filosofia Bot • /escola")
        await inter.response.send_message(embed=emb)

    # ── /conceito ─────────────────────────────────────────────────────────────
    @app_commands.command(name="conceito", description="Explica um conceito filosófico")
    @app_commands.describe(termo="Ex: maiêutica, epoché, dasein, niilismo, dialética, imperativo...")
    async def conceito(self, inter: discord.Interaction, termo: str):
        def normalize(s: str) -> str:
            return (s.lower()
                    .replace("ê","e").replace("ô","o").replace("ã","a")
                    .replace("ç","c").replace("é","e").replace("ó","o")
                    .replace("á","a").replace("í","i").replace("ú","u")
                    .replace(" ",""))

        norm = normalize(termo)
        match = None
        for k, v in CONCEITOS.items():
            if k in norm or norm in k or normalize(v[0]) in norm or norm in normalize(v[0]):
                match = v
                break

        if not match:
            return await inter.response.send_message(
                embed=embed_error(
                    "Conceito não encontrado",
                    f"Tente: maiêutica, epoché, dasein, phronesis, catarse, logos, aporia, alienação, "
                    f"niilismo, hermenêutica, teleologia, dialética, imperativo, intencionalidade, "
                    f"ontologia, epistemologia, utilitarismo, ceticismo..."
                ),
                ephemeral=True,
            )

        nome_c, desc_c, ref_c, sep_c = match
        emb = discord.Embed(title=f"{E['bulb']} {nome_c}", description=desc_c, color=PHILO_COLOR)
        emb.add_field(name=f"{E['pin']} Referência principal", value=ref_c, inline=True)
        if sep_c:
            emb.add_field(name=f"{E['arrow_blue']} SEP", value=f"[Ver verbete]({sep_c})", inline=True)
        emb.set_footer(text="Filosofia Bot • /conceito")
        await inter.response.send_message(embed=emb)

    # ── /questao ──────────────────────────────────────────────────────────────
    @app_commands.command(name="questao", description="Propõe uma grande questão filosófica para debate")
    async def questao(self, inter: discord.Interaction):
        q = random.choice(PHILOSOPHICAL_QUESTIONS)
        emb = discord.Embed(title=f"{E['question']} Questão para Debate", description=q, color=PHILO_COLOR)
        emb.set_footer(text="Filosofia Bot • /questao — Apresente seus argumentos!")
        await inter.response.send_message(embed=emb)

    # ── /paradoxo ─────────────────────────────────────────────────────────────
    @app_commands.command(name="paradoxo", description="Apresenta um paradoxo clássico da filosofia")
    async def paradoxo(self, inter: discord.Interaction):
        nome, desc = random.choice(PARADOXES)
        emb = discord.Embed(title=f"{E['circle']} {nome}", description=desc, color=PHILO_COLOR)
        emb.set_footer(text="Filosofia Bot • /paradoxo")
        await inter.response.send_message(embed=emb)

    # ── /dilema ───────────────────────────────────────────────────────────────
    @app_commands.command(name="dilema", description="Apresenta um dilema ético ou filosófico clássico")
    async def dilema(self, inter: discord.Interaction):
        dilemas = [
            (
                "O Bonde (Trolley Problem)",
                f"Um bonde descontrolado vai matar 5 pessoas. Você pode puxar uma alavanca e desviá-lo, matando 1.\n\n"
                f"{E['arrow_white']} **Utilitarismo (Mill/Bentham):** Desvie — o bem maior para o maior número.\n"
                f"{E['rules']} **Deontologia (Kant):** Não instrumentalize uma vida como meio para fins, mesmo nobres.\n"
                f"{E['question']} **Variante:** E se for você que tem que empurrar um homem gordo para parar o bonde?",
            ),
            (
                "O Véu da Ignorância (Rawls)",
                f"Antes de nascer, você não sabe quem será na sociedade — rico ou pobre, capaz ou deficiente, maioria ou minoria.\n\n"
                f"{E['bulb']} **Rawls:** Escolheríamos uma sociedade que maximize as condições do *pior situado* — pois podemos ser nós.\n"
                f"{E['arrow_white']} **Libertários (Nozick):** O véu ignora talentos e escolhas — a justiça é procedural, não distributiva.",
            ),
            (
                "A Caverna de Platão",
                f"Prisioneiros acorrentados veem apenas sombras na parede e creem ser a realidade. Um liberto sobe, vê o sol — ao retornar, ninguém acredita nele.\n\n"
                f"{E['question']} Somos nós os prisioneiros da *doxa* (opinião)?\n"
                f"{E['bulb']} O filósofo-rei deve governar mesmo contra sua vontade, pois conhece o Bem.",
            ),
            (
                "O Gênio Maligno de Descartes",
                f"Um gênio maligno onipotente pode nos enganar sobre *tudo* — sentidos, matemática, memória.\n\n"
                f"{E['verified']} **Descartes:** *Cogito, ergo sum* — ao duvidar, provo que existo, pois o ato de duvidar é um ato de pensar.\n"
                f"{E['question']} Versão contemporânea: e se estivermos num simulador? (Bostrom, 2003)",
            ),
            (
                "Libertarianismo vs. Igualitarismo",
                f"Nozick: se cada transação individual é justa, qualquer distribuição resultante é justa — redistribuição é coercitiva.\n\n"
                f"{E['arrow_white']} **Rawls:** Talentos são arbitrariedades da natureza; ninguém merece suas vantagens naturais.\n"
                f"{E['rules']} Como conciliar liberdade individual com equidade social?",
            ),
        ]
        nome, desc = random.choice(dilemas)
        emb = discord.Embed(title=f"{E['warning']} Dilema: {nome}", description=desc, color=PHILO_COLOR)
        emb.set_footer(text="Filosofia Bot • /dilema")
        await inter.response.send_message(embed=emb)

    # ── /debater ──────────────────────────────────────────────────────────────
    @app_commands.command(name="debater", description="Cria uma sessão de debate filosófico no canal")
    @app_commands.describe(tema="Tema do debate")
    @app_commands.default_permissions(manage_messages=True)
    async def debater(self, inter: discord.Interaction, tema: str):
        emb = discord.Embed(
            title=f"{E['fire_blue']} Debate Filosófico: {tema}",
            description=(
                f"O tema em questão é: **{tema}**\n\n"
                f"{E['arrow_white']} Apresente seus argumentos com rigor e respeito intelectual.\n"
                f"{E['rules']} Referências a autores, obras e argumentos são bem-vindas.\n"
                f"{E['bulb']} Atacar o argumento, nunca a pessoa.\n\n"
                f"*«O filósofo não é aquele que vence o debate, mas aquele que ilumina a questão.»*"
            ),
            color=PHILO_COLOR,
        )
        emb.set_footer(text=f"Debate proposto por {inter.user} • Filosofia Bot")
        await inter.channel.send(embed=emb)
        await inter.response.send_message(
            embed=discord.Embed(description=f"{E['verified']} Debate iniciado!", color=0x57F287),
            ephemeral=True,
        )

    # ── /ajuda ────────────────────────────────────────────────────────────────
    @app_commands.command(name="ajuda", description="Lista todos os comandos do Bot Filosofia")
    async def ajuda(self, inter: discord.Interaction):
        emb = discord.Embed(
            title=f"{E['fire_blue']} Bot Filosofia — Comandos",
            description=(
                f"{E['dash']} O bot de pesquisa acadêmica e moderação do servidor.\n\u200b"
            ),
            color=PHILO_COLOR,
        )
        emb.add_field(
            name=f"{E['bulb']} Filosofia",
            value=(
                "`/citacao` `/filosofo` `/escola` `/conceito`\n"
                "`/questao` `/paradoxo` `/dilema` `/debater`"
            ),
            inline=False,
        )
        emb.add_field(
            name=f"{E['arrow_blue']} Pesquisa Acadêmica",
            value=(
                "`/pesquisa sep` `/pesquisa philpapers`\n"
                "`/pesquisa livro` `/pesquisa autor`\n"
                "`/pesquisa doi` `/pesquisa wikipedia`\n"
                "`/pesquisa fontes`"
            ),
            inline=False,
        )
        emb.add_field(
            name=f"{E['trophy']} Academia (Cargos)",
            value="`/academia setup` `/academia painel` `/academia pendentes` `/academia remover_cargo`",
            inline=False,
        )
        emb.add_field(
            name=f"{E['fire_white']} Moderação",
            value=(
                "`/ban` `/unban` `/kick` `/timeout` `/untimeout`\n"
                "`/warn` `/warnings` `/clearwarn`\n"
                "`/purge` `/slowmode` `/lock` `/unlock`\n"
                "`/userinfo` `/setlogchannel`"
            ),
            inline=False,
        )
        emb.add_field(
            name=f"{E['rules']} AutoMod",
            value=(
                "`/automod adicionar` `/automod listar` `/automod remover`\n"
                "`/automod isentar_cargo` `/automod canal_log`"
            ),
            inline=False,
        )
        emb.add_field(
            name=f"{E['star']} Utilidades",
            value=(
                "`/ping` `/uptime` `/botinfo` `/serverinfo`\n"
                "`/userinfo` `/avatar` `/roleinfo` `/channelinfo` `/anuncio`"
            ),
            inline=False,
        )
        emb.set_footer(text="Filosofia Bot • «Conhece-te a ti mesmo.» — Delfos")
        await inter.response.send_message(embed=emb)


async def setup(bot: commands.Bot):
    await bot.add_cog(Philosophy(bot))
