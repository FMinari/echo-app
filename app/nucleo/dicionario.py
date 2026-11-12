"""Dicionário inglês → português das palavras das falas, montado por ferramentas/dicionario.py a partir do
Wiktionary (licença CC BY-SA 4.0; a aba Sobre cita a fonte). Vai no pacote do app, não no corpus.
"""
import gzip
import json
from functools import lru_cache
from pathlib import Path

from . import livre

ARQUIVO = Path(__file__).resolve().parent / "dicionario.json.gz"
FONTE = {"nome": "Wiktionary", "licenca": "CC BY-SA 4.0", "url": "https://en.wiktionary.org/"}


@lru_cache(maxsize=1)
def _dados():
    try:
        with gzip.open(ARQUIVO, "rt", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def _sem_repetir(entrada):
    """Sentidos com as mesmas traduções viram um só ("feliz / feliz" -> "feliz")."""
    vistos, sentidos = set(), []
    for s in entrada["sentidos"]:
        chave = tuple(t.lower() for t in s["traducoes"])
        if chave not in vistos:
            vistos.add(chave)
            sentidos.append(s)
    return {**entrada, "sentidos": sentidos}


def _lemas(p):
    """As formas a procurar, na ordem: as do corpus (saw -> see, que é o mais comum) e a própria palavra."""
    try:
        return list(dict.fromkeys([*livre.uso(p)[0], p]))
    except (ValueError, OSError):
        return [p]


def procurar(palavra):
    """{palavra, lema, entradas: [{classe, sentidos: [{sentido, traducoes}]}], tambem: [{lema, entradas}]}.
    A palavra como a cliente clicou; o lema é a forma que achou no dicionário, pela forma como ela aparece no
    corpus (took -> take; saw -> see primeiro, e "saw" (serra) em `tambem`). Contração vira as partes
    (didn't -> do + not)."""
    escrita = str(palavra or "").strip()
    p = escrita.lower().strip(".,!?;:\"“”‘’()[]…").replace("’", "'")
    dados = _dados()
    achados = []  # (lema, entradas), sem repetir
    if p:
        contracao = p not in dados and ("'" in p or p in ("gonna", "wanna", "gotta"))  # let's está no dicionário
        partes = livre.palavras(p) if contracao else [p]
        for parte in partes[:2]:
            for lema in _lemas(parte):
                if lema in dados and lema not in [a for a, _ in achados]:
                    achados.append((lema, [_sem_repetir(e) for e in dados[lema]]))
                    if len(partes) > 1:
                        break  # de cada parte da contração, só a forma principal
    if not achados:
        return {"palavra": escrita, "lema": None, "entradas": [], "tambem": []}
    (lema, entradas), *outros = achados[:2]
    return {"palavra": escrita, "lema": lema, "entradas": entradas,
            "tambem": [{"lema": l, "entradas": e} for l, e in outros]}
