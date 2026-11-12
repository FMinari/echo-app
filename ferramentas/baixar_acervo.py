"""Baixa os textos do acervo público (ver publico/ACERVO.md) para acervo/bruto/, como vieram da fonte.

Uso: python3 -I ferramentas/baixar_acervo.py [fonte ...]   (fontes: gutenberg voa apollo hansard tatoeba
     blender letras; sem nada, todas)

Só baixa o que ainda não está lá (apague o arquivo para baixar de novo). acervo/bruto/ fica fora do git;
quem transforma no formato do indexar.py é o converter_acervo.py.
"""
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import baixar_letra  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
BRUTO = RAIZ / "acervo" / "bruto"
AGENTE = "Mozilla/5.0 (compatible; echo-acervo/1.0; +https://github.com/FMinari/echo-app)"

# id do Gutenberg -> pasta (a mesma pasta vai para acervo/ depois de convertida)
GUTENBERG = {
    844: "the-importance-of-being-earnest", 885: "an-ideal-husband", 790: "lady-windermeres-fan",
    3825: "pygmalion", 3618: "arms-and-the-man", 383: "she-stoops-to-conquer", 1929: "the-school-for-scandal",
    1513: "romeo-and-juliet", 1514: "a-midsummer-nights-dream", 1526: "twelfth-night",
    1342: "pride-and-prejudice", 158: "emma", 46: "a-christmas-carol", 1400: "great-expectations",
    11: "alice-in-wonderland", 514: "little-women", 74: "tom-sawyer", 76: "huckleberry-finn",
    120: "treasure-island", 308: "three-men-in-a-boat", 1661: "sherlock-holmes", 2852: "the-hound-of-the-baskervilles",
    55: "the-wizard-of-oz", 45: "anne-of-green-gables", 289: "the-wind-in-the-willows", 16: "peter-pan",
    113: "the-secret-garden", 64317: "the-great-gatsby",
    10607: "mother-goose",
}
VOA = "https://learningenglish.voanews.com"
VOA_INICIO = ["/a/lets-learn-english-lesson-one/3111026.html", "/a/lets-learn-english-level-2-lesson1/3960391.html",
              "/a/6654462.html"]  # aula 1 do nível 1, do nível 2 e do "with Anna"
APOLLO = ["a8", "a11", "a13"]
HANSARD = "https://hansard-api.parliament.uk"
HANSARD_DESDE = "2025-01-01"
TATOEBA = "https://downloads.tatoeba.org/exports/per_language"
TATOEBA_ARQS = ["eng/eng_sentences.tsv.bz2", "eng/eng-por_links.tsv.bz2", "por/por_sentences.tsv.bz2"]
BLENDER = {"tears-of-steel.srt": "https://download.blender.org/demo/movies/ToS/subtitles/TOS-en.srt",
           "sintel.srt": "https://durian.blender.org/wp-content/content/subtitles/sintel_en.srt"}
# (artista, id no LRCLIB): letra só do próprio artista, publicada até 1930 (ver ACERVO.md)
LETRAS = [("Bessie Smith", 30217738), ("Bessie Smith", 18581462), ("Ma Rainey", 5182542),
          ("Ma Rainey", 30317780), ("Blind Lemon Jefferson", 1533181), ("Blind Lemon Jefferson", 4220314),
          ("Blind Lemon Jefferson", 30432244), ("George M. Cohan", 9430876), ("George M. Cohan", 36343813),
          ("George M. Cohan", 9322670)]


def baixar(url, destino, pausa=1.0):
    """Grava url em destino (se ainda não existir). Devolve o caminho."""
    if destino.exists():
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    for tentativa in range(5):
        try:
            with urllib.request.urlopen(pedido, timeout=60) as r:
                dados = r.read()
            break
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or tentativa == 4:
                raise
            time.sleep(10 * (tentativa + 1))  # servidor ocupado: espera e tenta de novo
    parcial = destino.with_name(destino.name + ".parcial")
    parcial.write_bytes(dados)
    parcial.replace(destino)  # nada pela metade se a conexão cair
    print(f"  {destino.relative_to(RAIZ)} ({len(dados) // 1024} KB)", flush=True)
    time.sleep(pausa)
    return destino


def gutenberg():
    for id_, pasta in GUTENBERG.items():
        baixar(f"https://www.gutenberg.org/cache/epub/{id_}/pg{id_}.txt", BRUTO / "gutenberg" / f"{pasta}.txt", 2)


def voa():
    """Segue as aulas pelos links "Lesson N" de cada página, a partir da aula 1 de cada série."""
    fila, vistos = list(VOA_INICIO), set()
    while fila and len(vistos) < 500:
        caminho = fila.pop(0)
        id_ = re.search(r"(\d+)\.html$", caminho)[1]
        if id_ in vistos:
            continue
        vistos.add(id_)
        pagina = baixar(VOA + caminho, BRUTO / "voa" / f"{id_}.html").read_text(encoding="utf-8", errors="ignore")
        for href, dentro in re.findall(r'<a [^>]*href="(/a/[^"]+?\d+\.html)"[^>]*>(.*?)</a>', pagina, re.S):
            rotulo = html.unescape(re.sub(r"<[^>]+>", " ", dentro))
            if re.search(r"(?i)\blesson \d+", rotulo) and not re.search(r"(?i)practice|quiz|test", rotulo):
                fila.append(href)
    print(f"voa: {len(vistos)} páginas")


def apollo():
    for m in APOLLO:
        baixar(f"https://raw.githubusercontent.com/Spacelog/Spacelog/master/missions/{m}/transcripts/TEC",
               BRUTO / "apollo" / f"{m}.txt")
        baixar(f"https://raw.githubusercontent.com/Spacelog/Spacelog/master/missions/{m}/transcripts/_meta",
               BRUTO / "apollo" / f"{m}.meta.json")


def hansard():
    params = {"queryParameters.searchTerm": "Engagements", "queryParameters.house": "Commons",
              "queryParameters.startDate": HANSARD_DESDE, "queryParameters.take": 200}
    busca = baixar(f"{HANSARD}/search/debates.json?{urllib.parse.urlencode(params)}",
                   BRUTO / "hansard" / f"busca-{HANSARD_DESDE}.json")
    achados = [x for x in json.loads(busca.read_text())["Results"]
               if x["Title"] == "Engagements" and x["DebateSection"] == "Commons Chamber"]
    falhas = 0
    for x in achados:
        try:
            baixar(f"{HANSARD}/debates/debate/{x['DebateSectionExtId']}.json",
                   BRUTO / "hansard" / f"{x['SittingDate'][:10]}-{x['DebateSectionExtId']}.json")
        except urllib.error.HTTPError as e:  # alguns ids da busca a API não serve (400): fica sem essa
            falhas += 1
            print(f"  sem {x['SittingDate'][:10]} {x['DebateSectionExtId']}: {e.code}", file=sys.stderr)
    print(f"hansard: {len(achados) - falhas} de {len(achados)} sessões")


def tatoeba():
    for arq in TATOEBA_ARQS:
        baixar(f"{TATOEBA}/{arq}", BRUTO / "tatoeba" / Path(arq).name)


def blender():
    for nome, url in BLENDER.items():
        baixar(url, BRUTO / "blender" / nome)


def letras():
    for artista, id_ in LETRAS:
        destino = BRUTO / "letras" / f"{id_}.json"
        if not destino.exists():
            destino.parent.mkdir(parents=True, exist_ok=True)
            x = baixar_letra.pegar(f"get/{id_}")
            x["artista"] = artista
            destino.write_text(json.dumps(x, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  {destino.relative_to(RAIZ)}: {x['artistName']} - {x['trackName']}", flush=True)
            time.sleep(1)


FONTES = {"gutenberg": gutenberg, "voa": voa, "apollo": apollo, "hansard": hansard, "tatoeba": tatoeba,
          "blender": blender, "letras": letras}

if __name__ == "__main__":
    pedidas = sys.argv[1:] or list(FONTES)
    if desconhecidas := set(pedidas) - set(FONTES):
        sys.exit(f"fonte desconhecida: {', '.join(sorted(desconhecidas))} (há: {', '.join(FONTES)})")
    for nome in pedidas:
        print(f"== {nome}", flush=True)
        FONTES[nome]()
