"""Converte acervo/bruto/ (o que o baixar_acervo.py trouxe) para acervo/<pasta>/, no formato que o
indexar.py lê, e grava acervo/obras.json.

Uso: python3 -I ferramentas/converter_acervo.py
Depois: .venv/bin/python -I ferramentas/indexar.py --acervo   (gera acervo.db)

Formatos (um .txt por capítulo, ato, aula, missão...):
- livro:    "NN - Título.txt", um parágrafo por linha (narração e falas juntas, sem personagem)
- peca:     "NN - Ato.txt", "Personagem: fala", "Scene: ..." e rubricas entre [ ]
- conversa: "NN - Título.txt", "Quem fala: fala" (Apollo, Parlamento)
- frases:   "NN - Título.txt", "frase em inglês<TAB>tradução" (Tatoeba)
- serie, filme e musica: como em transcripts/ (ver ferramentas/obras.json)
"""
import bz2
import html
import json
import re
import shutil
import string
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BRUTO = RAIZ / "acervo" / "bruto"
ACERVO = RAIZ / "acervo"

# pasta (= nome do arquivo em bruto/gutenberg) -> nome, tipo, ano
GUTENBERG = {
    "the-importance-of-being-earnest": ("The Importance of Being Earnest", "peca", 1895),
    "an-ideal-husband": ("An Ideal Husband", "peca", 1895),
    "lady-windermeres-fan": ("Lady Windermere's Fan", "peca", 1892),
    "pygmalion": ("Pygmalion", "peca", 1913),
    "arms-and-the-man": ("Arms and the Man", "peca", 1894),
    "she-stoops-to-conquer": ("She Stoops to Conquer", "peca", 1773),
    "the-school-for-scandal": ("The School for Scandal", "peca", 1777),
    "romeo-and-juliet": ("Romeo and Juliet", "peca", 1597),
    "a-midsummer-nights-dream": ("A Midsummer Night's Dream", "peca", 1600),
    "twelfth-night": ("Twelfth Night", "peca", 1623),
    "pride-and-prejudice": ("Pride and Prejudice", "livro", 1813),
    "emma": ("Emma", "livro", 1815),
    "a-christmas-carol": ("A Christmas Carol", "livro", 1843),
    "great-expectations": ("Great Expectations", "livro", 1861),
    "alice-in-wonderland": ("Alice's Adventures in Wonderland", "livro", 1865),
    "little-women": ("Little Women", "livro", 1868),
    "tom-sawyer": ("The Adventures of Tom Sawyer", "livro", 1876),
    "huckleberry-finn": ("Adventures of Huckleberry Finn", "livro", 1884),
    "treasure-island": ("Treasure Island", "livro", 1883),
    "three-men-in-a-boat": ("Three Men in a Boat", "livro", 1889),
    "sherlock-holmes": ("The Adventures of Sherlock Holmes", "livro", 1892),
    "the-hound-of-the-baskervilles": ("The Hound of the Baskervilles", "livro", 1902),
    "the-wizard-of-oz": ("The Wonderful Wizard of Oz", "livro", 1900),
    "anne-of-green-gables": ("Anne of Green Gables", "livro", 1908),
    "the-wind-in-the-willows": ("The Wind in the Willows", "livro", 1908),
    "peter-pan": ("Peter Pan", "livro", 1911),
    "the-secret-garden": ("The Secret Garden", "livro", 1911),
    "the-great-gatsby": ("The Great Gatsby", "livro", 1925),
}
ILUSTRACAO = re.compile(r"^\[Illustration[^\]]*\]$")
ROMANO = r"[IVXLC]+"
NUMERO = rf"(?:{ROMANO}|\d+|[A-Z][a-z]+(?:[- ][A-Z]?[a-z]+)?|[A-Z]+(?:[- ][A-Z]+)?)"
CAPITULO = re.compile(rf"^(?:(?:CHAPTER|Chapter|STAVE|Stave)\s+{NUMERO}\b.*|{ROMANO}\.?|{ROMANO}\.\s+[A-Z][A-Z ,.'’-]+)$")
# Sherlock Holmes: cada conto é "I. A SCANDAL IN BOHEMIA"; o "I." sozinho é parte dentro do conto
CAPITULO_DE = {"sherlock-holmes": re.compile(rf"^{ROMANO}\.\s+[A-Z][A-Z ,.'’-]+$")}
# livros em volumes, em que o "CHAPTER I" volta em cada um (aí não dá para achar o sumário por ele)
VOLUMES = {"emma"}
ATO = re.compile(r"^(?:ACT|Act)\s+(?:[IVX]+|[A-Z][a-z]+|THE [A-Z]+)\b.*$|^(?:FIRST|SECOND|THIRD|FOURTH|FIFTH) ACT\b.*$")
CENA = re.compile(r"^(?:SCENE|Scene)\b[ .:IVX0-9]*(.*)$")
FALANTE = re.compile(r"^((?:[A-Z][A-Z'’-]*\.?)(?: (?:[A-Z][A-Z'’-]*\.?|DE|OF|THE|AND|&))*?)(?:\.\s*|\s+(?=[\[(])|\s*$)(.*)$")
RUBRICA = re.compile(r"^(Enter|Re-enter|Exit|Exeunt|Manet|Flourish|Sennet|Alarum|Music)\b")
NAO_FALANTE = re.compile(r"^(ACT|SCENE|END|THE END|FINIS|EPILOGUE|PROLOGUE|CURTAIN|EXEUNT|EXIT|ENTER|DRAMATIS)\b")


def gutenberg_linhas(caminho):
    """O texto do livro, sem o cabeçalho e o rodapé do Projeto Gutenberg."""
    texto = caminho.read_text(encoding="utf-8-sig").replace("\r", "")
    ini = re.search(r"^\*\*\* ?START OF TH(?:E|IS) PROJECT GUTENBERG.*$", texto, re.M)
    fim = re.search(r"^\*\*\* ?END OF TH(?:E|IS) PROJECT GUTENBERG.*$", texto, re.M)
    assert ini and fim, f"{caminho.name}: sem as marcas de início e fim do Gutenberg"
    return texto[ini.end():fim.start()].split("\n")


def paragrafos(linhas):
    """Junta as linhas de cada parágrafo (separados por linha vazia). Devolve [(primeira linha, texto,
    número de linhas)]."""
    saida, atual = [], []
    for linha in linhas + [""]:
        if linha.strip():
            atual.append(linha.strip())
        elif atual:
            saida.append((atual[0], " ".join(atual), len(atual)))
            atual = []
    return saida


def sem_marcas(texto):
    texto = re.sub(r"\[Illustration[^\]]*\]", " ", texto.replace("_", ""))
    return re.sub(r"\s+", " ", texto).strip()


def titulo_do_capitulo(titulo):
    """'CHAPTER II. MISTRESS MARY QUITE CONTRARY' -> 'Mistress Mary Quite Contrary'; só número -> ''."""
    titulo = re.sub(rf"^(?:(?:CHAPTER|Chapter|STAVE|Stave)\s+{NUMERO}|{ROMANO})\b\.?\s*", "", sem_marcas(titulo))
    titulo = titulo.strip(" .[]")
    return string.capwords(titulo) if titulo.isupper() else titulo


def dividir(pars, cabecalho, minimo, pular_sumario=False):
    """Divide nos cabeçalhos; fica só com as partes que têm pelo menos `minimo` parágrafos (a lista de
    personagens tem cabeçalho e quase nada embaixo)."""
    partes, atual = [], None
    for primeira, texto, n in pars:
        # cabeçalho: uma linha, ou duas com o título embaixo (um sumário tem várias)
        if cabecalho.match(primeira) and n <= 2 and len(texto) < 120:
            atual = [texto, [], n]
            partes.append(atual)
        elif atual:
            atual[1].append((primeira, texto, n))
    # o sumário repete os cabeçalhos: o texto começa na última vez que aparece o do primeiro capítulo
    chave = lambda titulo: " ".join(re.sub(r"[^\w ]", " ", titulo).upper().split()[:2])  # noqa: E731
    if partes and pular_sumario:
        partes = partes[max(i for i, p in enumerate(partes) if chave(p[0]) == chave(partes[0][0])):]
    return [(titulo, pars, n) for titulo, pars, n in partes if len(pars) >= minimo]


def livro(pasta, linhas):
    capitulos = []
    for titulo, pars, n in dividir(paragrafos(linhas), CAPITULO_DE.get(pasta, CAPITULO), 3, pasta not in VOLUMES):
        # título do capítulo no parágrafo seguinte ("CHAPTER I." / "Down the Rabbit-Hole")
        if n == 1 and pars and pars[0][2] == 1 and len(pars[0][0]) < 60 and not re.search(r"[.!?:;,\"”]$", pars[0][0]):
            titulo = f"{titulo.rstrip('.')}. {pars[0][0]}"
            pars = pars[1:]
        capitulos.append((titulo_do_capitulo(titulo), [sem_marcas(t) for _, t, _ in pars if not ILUSTRACAO.match(t)]))
    return capitulos


def peca(pasta, linhas):
    atos = []
    for titulo, pars, _ in dividir(paragrafos(linhas), ATO, 15):
        saida, falante = [], None
        for _, texto, _ in pars:
            texto = sem_marcas(texto)
            if m := CENA.match(texto):
                if m[1].strip(" ."):
                    saida.append(f"Scene: {m[1].strip(' .')}")
                falante = None
            elif texto[0] in "[(" or RUBRICA.match(texto):
                saida.append(f"[{texto.strip('[]() ')}]")
            elif (m := FALANTE.match(texto)) and len(m[1]) > 1 and not NAO_FALANTE.match(m[1]):
                falante = m[1].rstrip(".")
                if m[2].strip():
                    saida.append(f"{falante}: {m[2].strip()}")
            elif falante:  # fala que continua em outro parágrafo (o nome veio sozinho na linha)
                saida.append(f"{falante}: {texto}")
            else:
                saida.append(f"[{texto}]")
        if sum(":" in l and not l.startswith("Scene:") for l in saida) >= 10:
            atos.append(("", saida))
    return atos


def nome_arquivo(n, titulo):
    titulo = re.sub(r'[<>:"/\\|?*]', "", titulo)[:80].strip()
    return f"{n:02d} - {titulo}.txt" if titulo else f"{n:02d}.txt"


def gravar(pasta, partes):
    destino = ACERVO / pasta
    shutil.rmtree(destino, ignore_errors=True)
    destino.mkdir(parents=True)
    for n, (titulo, linhas) in enumerate(partes, 1):
        (destino / nome_arquivo(n, titulo)).write_text("\n".join(linhas) + "\n", encoding="utf-8")


def converter_gutenberg(obras):
    for pasta, (nome, tipo, ano) in GUTENBERG.items():
        linhas = gutenberg_linhas(BRUTO / "gutenberg" / f"{pasta}.txt")
        partes = livro(pasta, linhas) if tipo == "livro" else peca(pasta, linhas)
        assert partes, f"{pasta}: nenhum capítulo ou ato achado"
        gravar(pasta, partes)
        obras[pasta] = {"nome": nome, "tipo": tipo, "ano": ano}
        print(f"{pasta}: {len(partes)} {'capítulos' if tipo == 'livro' else 'atos'}, "
              f"{sum(len(l) for _, l in partes)} linhas")


VOA_SERIES = [("Let’s Learn English - Level 1", 1), ("Let’s Learn English - Level 2", 2),
              ("Let’s Learn English with Anna", 3)]
VOA_FALA = re.compile(r"^([A-Z][A-Za-z.'’]+(?: [A-Z][A-Za-z.'’]+){0,2}):\s+(\S.*)$")
VOA_NAO_FALANTE = {"Note", "Photo", "Source", "Credit", "Words", "Writing", "Quiz", "Lesson", "Video", "Audio",
                   "Download", "Speaking", "Pronunciation", "Listening", "Learning Strategy", "New Words",
                   "Grammar", "Practice", "Example", "Examples", "Test", "Answer", "Question", "Teacher"}


def linhas_html(texto):
    texto = re.sub(r"(?s)<(script|style).*?</\1>", "", texto)
    texto = re.sub(r"(?i)<(/?(div|p|li|h\d|tr|section|article)\b[^>]*|br\s*/?)>", "\n", texto)
    texto = html.unescape(re.sub(r"<[^>]+>", "", texto))
    return [re.sub(r"\s+", " ", l).strip() for l in texto.split("\n") if l.strip()]


def converter_voa(obras):
    """Os diálogos do Let's Learn English: série, temporada = nível (3 = "with Anna"), episódio = aula."""
    aulas = {}  # (temporada, aula) -> (título, falas); a mesma aula tem página de vídeo e de texto
    for f in sorted((BRUTO / "voa").glob("*.html")):
        pagina = f.read_text(encoding="utf-8", errors="ignore")
        cabeca = html.unescape(pagina[:15000]).replace("'", "’")
        serie = min(((cabeca.find(n), t) for n, t in VOA_SERIES if n in cabeca), default=None)
        titulo = re.search(r"<title>\s*Lesson (\d+)\s*[:-]\s*(.*?)\s*</title>", html.unescape(pagina), re.S)
        if not serie or not titulo:
            continue
        linhas = [m for l in linhas_html(pagina) if (m := VOA_FALA.match(l)) and m[1] not in VOA_NAO_FALANTE]
        contagem = defaultdict(int)
        for m in linhas:
            contagem[m[1]] += 1
        falas = [f"{m[1]}: {m[2]}" for m in linhas if contagem[m[1]] >= 2]  # personagem fala mais de uma vez
        chave = (serie[1], int(titulo[1]))
        if len(falas) >= 5 and len(falas) > len(aulas.get(chave, ("", []))[1]):
            aulas[chave] = (titulo[2].strip(), falas)
    destino = ACERVO / "lets-learn-english"
    shutil.rmtree(destino, ignore_errors=True)
    destino.mkdir(parents=True)
    for (temporada, aula), (titulo, falas) in sorted(aulas.items()):
        nome = re.sub(r'[<>:"/\\|?*]', "", titulo)[:80].strip()
        (destino / f"S{temporada:02d}E{aula:02d} - {nome}.txt").write_text("\n".join(falas) + "\n", encoding="utf-8")
    obras["lets-learn-english"] = {"nome": "Let's Learn English (VOA)", "tipo": "serie", "ano": 2016, "duracao_min": 5}
    print(f"lets-learn-english: {len(aulas)} aulas, {sum(len(f) for _, f in aulas.values())} falas")


def converter_apollo(obras):
    partes = []
    for missao in ("a8", "a11", "a13"):
        meta = json.loads((BRUTO / "apollo" / f"{missao}.meta.json").read_text(encoding="utf-8"))
        nomes = {}
        for codigo, c in meta["characters"].items():
            nome = re.sub(r"\s*\(.*?\)", "", c.get("short_name") or c.get("name") or "").strip()
            nomes[codigo] = nome
        saida = []
        for linha in (BRUTO / "apollo" / f"{missao}.txt").read_text(encoding="utf-8").splitlines():
            m = re.match(r"^([A-Z][A-Z0-9 _()-]*?):\s*(.+)$", linha)
            if not m or linha.startswith("_"):
                continue  # tempo da missão, página e fita
            codigo = m[1].strip()
            quem = nomes.get(codigo) or nomes.get(codigo.split(" (")[0]) or codigo
            if quem in ("Noise of some kind", "Music", ""):
                continue
            texto = re.sub(r"\[glossary:([^\]]+)\]", r"\1", m[2])
            texto = re.sub(r"\[(?:time|image|ref):[^\]]*\]", " ", texto).strip()
            if re.search(r"[A-Za-z]{2}", texto):
                saida.append(f"{quem}: {texto}")
        partes.append((meta["copy"].get("title") or missao, saida))
    gravar("apollo", partes)
    obras["apollo"] = {"nome": "Missões Apollo (NASA)", "tipo": "conversa", "ano": 1968}
    print(f"apollo: {len(partes)} missões, {sum(len(l) for _, l in partes)} falas")


def converter_hansard(obras):
    """Prime Minister's Questions, uma sessão por dia (as seções "Engagements" do mesmo dia juntas)."""
    por_dia = defaultdict(list)
    for f in sorted((BRUTO / "hansard").glob("20*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if "Items" not in d:  # a API às vezes responde {"Message": "An error has occurred."}
            print(f"  hansard: {f.name} sem falas, pulado", file=sys.stderr)
            continue
        itens = sorted(d["Items"], key=lambda x: x.get("OrderInSection") or 0)
        por_dia[f.name[:10]].append((d["Overview"].get("Id") or 0, itens))
    partes = []
    for dia, secoes in sorted(por_dia.items()):
        saida = []
        for _, itens in sorted(secoes):
            for x in itens:
                if x["ItemType"] != "Contribution" or not x.get("AttributedTo"):
                    continue
                quem = re.sub(r"\s*\(.*$", "", x["AttributedTo"]).strip()
                for par in linhas_html(x.get("Value") or ""):
                    par = re.sub(r"^Q\d+\.\s*(\[\d+\]\s*)?", "", par).strip()
                    if par:
                        saida.append(f"{quem}: {par}")
        if saida:
            a, m, d = dia.split("-")
            partes.append((f"{d}-{m}-{a}", saida))
    gravar("prime-ministers-questions", partes)
    obras["prime-ministers-questions"] = {"nome": "Prime Minister's Questions", "tipo": "conversa", "ano": 2025}
    print(f"prime-ministers-questions: {len(partes)} sessões, {sum(len(l) for _, l in partes)} falas")


# shortcut: as 60 mil mais antigas de 5 a 20 palavras (de ~240 mil com tradução), para o acervo.db caber
# no git do público; com o banco publicado em release, dá para levar todas
TATOEBA_MAX = 60000


def converter_tatoeba(obras):
    """Frases em inglês que têm tradução em português, mil por arquivo (a ordem é a do número no Tatoeba)."""
    def ler(nome):
        with bz2.open(BRUTO / "tatoeba" / nome, "rt", encoding="utf-8") as f:
            for linha in f:
                yield linha.rstrip("\n").split("\t")
    portugues = {i: texto for i, _, texto in ler("por_sentences.tsv.bz2")}
    traducao = {}
    for ingles, por in ler("eng-por_links.tsv.bz2"):
        if ingles not in traducao and por in portugues:
            traducao[ingles] = portugues[por]
    frases = sorted((int(i), texto, traducao[i]) for i, _, texto in ler("eng_sentences.tsv.bz2")
                    if i in traducao and 5 <= len(texto.split()) <= 20)[:TATOEBA_MAX]
    partes = []
    for ini in range(0, len(frases), 1000):
        bloco = frases[ini:ini + 1000]
        partes.append((f"Frases {ini + 1}–{ini + len(bloco)}",
                       [f"{texto}\t{pt}\t{i}" for i, texto, pt in bloco if "\t" not in texto + pt]))
    gravar("tatoeba", partes)
    obras["tatoeba"] = {"nome": "Tatoeba", "tipo": "frases", "ano": 2006}
    print(f"tatoeba: {len(frases)} frases em {len(partes)} arquivos")


BLENDER = {"tears-of-steel": ("Tears of Steel", 2012, 12), "sintel": ("Sintel", 2010, 15)}


def converter_blender(obras):
    for pasta, (nome, ano, minutos) in BLENDER.items():
        srt = (BRUTO / "blender" / f"{pasta}.srt").read_text(encoding="utf-8-sig", errors="replace")
        linhas = [l.strip() for l in srt.replace("\r", "").split("\n")
                  if l.strip() and not re.match(r"^\d+$|^\d\d:\d\d:\d\d", l.strip())]
        # legenda quebra a frase em duas linhas: junta a que não termina em pontuação com a seguinte
        juntas = []
        for l in linhas:
            l = re.sub(r"<[^>]+>", "", l)
            if juntas and not re.search(r"[.!?…\"”]$", juntas[-1]) and l[:1].islower():
                juntas[-1] += " " + l
            else:
                juntas.append(l)
        destino = ACERVO / pasta
        shutil.rmtree(destino, ignore_errors=True)
        destino.mkdir(parents=True)
        (destino / f"{nome}.txt").write_text("\n".join(juntas) + "\n", encoding="utf-8")
        obras[pasta] = {"nome": nome, "tipo": "filme", "ano": ano, "duracao_min": minutos}
        print(f"{pasta}: {len(juntas)} falas")


def converter_letras(obras):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import baixar_letra
    artistas = defaultdict(list)
    for f in sorted((BRUTO / "letras").glob("*.json")):
        artistas[json.loads(f.read_text(encoding="utf-8"))["artista"]].append(f)
    for artista, arquivos in artistas.items():
        pasta = baixar_letra.pasta_do_artista(artista)
        destino = ACERVO / pasta
        shutil.rmtree(destino, ignore_errors=True)
        destino.mkdir(parents=True)
        for f in arquivos:
            x = json.loads(f.read_text(encoding="utf-8"))
            letra = x.get("syncedLyrics") or x.get("plainLyrics")
            duracao = int(round(x.get("duration") or 0))
            cabecalho = [f"[ti:{x['trackName']}]", f"[ar:{artista}]", f"[al:{x.get('albumName') or ''}]",
                         f"[length:{duracao // 60:02d}:{duracao % 60:02d}]", f"[lrclib:{x['id']}]"]
            (destino / baixar_letra.nome_de_arquivo(x["trackName"])).write_text(
                "\n".join(cabecalho + letra.strip().splitlines()) + "\n", encoding="utf-8")
        obras[pasta] = {"nome": artista, "tipo": "musica"}
        print(f"{pasta}: {len(arquivos)} músicas")


def converter_mother_goose(obras):
    """Cada cantiga (título em caixa alta + versos) vira uma "música" sem tempo."""
    linhas = gutenberg_linhas(BRUTO / "gutenberg" / "mother-goose.txt")
    cantigas, atual = [], None
    for linha in linhas:
        s = linha.strip()
        if s and s.isupper() and len(s) < 50 and re.search(r"[A-Z]{2}", s):
            atual = [string.capwords(s), []]
            cantigas.append(atual)
        elif s and atual and not ILUSTRACAO.match(s):
            atual[1].append(sem_marcas(s))
    destino = ACERVO / "mother-goose"
    shutil.rmtree(destino, ignore_errors=True)
    destino.mkdir(parents=True)
    vistos = defaultdict(int)
    for titulo, versos in cantigas:
        if len(versos) < 2:
            continue
        vistos[titulo] += 1
        nome = titulo + (f" ({vistos[titulo]})" if vistos[titulo] > 1 else "")
        (destino / f"{re.sub(r'[<>:"/\\|?*]', '', nome)}.txt").write_text(
            "\n".join([f"[ti:{nome}]", "[ar:Mother Goose]"] + versos) + "\n", encoding="utf-8")
    obras["mother-goose"] = {"nome": "Mother Goose", "tipo": "musica", "ano": 1916}
    print(f"mother-goose: {len(list(destino.iterdir()))} cantigas")


ETAPAS = {"gutenberg": converter_gutenberg, "voa": converter_voa, "apollo": converter_apollo,
          "hansard": converter_hansard, "tatoeba": converter_tatoeba, "blender": converter_blender,
          "letras": converter_letras, "mother-goose": converter_mother_goose}

if __name__ == "__main__":
    obras_json = ACERVO / "obras.json"
    obras = json.loads(obras_json.read_text(encoding="utf-8")) if obras_json.exists() else {}
    for nome in sys.argv[1:] or list(ETAPAS):
        ETAPAS[nome](obras)
    obras_json.write_text(json.dumps(obras, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
