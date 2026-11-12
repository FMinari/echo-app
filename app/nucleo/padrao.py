"""Linguagem de padrões sobre as frases etiquetadas.

No corpus, cada frase tem `tagged` = tokens `palavra/lema/TAG` separados por espaço e
`offsets` = onde cada token começa no texto da frase.

Elementos do padrão, casados em sequência, um token cada:
  [w=if]           palavra em minúsculas; aceita regex: [w=if|when]
  [l=have]         lema (have casa has/had/'ve/'d…)
  [t=VBD]          tag Penn Treebank como regex: [t=VBD|VBN], [t=VB.*] (sem colchetes dentro)
  [l=be t=VBD]     várias condições no mesmo token
  []               qualquer token
  ...              qualquer quantidade de tokens (0 ou mais), sem destaque
  if               atalho para [w=if]
  quantificador logo após o ]: ? * + {0,3}
"""
import re

ELEMENTO = re.compile(r"\.\.\.|\[[^\]]*\](?:[?*+]|\{\d*,?\d*\})?|[^\s\[\]]+")


class PadraoInvalido(ValueError):
    pass


CORINGA = re.compile(r"\[\s*\]((?:[?*+]|\{\d*,?\d*\})?)$")


def _limites(quant):
    """(mínimo, máximo ou None) de tokens de um quantificador ("", "?", "*", "+", "{0,3}")."""
    if quant in ("", "?", "*", "+"):
        return {"": (1, 1), "?": (0, 1), "*": (0, None), "+": (1, None)}[quant]
    a, virgula, b = quant[1:-1].partition(",")
    minimo = int(a or 0)
    return minimo, (int(b) if b else None) if virgula else minimo


def _juntar_coringas(elementos):
    """Coringas vizinhos ("...", "[]", "[]{0,3}") viram um só: juntos, o regex testava cada jeito de
    dividir as palavras entre eles (Palavras no meio + Até 3 palavras levava 20 s no corpus). Com "..."
    no meio, o resultado é um "..." (sem destaque) com o mínimo de palavras somado."""
    saida, grupo = [], []

    def fechar():
        if len(grupo) == 1:
            saida.append(grupo[0])
        elif grupo:
            limites = [(0, None) if el == "..." else _limites(CORINGA.match(el).group(1)) for el in grupo]
            minimo = sum(a for a, _ in limites)
            maximo = None if any(b is None for _, b in limites) else sum(b for _, b in limites)
            if "..." in grupo:
                saida.append(("...", minimo))
            else:
                saida.append(f"[]{{{minimo},{'' if maximo is None else maximo}}}")
        grupo.clear()

    for el in elementos:
        if el == "..." or CORINGA.match(el):
            grupo.append(el)
        else:
            fechar()
            saida.append(el)
    fechar()
    return saida


def compilar(padrao):
    partes = []
    for el in _juntar_coringas(ELEMENTO.findall(padrao)):
        if isinstance(el, tuple):  # "..." com um mínimo de palavras
            partes.append(rf"(?:[^ ]+ ){{{el[1]},}}?")
            continue
        if el == "...":
            partes.append(r"(?:[^ ]+ )*?")
            continue
        if not el.startswith("["):
            el = f"[w={el}]"
        fecha = el.rindex("]")
        corpo, quant = el[1:fecha], el[fecha + 1:]
        campos = {"w": r"[^ /]*", "l": r"[^ /]*", "t": r"[^ ]*"}
        for cond in corpo.split():
            chave, _, valor = cond.partition("=")
            if chave not in campos or not valor:
                raise PadraoInvalido(f"condição inválida: {cond!r} (use w=, l= ou t=)")
            campos[chave] = f"(?:{valor})"
        token = f"(?:{campos['w']}/{campos['l']}/{campos['t']} )"
        partes.append(f"({token}{quant})")  # cada elemento é um grupo, para o destaque
    if not partes:
        raise PadraoInvalido("padrão vazio")
    try:
        return re.compile(" " + "".join(partes))
    except re.error as e:
        raise PadraoInvalido(f"regex inválida no padrão: {e}") from e


def casar(rx, tagged, offsets, texto):
    """Devolve a lista de trechos [inicio, fim] (em caracteres de `texto`) ou None."""
    s = " " + tagged + " "
    m = rx.search(s)
    if not m:
        return None
    inicios = [int(o) for o in offsets.split()]
    trechos = []
    for g in range(1, (m.lastindex or 0) + 1):
        ini, fim = m.span(g)
        if ini == fim:
            continue
        k = s.count(" ", 0, ini) - 1                  # índice do primeiro token do grupo
        n = len(s[ini:fim].split())
        a = inicios[k]
        b = inicios[k + n] if k + n < len(inicios) else len(texto)
        b = a + len(texto[a:b].rstrip())
        if trechos and not texto[trechos[-1][1]:a].strip():
            trechos[-1][1] = b                        # junta tokens vizinhos num trecho só
        else:
            trechos.append([a, b])
    return trechos or [[0, len(texto)]]
