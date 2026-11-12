"""Regra de busca montada com peças, para quem não escreve a linguagem de padrões (padrao.py).

Uma estrutura montada assim guarda `blocos` = {"pecas": [...], "excluir": [...]}:

- cada peça é {"tipo": <id de PECAS>, "texto": "...", "menos": "...", "opcional": bool}; `texto` só nas
  peças que se escrevem ("palavra": palavra exata, "forma": qualquer forma de um verbo/palavra). Várias
  opções separadas por "/": "would/'d", "say/tell". `menos` só nas peças de classe: formas básicas que
  não valem ("Verbo no passado", menos "be/have/do" = qualquer verbo no passado que não seja
  was/were/had/did).
- `excluir` é uma lista de expressões; frase que tiver alguma delas sai do resultado ("had to").

`para_padrao` e `para_excluir` traduzem isso para o que a busca entende.
"""
import re

# id: (grupo, rótulo, exemplos, elemento do padrão). Elemento None = peça que se escreve.
PECAS = {
    "palavra": ("Escrever", "Palavra exata", "escreva: would  ·  várias opções: would/'d", None),
    "forma": ("Escrever", "Qualquer forma de…", "escreva a forma básica: have (pega has, had, 've)", None),
    "pessoa": ("Pessoas e coisas", "Alguém ou algo", "I, you, Ross, the dog, it", "[t=PRP|NNP|NNPS|NN|NNS|EX]+"),
    "substantivo": ("Pessoas e coisas", "Substantivo", "dog, ideas, coffee", "[t=NN|NNS]"),
    "verbo_base": ("Verbos", "Verbo na forma básica", "go, eat, be", "[t=VB]"),
    "verbo_presente": ("Verbos", "Verbo no presente", "go, goes, am, is", "[t=VBP|VBZ]"),
    "verbo_passado": ("Verbos", "Verbo no passado", "went, ate, was, played", "[t=VBD]"),
    "participio": ("Verbos", "Particípio", "gone, eaten, been, played", "[t=VBN]"),
    "verbo_ing": ("Verbos", "Verbo com -ing", "going, eating, being", "[t=VBG]"),
    "verbo_qualquer": ("Verbos", "Qualquer verbo", "go, went, gone, going", "[t=VB|VBD|VBG|VBN|VBP|VBZ]"),
    "modal": ("Verbos", "Verbo modal", "can, could, will, would, should, must, might", "[t=MD]"),
    "adjetivo": ("Descrições", "Adjetivo", "happy, big, tired", "[t=JJ]"),
    "comparativo": ("Descrições", "Comparativo", "bigger, better, more", "[t=JJR|RBR]"),
    "superlativo": ("Descrições", "Superlativo", "biggest, best, most", "[t=JJS|RBS]"),
    "adverbios": ("No meio", "Advérbios (podem faltar)", "just, never, not, really", "[t=RB]*"),
    "palavra_qualquer": ("No meio", "Uma palavra qualquer", "qualquer palavra", "[]"),
    "ate_3": ("No meio", "Até 3 palavras", "0 a 3 palavras quaisquer", "[]{0,3}"),
    "palavras_meio": ("No meio", "Palavras no meio", "quantas forem", "..."),
}
# peças que nunca são o "núcleo" da regra: sozinhas, achariam qualquer frase
SO_RECHEIO = {"adverbios", "palavra_qualquer", "ate_3", "palavras_meio"}

# como o spaCy separa as contrações do inglês no corpus
_NT_ESPECIAIS = {"can't": ["ca", "n't"], "won't": ["wo", "n't"], "ain't": ["ai", "n't"],
                 "shan't": ["sha", "n't"], "cannot": ["can", "not"]}
# gonna e gotta viram duas palavras no corpus; wanna e lemme ficam inteiras (conferido no corpus.db)
_JUNTAS = {"gonna": ["gon", "na"], "gotta": ["got", "ta"]}
_SUFIXOS = ("'ll", "'d", "'ve", "'re", "'m", "'s")


def catalogo_de_pecas():
    """Para a janela montar a lista: [{id, grupo, rotulo, exemplos, escreve, recheio}]."""
    return [{"id": i, "grupo": g, "rotulo": r, "exemplos": x, "escreve": el is None, "recheio": i in SO_RECHEIO}
            for i, (g, r, x, el) in PECAS.items()]


def _limpar(texto):
    texto = str(texto or "").replace("’", "'").replace("‘", "'").strip().lower()
    if "[" in texto or "]" in texto:
        raise ValueError("Não use [ ] nas palavras.")
    return texto


def _tokens(palavras):
    """'I don't' -> ['i', 'do', "n't"], do jeito que o corpus guarda."""
    saida = []
    for p in palavras.split():
        if p in _NT_ESPECIAIS:
            saida += _NT_ESPECIAIS[p]
        elif p in _JUNTAS:
            saida += _JUNTAS[p]
        elif p.endswith("n't") and len(p) > 3:
            saida += [p[:-3], "n't"]
        elif p.endswith(_SUFIXOS) and p.rindex("'") > 0:  # i'm, he's (não 'em)
            corte = p.rindex("'")
            saida += [p[:corte], p[corte:]]
        else:
            saida.append(p)
    return saida


def _elementos_escritos(peca):
    """Peça escrita vira um elemento por palavra; as opções ("/") se alinham palavra a palavra."""
    tipo, texto = peca["tipo"], _limpar(peca.get("texto"))
    opcoes = [o.strip() for o in texto.split("/") if o.strip()]
    if not opcoes:
        raise ValueError(f"A peça “{PECAS[tipo][1]}” está sem texto.")
    if tipo == "forma":
        if any(" " in o for o in opcoes):
            raise ValueError("Em “Qualquer forma de…” vai uma palavra só (use outra peça para a próxima).")
        listas = [[o] for o in opcoes]
    else:
        listas = [_tokens(o) for o in opcoes]
    if len({len(l) for l in listas}) > 1:
        raise ValueError(f"As opções de “{texto}” têm números diferentes de palavras: "
                         "use uma peça para cada jeito.")
    campo = "l" if tipo == "forma" else "w"
    elementos = []
    for i in range(len(listas[0])):
        valores = list(dict.fromkeys(re.escape(l[i]) for l in listas))
        elementos.append(f"[{campo}={'|'.join(valores)}]")
    return elementos


def _com_menos(elemento, menos):
    """'[t=VBD]' + 'be/have' -> '[t=VBD l=(?!(?:be|have)/)\\S+?]': a classe, menos essas formas básicas."""
    formas = [re.escape(f.strip()) for f in _limpar(menos).split("/") if f.strip()]
    if not formas:
        return elemento
    if any(" " in f for f in formas):
        raise ValueError("Em “menos”, vão formas básicas de uma palavra só, separadas por /: be/have/do.")
    fecha = elemento.rindex("]")
    return f"{elemento[:fecha]} l=(?!(?:{'|'.join(formas)})/)\\S+?{elemento[fecha:]}"


def _elementos(peca):
    tipo = peca.get("tipo")
    if tipo not in PECAS:
        raise ValueError(f"Peça desconhecida: {tipo!r}.")
    if PECAS[tipo][3] is None:
        elementos = _elementos_escritos(peca)
    else:
        elementos = [_com_menos(PECAS[tipo][3], peca.get("menos")) if tipo not in SO_RECHEIO else PECAS[tipo][3]]
    if peca.get("opcional") and tipo not in SO_RECHEIO:
        elementos = [e[:-1] + "*" if e.endswith("]+") else e + "?" for e in elementos]
    return elementos


def para_padrao(pecas):
    pecas = list(pecas or [])
    if not any(p.get("tipo") not in SO_RECHEIO and not p.get("opcional") for p in pecas):
        raise ValueError("A regra precisa de pelo menos uma peça obrigatória que diga o que procurar "
                         "(uma palavra, um verbo…), não só peças do meio ou opcionais.")
    return " ".join(e for p in pecas for e in _elementos(p))


def para_excluir(expressoes):
    """Expressões a tirar -> regex sobre o texto da frase (ou None)."""
    partes = []
    for x in expressoes or []:
        x = " ".join(_limpar(x).split())
        if x:
            partes.append(r"\s+".join(re.escape(p) for p in x.split()))
    return rf"(?<!\w)(?:{'|'.join(partes)})(?!\w)" if partes else None


def descrever(pecas):
    """'wish + alguém ou algo + would + verbo na forma básica', para mostrar a regra em português."""
    nomes = []
    for p in pecas or []:
        rotulo = PECAS.get(p.get("tipo"), (None, "?"))[1]
        nome = p.get("texto") if PECAS.get(p.get("tipo"), (0, 0, 0, 1))[3] is None else rotulo.lower()
        if p.get("tipo") == "forma":
            nome = f"{p.get('texto')} (qualquer forma)"
        elif p.get("menos") and p.get("tipo") not in SO_RECHEIO and PECAS.get(p.get("tipo"), (0, 0, 0, None))[3]:
            nome = f"{nome} (menos {p['menos']})"
        nomes.append(f"{nome} (opcional)" if p.get("opcional") and p.get("tipo") not in SO_RECHEIO else nome)
    return " + ".join(nomes)
