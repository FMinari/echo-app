"""Monta o dicionário inglês → português do app (`app/nucleo/dicionario.json.gz`) a partir do Wiktionary.

Fonte: o extrato do Wiktionary em inglês feito pelo wiktextract (https://kaikki.org/dictionary/English/),
licença CC BY-SA 4.0 / GFDL, como o próprio Wiktionary: o app cita a fonte na aba Sobre. O arquivo tem
~3 GB; é lido em fluxo (sem guardar), e só ficam as palavras e expressões que aparecem nas falas do
corpus.db (lemas), com as traduções para o português agrupadas por classe e sentido.

Uso: app/.venv/bin/python -I ferramentas/dicionario.py [arquivo .jsonl já baixado]
     app/.venv/bin/python -I ferramentas/dicionario.py --so-limpar   (só passa a limpeza no arquivo que já existe)
Refazer quando entrar muita obra nova no corpus (palavras novas).
"""
import gzip
import json
import re
import sqlite3
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
URL = "https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl"
SAIDA = RAIZ / "app" / "nucleo" / "dicionario.json.gz"
CLASSES = {"noun": "substantivo", "verb": "verbo", "adj": "adjetivo", "adv": "advérbio", "prep": "preposição",
           "pron": "pronome", "conj": "conjunção", "intj": "interjeição", "phrase": "expressão",
           "det": "determinante", "num": "numeral", "particle": "partícula", "prep_phrase": "expressão",
           "contraction": "contração", "article": "artigo", "postp": "posposição", "prefix": "prefixo",
           "suffix": "sufixo", "symbol": "símbolo"}
# no Wiktionary, às vezes o exemplo ou a observação em inglês vai no lugar da tradução ("We sat on the bench")
INGLES = {"the", "of", "with", "without", "or", "and", "we", "on", "in", "at", "is", "are", "was", "a", "an", "to"}
MAX_SENTIDOS = 6
MAX_TRADUCOES = 5


def lemas_do_corpus():
    """Lemas das falas (e os phrasal verbs, "get over"), em minúsculas."""
    lemas = set()
    con = sqlite3.connect(f"file:{RAIZ / 'corpus.db'}?mode=ro", uri=True)
    for (tagged,) in con.execute("SELECT tagged FROM frases"):
        for token in tagged.split():
            partes = token.rsplit("/", 2)
            if len(partes) == 3 and re.fullmatch(r"[a-z][a-z'-]*", partes[1]):
                lemas.add(partes[1])
    sys.path.insert(0, str(RAIZ / "app"))
    from nucleo import phrasal
    lemas.update(phrasal.significados())
    return lemas


def linhas(origem):
    if origem:
        with open(origem, encoding="utf-8") as f:
            yield from f
        return
    with urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "sitcomatica"}), timeout=120) as r:
        for linha in r:
            yield linha.decode("utf-8")


def traducoes_pt(entrada):
    """[(sentido em inglês, palavra em português)] da entrada (no topo ou dentro dos sentidos)."""
    todas = list(entrada.get("translations") or [])
    for s in entrada.get("senses") or []:
        todas += s.get("translations") or []
    return [(t.get("sense") or "", t["word"]) for t in todas
            if t.get("code") == "pt" and t.get("word") and len(t["word"]) < 60]


def parece_ingles(traducao):
    return sum(w in INGLES for w in re.findall(r"[a-z]+", traducao.lower())) >= 2


def limpar(dic):
    """Tira as "traduções" em inglês, os sentidos que ficarem vazios, e põe as classes em português."""
    saida = {}
    for palavra, entradas in dic.items():
        novas = []
        for e in entradas:
            sentidos = [{**s, "traducoes": t} for s in e["sentidos"]
                        if (t := [x for x in s["traducoes"] if not parece_ingles(x)])]
            if sentidos:
                novas.append({"classe": CLASSES.get(e["classe"], e["classe"]), "sentidos": sentidos})
        if novas:
            saida[palavra] = novas
    return saida


def gravar(saida):
    with gzip.open(SAIDA, "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(saida, f, ensure_ascii=False, separators=(",", ":"))


def main():
    if "--so-limpar" in sys.argv:
        with gzip.open(SAIDA, "rt", encoding="utf-8") as f:
            saida = limpar(json.load(f))
        gravar(saida)
        print(f"{len(saida)} palavras → {SAIDA.name} ({SAIDA.stat().st_size / 1e6:.1f} MB)")
        return
    inicio = time.time()
    lemas = lemas_do_corpus()
    print(f"{len(lemas)} lemas no corpus", flush=True)
    dic = defaultdict(lambda: defaultdict(dict))  # palavra -> classe -> sentido -> [traduções]
    lidas = 0
    for linha in linhas(sys.argv[1] if len(sys.argv) > 1 else None):
        lidas += 1
        if lidas % 200000 == 0:
            print(f"  {lidas} entradas lidas, {len(dic)} palavras ({time.time() - inicio:.0f} s)", flush=True)
        if '"code": "pt"' not in linha and '"code":"pt"' not in linha:
            continue
        e = json.loads(linha)
        palavra = (e.get("word") or "").lower()
        if e.get("lang_code") != "en" or palavra not in lemas or e.get("pos") == "name":
            continue
        classe = CLASSES.get(e.get("pos"), e.get("pos") or "")
        for sentido, pt in traducoes_pt(e):
            lista = dic[palavra][classe].setdefault(sentido, [])
            if pt not in lista and len(lista) < MAX_TRADUCOES:
                lista.append(pt)
    saida = limpar({p: [{"classe": c, "sentidos": [{"sentido": s, "traducoes": t} for s, t in list(sentidos.items())[:MAX_SENTIDOS]]}
                        for c, sentidos in classes.items()] for p, classes in sorted(dic.items())})
    gravar(saida)
    print(f"{len(saida)} palavras com tradução → {SAIDA.name} ({SAIDA.stat().st_size / 1e6:.1f} MB) "
          f"em {time.time() - inicio:.0f} s")


if __name__ == "__main__":
    main()
