"""Busca de frases no corpus por padrão gramatical e/ou texto.

Buscas por estrutura do catálogo usam cache: a primeira vez que a estrutura X é procurada na
obra Y, o corpus inteiro da obra é varrido e todos os achados vão para `ocorrencias` (dados.db).
Da segunda vez em diante é só SELECT. A varredura é refeita sozinha quando a regra da estrutura
muda (hash de padrão/texto/excluir) ou quando o corpus é trocado (versão em corpus.meta).
Padrões avulsos (sem estrutura, como a busca escrita de livre.py) não vão para o dados.db: varrem o
corpus e as últimas ficam só na memória (_AVULSAS), para trocar de página e filtrar sem varrer de novo.
"""
import hashlib
import json
import random
import re
import sqlite3
from collections import Counter, OrderedDict

from . import bancos, catalogo, grupos
from .grupos import sem_acento
from .padrao import casar, compilar
from .registro import NaoEncontrado

TIPOS = ("serie", "filme", "musica", "livro", "peca", "conversa", "frases")  # ordem das seções no resultado


def frases_do_episodio(con, arquivo, texto, colunas):
    """As frases com este texto neste episódio (as guardadas são achadas por arquivo + texto). Começa
    pelo episódio: a ordem natural do SQLite varria o corpus inteiro (~0,3 s por frase)."""
    return con.execute(f"""SELECT {colunas} FROM episodios e CROSS JOIN linhas l CROSS JOIN frases f
                           WHERE e.arquivo = ? AND l.episodio_id = e.id AND f.linha_id = l.id AND f.texto = ?
                           ORDER BY f.id""", (arquivo, texto)).fetchall()


def tempo(segundos, tipo=None):
    """Série e filme: arredonda para 30 s, porque o tempo é estimado e não tem precisão melhor que isso.
    Música: o tempo do verso na letra (LRC), exato. Sem tempo (livro, peça, letra sem duração): vazio."""
    if segundos is None:
        return ""
    if tipo == "musica":
        s = int(segundos or 0)
        return f"{s // 60:02d}:{s % 60:02d}"
    s = int(round((segundos or 0) / 30) * 30)
    return f"~{s // 60:02d}:{s % 60:02d}"


def referencia(temporada, episodio, episodio_fim, tipo=None):
    if tipo == "musica":
        return "música"
    if tipo == "livro":
        return f"cap. {episodio}"
    if tipo == "peca":
        return f"ato {episodio}"
    if tipo in ("conversa", "frases"):
        return ""  # o título (missão, sessão) já diz onde é
    if temporada is None:
        return "filme"
    if episodio is None:
        return f"S{temporada:02d} extra"
    fim = f"-E{episodio_fim:02d}" if episodio_fim and episodio_fim != episodio else ""
    return f"S{temporada:02d}E{episodio:02d}{fim}"


def tipos_das_obras():
    """{nome da obra: tipo}. As frases guardadas nas aulas não têm o tipo: ele vem daqui pelo nome."""
    with bancos.corpus() as con:
        return dict(con.execute("SELECT nome, tipo FROM obras").fetchall())


def listar_obras():
    with bancos.corpus() as con:
        return [dict(r) for r in con.execute(
            """SELECT o.id, o.nome, o.tipo, o.ano, count(e.id) AS episodios,
                      min(e.temporada) AS primeira_temporada, max(e.temporada) AS ultima_temporada
               FROM obras o LEFT JOIN episodios e ON e.obra_id = o.id
               GROUP BY o.id ORDER BY o.nome""")]


def listar_falantes(obras=None, minimo=20):
    """Personagens por obra (o mesmo nome pode existir em duas séries), mais falantes primeiro."""
    sql = """SELECT l.falante, o.id AS obra_id, o.nome AS obra, count(*) AS falas
             FROM linhas l JOIN episodios e ON e.id = l.episodio_id JOIN obras o ON o.id = e.obra_id
             WHERE l.tipo = 'fala' AND l.falante IS NOT NULL"""
    args = []
    if obras:
        ids = _ids_obras(obras)
        sql += f" AND e.obra_id IN ({','.join('?' * len(ids))})"
        args += ids
    sql += " GROUP BY o.id, l.falante HAVING count(*) >= ? ORDER BY o.nome, falas DESC"
    with bancos.corpus() as con:
        return [dict(r) for r in con.execute(sql, args + [minimo])]


def _ids_obras(obras=None, tipo=None):
    """Aceita ids, nomes de obra ou nomes de grupo (sem distinção de maiúsculas). Sem `obras`, todas
    (do `tipo`, se dado)."""
    with bancos.corpus() as con:
        todas = {r["nome"].lower(): (r["id"], r["tipo"]) for r in con.execute("SELECT id, nome, tipo FROM obras")}
    if not obras:
        return [i for i, t in todas.values() if not tipo or t == tipo]
    por_id = {i: t for i, t in todas.values()}
    ids, de_grupos = [], None
    for o in obras:
        if isinstance(o, int) or str(o).isdigit():
            if int(o) not in por_id:
                raise ValueError(f"obra desconhecida: {o!r}")
            achadas = [int(o)]
        elif str(o).lower() in todas:
            achadas = [todas[str(o).lower()][0]]
        else:
            de_grupos = de_grupos if de_grupos is not None else grupos.por_nome()
            if str(o).lower() not in de_grupos:
                raise ValueError(f"obra ou grupo desconhecido: {o!r}. Obras: {', '.join(sorted(todas))}. "
                                 f"Grupos: {', '.join(sorted(de_grupos)) or 'nenhum'}")
            achadas = de_grupos[str(o).lower()]
        ids += [i for i in achadas if (not tipo or por_id[i] == tipo) and i not in ids]
    return ids


def versao_corpus():
    with bancos.corpus() as con:
        r = con.execute("SELECT valor FROM meta WHERE chave = 'versao'").fetchone()
    return r["valor"] if r else "sem-versao"


def rotulo_corpus():
    """Versão legível do corpus, ex. "06/10/2026 20:51 · 5 obras": serve pra saber qual banco a cliente tem."""
    with bancos.corpus() as con:
        r = con.execute("SELECT valor FROM meta WHERE chave = 'gerado_em'").fetchone()
        n = con.execute("SELECT count(*) FROM obras").fetchone()[0]
    if not r:
        return f"{n} obras"
    data, _, hora = r["valor"].partition(" ")
    a, m, d = data.split("-")
    return f"{d}/{m}/{a} {hora[:5]} · {n} obras"


def hash_regra(e):
    return hashlib.sha1(json.dumps([e["padrao"], e["texto"], e["excluir"]]).encode()).hexdigest()[:16]


def _linhas(con, obra_ids, contem=None):
    """Frases das obras. `contem` = (trecho SQL sobre f.tagged, argumentos): separa antes as frases que
    têm as palavras procuradas, bem mais rápido que testar o padrão em todas."""
    filtro, args = contem or ("1", ())
    return con.execute(f"""SELECT f.id, f.texto, f.tagged, f.offsets, l.falante, e.obra_id, e.temporada, e.arquivo
              FROM frases f JOIN linhas l ON l.id = f.linha_id JOIN episodios e ON e.id = l.episodio_id
              WHERE e.obra_id IN ({','.join('?' * len(obra_ids))}) AND ({filtro})""", [*obra_ids, *args])


def _casar_linha(r, rx_padrao, rx_texto, rx_excluir):
    """Destaques da regra nessa frase, ou None se ela não casa."""
    frase = r["texto"]
    m = None
    if rx_texto and not (m := rx_texto.search(frase)):
        return None
    if rx_excluir and rx_excluir.search(frase):
        return None
    if rx_padrao:
        return casar(rx_padrao, r["tagged"], r["offsets"], frase)
    return [list(m.span())]


def _achado(r, destaques):
    return (r["id"], r["obra_id"], r["temporada"], r["falante"], len(r["texto"].split()),
            destaques, r["arquivo"], r["texto"])


def _varrer(con, rx_padrao, rx_texto, rx_excluir, obra_ids, contem=None):
    """Gera (frase_id, obra_id, temporada, falante, palavras, destaques, arquivo, texto)."""
    for r in _linhas(con, obra_ids, contem):
        destaques = _casar_linha(r, rx_padrao, rx_texto, rx_excluir)
        if destaques is not None:
            yield _achado(r, destaques)


def _compilar(padrao, texto, excluir):
    return (compilar(padrao) if padrao else None,
            re.compile(texto, re.I) if texto else None,
            re.compile(excluir, re.I) if excluir else None)


def garantir_varredura(estrutura, obra_ids):
    """Varre só as obras que ainda não têm cache válido para a estrutura. Devolve quantas varreu."""
    return garantir_varreduras([estrutura], obra_ids)


POR_PASSADA = 20  # estruturas testadas por leitura do corpus (mais que isso pesa na memória)


def garantir_varreduras(estruturas, obra_ids):
    """Cache válido para várias estruturas nessas obras. Ler o corpus custa mais que testar uma
    regra, então cada leitura testa até POR_PASSADA estruturas. Devolve quantas (estrutura, obra)
    foram varridas."""
    corpus_v = versao_corpus()
    tarefas = []
    for estrutura in estruturas:
        e = catalogo.obter(estrutura)
        regra = hash_regra(e)
        with bancos.dados() as dados:
            feitas = {r["obra_id"] for r in dados.execute(
                "SELECT obra_id FROM varreduras WHERE estrutura_id = ? AND regra = ? AND corpus = ?",
                (e["id"], regra, corpus_v))}
        pendentes = [o for o in obra_ids if o not in feitas]
        if pendentes:
            tarefas.append({"e": e, "regra": regra, "pendentes": pendentes, "achados": [],
                            "rxs": _compilar(e["padrao"], e["texto"], e["excluir"]),
                            "falsos": catalogo.falsos_positivos(e["id"])})
    tarefas = [t for t in tarefas if not _do_cache_de_fabrica(t, corpus_v)]
    for i in range(0, len(tarefas), POR_PASSADA):
        lote = tarefas[i:i + POR_PASSADA]
        for t in lote:
            t["obras"] = set(t["pendentes"])
        with bancos.corpus() as con:
            for r in _linhas(con, sorted(set().union(*(t["obras"] for t in lote)))):
                for t in lote:
                    if r["obra_id"] in t["obras"]:
                        destaques = _casar_linha(r, *t["rxs"])
                        if destaques is not None and (r["arquivo"], r["texto"]) not in t["falsos"]:
                            t["achados"].append(_achado(r, destaques))
        for t in lote:
            _gravar_varredura(t["e"]["id"], t["regra"], corpus_v, t["pendentes"], t["achados"])
            t["achados"] = None  # libera a memória antes do próximo lote
    return sum(len(t["pendentes"]) for t in tarefas)


def _do_cache_de_fabrica(t, corpus_v):
    """Se o corpus.db traz pronta essa regra (ferramentas/cache_fabrica.py, para as estruturas de
    fábrica), copia os achados em vez de varrer. Devolve se copiou."""
    with bancos.corpus() as con:
        try:
            if not con.execute("SELECT 1 FROM fabrica_regras WHERE regra = ?", (t["regra"],)).fetchone():
                return False
        except sqlite3.OperationalError:  # corpus sem o cache de fábrica
            return False
        fora = set()
        for arquivo, frase in t["falsos"]:  # falsos positivos da cliente: guardados por arquivo + texto
            fora.update(r["id"] for r in frases_do_episodio(con, arquivo, frase, "f.id"))
        marcas = ",".join("?" * len(t["pendentes"]))
        achados = [(r[0], r[1], r[2], r[3], r[4], json.loads(r[5])) for r in con.execute(
            f"""SELECT frase_id, obra_id, temporada, falante, palavras, destaques FROM fabrica_ocorrencias
                WHERE regra = ? AND obra_id IN ({marcas})""", [t["regra"], *t["pendentes"]])
            if r[0] not in fora]
    _gravar_varredura(t["e"]["id"], t["regra"], corpus_v, t["pendentes"], achados)
    return True


def _gravar_varredura(estrutura_id, regra, corpus_v, pendentes, achados):
    with bancos.dados() as dados:
        marcas = ",".join("?" * len(pendentes))
        dados.execute(f"DELETE FROM ocorrencias WHERE estrutura_id = ? AND obra_id IN ({marcas})",
                      [estrutura_id, *pendentes])
        dados.executemany(
            "INSERT INTO ocorrencias (estrutura_id, frase_id, obra_id, temporada, falante, palavras, destaques)"
            " VALUES (?,?,?,?,?,?,?)",
            [(estrutura_id, a[0], a[1], a[2], a[3], a[4], json.dumps(a[5])) for a in achados])
        dados.executemany(
            "INSERT OR REPLACE INTO varreduras (estrutura_id, obra_id, regra, corpus, total)"
            " VALUES (?,?,?,?,?)",
            [(estrutura_id, o, regra, corpus_v, sum(1 for a in achados if a[1] == o)) for o in pendentes])


def aquecer(estruturas=None, obras=None):
    """Pré-varre estruturas (todas do catálogo, por padrão) em todas as obras."""
    ids = _ids_obras(obras)
    nomes = estruturas or [e["id"] for e in catalogo.listar()]
    return garantir_varreduras(nomes, ids)


_AVULSAS = OrderedDict()  # (regra, obras, temporada, falante…) -> achados das últimas buscas avulsas
MEMORIA_AVULSAS = 8


def _achados_avulsos(padrao, texto, excluir, contem, obra_ids, temporada, falante, min_palavras):
    chave = (padrao, texto, excluir, repr(contem), tuple(obra_ids), temporada, (falante or "").lower(),
             min_palavras, versao_corpus())
    if chave in _AVULSAS:
        _AVULSAS.move_to_end(chave)
        return list(_AVULSAS[chave])
    rxs = _compilar(padrao, texto, excluir)
    with bancos.corpus() as con:
        achados = [(a[0], a[1], a[3], a[5]) for a in _varrer(con, *rxs, obra_ids, contem)
                   if a[4] >= min_palavras
                   and (not temporada or a[2] == int(temporada))
                   and (not falante or (a[3] or "").lower() == falante.lower())]
    _AVULSAS[chave] = achados
    while len(_AVULSAS) > MEMORIA_AVULSAS:
        _AVULSAS.popitem(last=False)
    return list(achados)


def buscar(padrao=None, texto=None, excluir=None, estrutura=None, obras=None, tipo=None,
           temporada=None, falante=None, min_palavras=4, limite=20, semente=0, filtro=None,
           por_tipo=False, pagina=1, contem=None, rotulo=None):
    """Procura frases. Com `estrutura` (nome ou id do catálogo) usa o cache; com padrão/texto
    avulsos, varre o corpus (só as frases que passam no pré-filtro `contem`, ver _linhas) e guarda
    os achados na memória. `rotulo` é o nome que vai nos resultados de uma busca avulsa.

    `filtro` refina o que já casou: fica só o achado cuja obra ou personagem contém cada palavra
    do filtro (sem acento, sem maiúsculas).

    Devolve {total, total_sem_filtro, por_obra, por_tipo, top_falantes, resultados}. `resultados` é
    uma amostra aleatória (reprodutível pela `semente`) de até `limite` frases, em ordem de episódio.
    Com `por_tipo`, são até `limite` séries, até `limite` filmes e até `limite` músicas: numa amostra só,
    as séries (muito mais frases) engoliriam o resto.

    `pagina` (a partir de 1) anda pela mesma ordem embaralhada: página 2 = os `limite` seguintes, sem
    repetir. Com `por_tipo`, é por tipo: {"serie": 2, "filme": 1}. Devolve `pagina` com as usadas.
    """
    obra_ids = _ids_obras(obras, tipo)
    if not obra_ids:
        return {"total": 0, "total_sem_filtro": 0, "por_obra": {}, "por_tipo": {}, "top_falantes": [],
                "resultados": [], "pagina": 1, "por_pagina": limite}
    nome_estrutura = rotulo

    if estrutura is not None:
        e = catalogo.obter(estrutura)
        nome_estrutura = e["nome"]
        garantir_varredura(e["id"], obra_ids)
        sql = f"""SELECT frase_id, obra_id, temporada, falante, destaques FROM ocorrencias
                  WHERE estrutura_id = ? AND obra_id IN ({','.join('?' * len(obra_ids))})
                  AND palavras >= ?"""
        args = [e["id"], *obra_ids, min_palavras]
        if temporada:
            sql += " AND temporada = ?"; args.append(int(temporada))
        if falante:
            sql += " AND falante = ? COLLATE NOCASE"; args.append(falante)
        with bancos.dados() as dados:
            achados = [(r["frase_id"], r["obra_id"], r["falante"], json.loads(r["destaques"]))
                       for r in dados.execute(sql, args)]
    else:
        if not (padrao or texto):
            raise ValueError("informe um padrão, um texto ou uma estrutura")
        achados = _achados_avulsos(padrao, texto, excluir, contem, obra_ids, temporada, falante, min_palavras)

    with bancos.corpus() as con:
        obras_corpus = con.execute("SELECT id, nome, tipo FROM obras").fetchall()
        nomes = {r["id"]: r["nome"] for r in obras_corpus}
        tipos = {r["id"]: r["tipo"] for r in obras_corpus}
        total_sem_filtro = len(achados)
        if termos := sem_acento(filtro).split():
            achados = [a for a in achados
                       if all(t in f"{sem_acento(nomes[a[1]])} {sem_acento(a[2])}" for t in termos)]
        por_obra = Counter(nomes[a[1]] for a in achados)
        por_tipo_total = Counter(tipos[a[1]] for a in achados)
        top = Counter(a[2] for a in achados if a[2]).most_common(5)
        achados.sort(key=lambda a: a[0])  # ordem fixa antes de embaralhar: as páginas não se repetem
        random.Random(semente).shuffle(achados)

        def fatia(lista, p):
            ultima = max(1, -(-len(lista) // limite)) if limite else 1
            p = min(max(1, int(p or 1)), ultima)
            return lista[(p - 1) * limite:p * limite], p

        paginas = pagina if isinstance(pagina, dict) else {}
        if por_tipo:
            amostra, usadas = [], {}
            for t in TIPOS:
                parte, usadas[t] = fatia([x for x in achados if tipos[x[1]] == t], paginas.get(t, 1))
                amostra += parte
        else:
            amostra, usadas = fatia(achados, pagina if not isinstance(pagina, dict) else 1)
        resultados = [_resultado(con, fid, d, nome_estrutura) for fid, _, _, d in amostra]
    # o arquivo desempata as músicas de um artista (todas sem temporada nem episódio)
    resultados.sort(key=lambda x: (x["obra"], x["temporada"] or 0, x["episodio"] or 0, x["arquivo"], x["_n"]))
    for x in resultados:
        del x["_n"]
    return {"total": len(achados), "total_sem_filtro": total_sem_filtro, "por_obra": dict(por_obra),
            "por_tipo": dict(por_tipo_total), "pagina": usadas, "por_pagina": limite,
            "top_falantes": [{"falante": f, "frases": n} for f, n in top],
            "resultados": resultados}


def detalhar(frase_id, estrutura=None):
    """Uma frase do corpus atual, no mesmo formato de buscar()['resultados'].

    Com `estrutura`, o destaque vem da regra dela; sem, a frase inteira fica destacada."""
    nome, destaques = None, None
    with bancos.corpus() as con:
        f = con.execute("SELECT texto, tagged, offsets FROM frases WHERE id = ?", (frase_id,)).fetchone()
        if not f:
            raise NaoEncontrado(f"frase não encontrada: {frase_id} (o corpus pode ter sido atualizado)")
        if estrutura is not None:
            e = catalogo.obter(estrutura)
            nome = e["nome"]
            rx_padrao, rx_texto, _ = _compilar(e["padrao"], e["texto"], None)
            if rx_padrao:
                destaques = casar(rx_padrao, f["tagged"], f["offsets"], f["texto"])
            elif m := rx_texto.search(f["texto"]):
                destaques = [list(m.span())]
        x = _resultado(con, frase_id, destaques or [[0, len(f["texto"])]], nome)
    del x["_n"]
    return x


def _resultado(con, frase_id, destaques, nome_estrutura):
    r = con.execute(
        """SELECT f.texto, l.n, l.falante, l.cena, l.segundo, e.id AS ep_id, e.arquivo, e.temporada,
                  e.episodio, e.episodio_fim, e.titulo, o.nome AS obra, o.tipo
           FROM frases f JOIN linhas l ON l.id = f.linha_id JOIN episodios e ON e.id = l.episodio_id
           JOIN obras o ON o.id = e.obra_id WHERE f.id = ?""", (frase_id,)).fetchone()
    vizinhas = con.execute(
        """SELECT n, falante, texto FROM linhas
           WHERE episodio_id = ? AND tipo = 'fala' AND n BETWEEN ? AND ? ORDER BY n""",
        (r["ep_id"], r["n"] - 8, r["n"] + 6)).fetchall() if r["tipo"] != "frases" else []  # frases soltas: vizinha não é contexto
    antes = [{"falante": v["falante"], "texto": v["texto"]} for v in vizinhas if v["n"] < r["n"]][-2:]
    depois = [{"falante": v["falante"], "texto": v["texto"]} for v in vizinhas if v["n"] > r["n"]][:2]
    return {
        "frase_id": frase_id, "estrutura": nome_estrutura, "_n": r["n"],
        "obra": r["obra"], "tipo": r["tipo"], "arquivo": r["arquivo"],
        "temporada": r["temporada"], "episodio": r["episodio"], "episodio_fim": r["episodio_fim"],
        "titulo": r["titulo"], "referencia": referencia(r["temporada"], r["episodio"], r["episodio_fim"], r["tipo"]),
        "segundo": r["segundo"], "tempo": tempo(r["segundo"], r["tipo"]),
        "falante": r["falante"], "frase": r["texto"], "destaques": destaques,
        "trecho": " … ".join(r["texto"][a:b] for a, b in destaques),
        "cena": r["cena"], "antes": antes, "depois": depois,
    }
