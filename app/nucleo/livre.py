"""Busca escrita na hora ("Escrever o que procuro"): o que a cliente digita vira um padrão de padrao.py.

- Com `outras_formas`, cada palavra vale em qualquer forma: o lema dela no corpus (took -> take, que
  casa take/takes/taking/taken). Entre o verbo e uma partícula logo depois dele podem entrar até 3
  palavras do objeto: "take off" acha "take your shoes off".
- `tempo` restringe o primeiro verbo do texto a uma forma (passado, -ing…).
- Uma palavra só que é verbo também lista os phrasal verbs dele nas falas (`phrasal_verbs`).

Com o índice montado (indice.py), as frases com as palavras saem dele na hora; sem ele, de um LIKE no
corpus. Nada aqui grava no dados.db: a busca é avulsa (ver busca.buscar).
"""
import re
from collections import Counter
from functools import lru_cache

from . import bancos, busca, catalogo, indice, phrasal
from .blocos import _limpar, _tokens
from .phrasal import PARTICULAS

TEMPOS = {
    "presente": "VBP|VBZ",
    "passado": "VBD",
    "participio": "VBN",
    "ing": "VBG",
    "basica": "VB",
}
OBJETO = r"[t=PRP|PRP\$|DT|NN|NNS|NNP|NNPS|JJ|CD]{0,3}"
MAXIMO_PALAVRAS = 12
MINIMO_FRASES = 3  # phrasal verb que aparece menos que isso costuma ser erro de etiqueta


# como o corpus guarda: "ex-wife" -> ex - wife, "Mr." com o ponto, "fiancé" com o acento
_HIFEN = re.compile(r"(?<=[^\W_])-(?=[^\W_])")
_PALAVRA = re.compile(r"\b(?:mrs?|ms|dr|st|jr|sr)\.|[^\W_](?:[^\W_]|')*|(?<= )-(?= )")


def palavras(texto):
    """'Took it OFF!' -> ['took', 'it', 'off'], separando contrações como o corpus ('don't' -> do n't)."""
    limpo = _HIFEN.sub(" - ", _limpar(texto))
    return _tokens(" ".join(_PALAVRA.findall(limpo)))


def _like(texto):
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@lru_cache(maxsize=1024)
def _uso(palavra, corpus, com_indice):
    """Como a palavra aparece no corpus (amostra): (lemas, é verbo na maioria das vezes, às vezes é verbo)."""
    lemas, verbo, n = Counter(), 0, 0
    termo = indice.termo("2", palavra) if com_indice else None
    with bancos.corpus() as con:
        if termo:
            linhas = con.execute("SELECT tagged FROM frases WHERE id IN "
                                 "(SELECT rowid FROM ix.palavras WHERE palavras MATCH ? LIMIT 300)", (termo,))
        else:
            linhas = con.execute(r"SELECT tagged FROM frases WHERE ' ' || tagged LIKE ? ESCAPE '\' LIMIT 300",
                                 (f"% {_like(palavra)}/%",))
        for (t,) in linhas:
            for token in t.split():
                partes = token.rsplit("/", 2)
                if len(partes) == 3 and partes[0] == palavra:
                    lemas[partes[1]] += 1
                    verbo += partes[2].startswith("VB")
                    n += 1
    frequentes = [l for l, k in lemas.most_common() if k >= n * 0.1]
    return tuple(dict.fromkeys([*frequentes, palavra])), n > 0 and verbo > n / 2, verbo >= 2


def uso(palavra):
    """(lemas, é verbo na maioria das vezes)."""
    return _uso(palavra, str(bancos.caminho_corpus()), indice.pronto() is not None)[:2]


def pode_ser_verbo(palavra):
    """Aparece como verbo pelo menos de vez em quando ("plan", "date": mais substantivo que verbo)."""
    return _uso(palavra, str(bancos.caminho_corpus()), indice.pronto() is not None)[2]


def _contem(grupos, com_indice):
    """Pré-filtro das frases: cada grupo é (lemas, None) ou (None, palavra exata) e a frase precisa ter
    todos. Com o índice, um MATCH; o que o índice não guarda (n't, 's) vai por LIKE."""
    fts, condicoes, argumentos = [], [], []
    for lemas, exata in grupos:
        termos = [indice.termo("1", l) for l in lemas] if lemas else [indice.termo("2", exata)]
        if com_indice and all(termos):
            fts.append("(" + " OR ".join(termos) + ")")
        elif lemas:
            condicoes.append("(" + " OR ".join(r"f.tagged LIKE ? ESCAPE '\'" for _ in lemas) + ")")
            argumentos += [f"%/{_like(l)}/%" for l in lemas]
        else:
            condicoes.append(r"' ' || f.tagged LIKE ? ESCAPE '\'")
            argumentos.append(f"% {_like(exata)}/%")
    if fts:
        condicoes.insert(0, "f.id IN (SELECT rowid FROM ix.palavras WHERE palavras MATCH ?)")
        argumentos.insert(0, " AND ".join(fts))
    return " AND ".join(condicoes), tuple(argumentos)


def montar(texto, outras_formas=True, tempo=None):
    """{padrao, contem, palavras, verbo}: `contem` = (trecho SQL, argumentos) que separa as frases com
    essas palavras antes de aplicar o padrão; `verbo` = a palavra que o tempo afeta (ou None)."""
    ps = palavras(texto)
    if not ps:
        raise ValueError("Escreva o que quer procurar: uma palavra ou mais, em inglês.")
    if len(ps) > MAXIMO_PALAVRAS:
        raise ValueError(f"Escreva no máximo {MAXIMO_PALAVRAS} palavras.")
    if tempo and tempo not in TEMPOS:
        raise ValueError(f"Tempo do verbo desconhecido: {tempo!r}.")
    elementos, grupos, verbo = [], [], None
    if outras_formas:
        # o verbo: a primeira palavra que é verbo quase sempre; com tempo pedido, serve a que às vezes é
        # ("plan" no passado = planned, mesmo "plan" sendo mais substantivo)
        verbo = next((i for i, p in enumerate(ps) if uso(p)[1]), None)
        if verbo is None and tempo:
            verbo = next((i for i, p in enumerate(ps) if pode_ser_verbo(p)), None)
        if verbo is None and tempo:
            raise ValueError("Não achei um verbo no que você escreveu para mudar o tempo. Tire o “Tempo do "
                             "verbo” ou escreva um verbo.")
    for i, p in enumerate(ps):
        if outras_formas:
            lemas = uso(p)[0]
            cond = "l=" + "|".join(re.escape(l) for l in lemas)
            if i == verbo:
                if tempo:
                    cond += f" t={TEMPOS[tempo]}"
            elif verbo is not None and i == verbo + 1 and p in PARTICULAS:
                elementos.append(OBJETO)
            grupos.append((lemas, None))
        else:
            cond = f"w={re.escape(p)}"
            grupos.append((None, p))
        elementos.append(f"[{cond}]")
    significado = None
    if verbo == 0 and len(ps) > 1:  # "took off" -> o significado de "take off"
        significado = phrasal.significado(" ".join([uso(ps[0])[0][0], *ps[1:]]))
    return {"padrao": " ".join(elementos), "contem": _contem(grupos, indice.pronto() is not None),
            "palavras": ps, "verbo": ps[verbo] if verbo is not None else None,
            "significado": significado or phrasal.significado(" ".join(ps))}


def buscar(texto, outras_formas=True, tempo=None, **filtros):
    """busca.buscar com o que a cliente escreveu; devolve também `livre` = {palavras, verbo}."""
    regra = montar(texto, outras_formas, tempo)
    r = busca.buscar(padrao=regra["padrao"], contem=regra["contem"],
                     rotulo=f"Busca: {' '.join(texto.split())}", **filtros)
    r["livre"] = {"palavras": regra["palavras"], "verbo": regra["verbo"], "significado": regra["significado"]}
    return r


NOMES_TEMPOS = {"presente": "presente", "passado": "passado", "participio": "particípio", "ing": "com -ing",
               "basica": "forma básica"}
CATEGORIA_PADRAO = "Minhas buscas"


def guardar(texto, outras_formas=True, tempo=None, nome=None, categoria=None):
    """Guarda a busca escrita como estrutura do catálogo (regra avançada = o padrão da busca) e já
    preenche o cache da cliente com os achados em todas as obras: a primeira busca não varre o corpus."""
    regra = montar(texto, outras_formas, tempo)
    escrito = " ".join(str(texto).split())
    nome = " ".join(str(nome or escrito).split())
    if not nome:
        raise ValueError("Dê um nome para a estrutura.")
    como = ["outras formas" if outras_formas else "só do jeito que foi escrito"]
    if tempo and outras_formas:
        como.append(f"verbo no {NOMES_TEMPOS[tempo]}" if tempo != "ing" else "verbo com -ing")
    obra_ids = busca._ids_obras()
    with bancos.corpus() as con:
        achados = list(busca._varrer(con, *busca._compilar(regra["padrao"], None, None), obra_ids, regra["contem"]))
    if not achados:
        raise ValueError("Essa busca não acha nenhuma frase: não dá para guardar como estrutura.")
    exemplos = [a[7] for a in sorted(achados, key=lambda a: a[0]) if 5 <= a[4] <= 14][:2]
    e = catalogo.criar(
        nome=nome, categoria=" ".join(str(categoria or "").split()) or CATEGORIA_PADRAO, formula=escrito,
        explicacao=(f"{regra['significado']}. " if regra["significado"] else "")
        + f"Guardada da busca escrita ({', '.join(como)}).",
        padrao=regra["padrao"], exemplos=exemplos, origem="busca")
    busca._gravar_varredura(e["id"], busca.hash_regra(e), busca.versao_corpus(), obra_ids,
                            [a[:6] for a in achados])
    return catalogo.obter(e["id"])


def phrasal_verbs(texto, tempo=None, obras=None, tipo=None, temporada=None, falante=None, min_palavras=4):
    """Phrasal verbs de um verbo (uma palavra só) nas falas, mais usados primeiro:
    [{texto: 'take off', frases: 466, significado: '…'}, …]. Outra coisa que não um verbo sozinho: []."""
    ps = palavras(texto)
    if len(ps) != 1:
        return []
    if tempo and tempo not in TEMPOS:
        raise ValueError(f"Tempo do verbo desconhecido: {tempo!r}.")
    obra_ids = busca._ids_obras(obras, tipo)
    if not obra_ids:
        return []
    todas = len(obra_ids) == len(busca._ids_obras())
    lista = _phrasal_verbs(ps[0], tempo, None if todas else tuple(obra_ids), temporada,
                           (falante or "").lower() or None, min_palavras, str(bancos.caminho_corpus()),
                           indice.pronto() is not None)
    return [dict(x) | {"significado": phrasal.significado(dict(x)["texto"])} for x in lista]


@lru_cache(maxsize=32)
def _phrasal_verbs(palavra, tempo, obra_ids, temporada, falante, min_palavras, corpus, com_indice):
    lemas, e_verbo = uso(palavra)
    if not e_verbo:
        return ()
    tags = TEMPOS[tempo].split("|") if tempo else list(phrasal.TAGS_VERBO)
    filtros, args = "", []
    if obra_ids or temporada or falante:  # o JOIN custa caro no corpus inteiro: só com filtro
        filtros = " AND f.linha_id IN (SELECT l.id FROM linhas l JOIN episodios e ON e.id = l.episodio_id "
        filtros += f"WHERE e.obra_id IN ({','.join('?' * len(obra_ids or busca._ids_obras()))})"
        args += list(obra_ids or busca._ids_obras())
        if temporada:
            filtros += " AND e.temporada = ?"
            args.append(int(temporada))
        if falante:
            filtros += " AND l.falante = ? COLLATE NOCASE"
            args.append(falante)
        filtros += ")"
    conta = Counter()
    with bancos.corpus() as con:
        if com_indice:
            sql = (f"""SELECT p.combo, count(DISTINCT p.frase_id) FROM ix.phrasal p
                       {"JOIN frases f ON f.id = p.frase_id" if filtros else ""}
                       WHERE p.lema IN ({','.join('?' * len(lemas))}) AND p.tag IN ({','.join('?' * len(tags))})
                         AND p.palavras >= ?{filtros} GROUP BY p.combo""")
            conta.update(dict(con.execute(sql, [*lemas, *tags, min_palavras, *args]).fetchall()))
        else:
            sql = (f"""SELECT f.tagged, length(f.texto) - length(replace(f.texto, ' ', '')) + 1 FROM frases f
                       WHERE ({' OR '.join(r"f.tagged LIKE ? ESCAPE '\'" for _ in lemas)})"""
                   + filtros)
            for tagged, n in con.execute(sql, [*(f"%/{_like(l)}/%" for l in lemas), *args]):
                if n < min_palavras:
                    continue
                conta.update({combo for lema, tag, combos in phrasal.achar(tagged)
                              if lema in lemas and tag in tags for combo in combos})
    base = lemas[0]
    return tuple((("texto", f"{base} {combo}"), ("frases", n))
                 for combo, n in sorted(conta.items(), key=lambda x: (-x[1], x[0])) if n >= MINIMO_FRASES)
