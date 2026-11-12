"""Reconhecer phrasal verbs numa frase etiquetada (`palavra/lema/TAG …`) e o significado dos mais comuns.

Usado pelo índice (indice.py, que guarda todos) e pela busca sem índice (livre.py): as duas contam igual.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

# partículas de phrasal verb: podem vir depois do objeto (take it off, put your coat on)
PARTICULAS = {"up", "down", "out", "off", "on", "in", "over", "back", "away", "around", "about",
              "through", "along", "together", "apart", "ahead", "by", "forward", "across"}
# preposições que só formam phrasal verb coladas no verbo (look after, look for, run into)
COLADAS = {"after", "for", "into"}
# depois da partícula, a preposição dos phrasal verbs de três palavras (come up with, run out of)
TERCEIRA = {"with", "of", "to", "from", "for", "on", "at"}
# o que pode ficar entre o verbo e a partícula: o objeto (it, your shoes, the car)
TAGS_OBJETO = {"PRP", "PRP$", "DT", "NN", "NNS", "NNP", "NNPS", "JJ", "CD"}
TAGS_VERBO = ("VB", "VBD", "VBG", "VBN", "VBP", "VBZ")

_OBJETO = "|".join(re.escape(t) for t in sorted(TAGS_OBJETO))
_PARTICULA = "|".join(sorted(PARTICULAS | COLADAS))
# verbo (lema e tag), até 3 palavras do objeto, a partícula e, olhando sem consumir, a palavra seguinte
_RX = re.compile(rf"(?:^| )[^ /]+/([^ /]+)/(VB[A-Z]*) ((?:[^ ]+/[^ ]+/(?:{_OBJETO}) ){{0,3}})"
                 rf"({_PARTICULA})/[^ ]+(?= ([^ /]+)/|)")
SIGNIFICADOS = Path(__file__).resolve().parent / "phrasal_significados.json"


def achar(tagged):
    """Gera (lema, tag, combinações) de cada phrasal verb da frase: combinações = ("off",) ou
    ("out", "out of") quando vem a preposição dos de três palavras."""
    for m in _RX.finditer(tagged):
        lema, tag, objeto, particula, depois = m.groups()
        if particula in COLADAS and objeto:
            continue
        if particula in PARTICULAS and depois in TERCEIRA:
            yield lema, tag, (particula, f"{particula} {depois}")
        else:
            yield lema, tag, (particula,)


@lru_cache(maxsize=1)
def significados():
    """{"get over": "superar…", …} (vazio se o arquivo não existir)."""
    try:
        return json.loads(SIGNIFICADOS.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def significado(texto):
    return significados().get(" ".join(str(texto).lower().split()))
