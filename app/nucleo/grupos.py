"""Grupos de obras, para buscar em várias de uma vez.

- Prontos: tabela `grupos` do corpus.db, gravada pelo indexador a partir de ferramentas/grupos.json.
  Vêm e vão junto com o corpus.
- Da cliente: `meus_grupos` + `meus_grupos_obras` no dados.db. Guardam a pasta da obra, não o id, porque
  os ids mudam toda vez que o corpus é refeito.
"""
import sqlite3
import unicodedata

from . import bancos


def sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or ""))
                   if unicodedata.category(c) != "Mn").lower()


def _prontos(con):
    try:
        linhas = con.execute("SELECT nome, obra_id FROM grupos ORDER BY ordem, rowid").fetchall()
    except sqlite3.OperationalError:  # corpus de antes dos grupos
        return []
    grupos = {}
    for r in linhas:
        grupos.setdefault(r["nome"], []).append(r["obra_id"])
    return [{"id": None, "nome": nome, "meu": False, "obras": ids} for nome, ids in grupos.items()]


def listar():
    """Os da cliente primeiro (por nome), depois os prontos. `obras` são ids do corpus atual; obra que
    saiu do corpus some do grupo sem erro."""
    with bancos.corpus() as con:
        por_pasta = {r["pasta"]: r["id"] for r in con.execute("SELECT pasta, id FROM obras")}
        prontos = _prontos(con)
    with bancos.dados() as con:
        meus = {}
        for r in con.execute("""SELECT g.id, g.nome, o.pasta FROM meus_grupos g
                                LEFT JOIN meus_grupos_obras o ON o.grupo_id = g.id
                                ORDER BY g.nome COLLATE NOCASE, o.rowid"""):
            g = meus.setdefault(r["id"], {"id": r["id"], "nome": r["nome"], "meu": True, "obras": []})
            if r["pasta"] in por_pasta:
                g["obras"].append(por_pasta[r["pasta"]])
    return [*meus.values(), *prontos]


def por_nome():
    """{nome em minúsculas: [ids]}; se um grupo da cliente tiver o nome de um pronto, vale o da cliente."""
    resultado = {}
    for g in reversed(listar()):
        resultado[g["nome"].lower()] = g["obras"]
    return resultado


def criar(nome, obras):
    """`obras`: ids do corpus atual. Devolve o id do grupo."""
    nome = " ".join(str(nome or "").split())
    if not nome:
        raise ValueError("Dê um nome ao grupo.")
    with bancos.corpus() as con:
        obras_corpus = {r["id"]: (r["pasta"], r["nome"]) for r in con.execute("SELECT id, pasta, nome FROM obras")}
        prontos = _prontos(con)
    ocupados = {n.lower() for _, n in obras_corpus.values()} | {g["nome"].lower() for g in prontos}
    if nome.lower() in ocupados:
        raise ValueError(f"Já existe uma obra ou um grupo pronto chamado “{nome}”.")
    pastas = list(dict.fromkeys(obras_corpus[int(i)][0] for i in obras if int(i) in obras_corpus))
    if len(pastas) < 2:
        raise ValueError("Um grupo precisa de pelo menos duas obras.")
    with bancos.dados() as con:
        try:
            gid = con.execute("INSERT INTO meus_grupos (nome) VALUES (?)", (nome,)).lastrowid
        except sqlite3.IntegrityError:
            raise ValueError(f"Você já tem um grupo chamado “{nome}”.") from None
        con.executemany("INSERT INTO meus_grupos_obras (grupo_id, pasta) VALUES (?,?)",
                        [(gid, p) for p in pastas])
    return gid


def apagar(grupo_id):
    with bancos.dados() as con:
        con.execute("DELETE FROM meus_grupos WHERE id = ?", (int(grupo_id),))
