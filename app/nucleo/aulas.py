"""Aulas: pastas com as frases que a cliente guardou para uma aula, cada uma com uma nota, e a folha para
os alunos (exemplos ou exercício de completar).

As frases são as de favoritos.py (cópias, independentes dos ids do corpus); aqui fica o que é da aula.
Apagar uma aula não apaga as frases nem os textos (textos.py): eles vão para "Sem aula".
"""
from . import bancos, busca, favoritos
from .registro import NaoEncontrado


def _nome(nome):
    nome = " ".join(str(nome or "").split())
    if not nome:
        raise ValueError("Dê um nome para a aula.")
    if len(nome) > 80:
        raise ValueError("Nome de aula comprido demais (até 80 letras).")
    return nome


def listar():
    """{"aulas": [{id, nome, frases, textos}], "sem_aula": n, "sem_aula_textos": n}, as mais novas primeiro."""
    with bancos.dados() as con:
        aulas = [dict(r) for r in con.execute(
            """SELECT a.id, a.nome, a.criado_em, count(f.id) AS frases,
                      (SELECT count(*) FROM textos t WHERE t.aula_id = a.id) AS textos FROM aulas a
               LEFT JOIN favoritos f ON f.aula_id = a.id GROUP BY a.id ORDER BY a.criado_em DESC, a.id DESC""")]
        sem = con.execute("SELECT count(*) FROM favoritos WHERE aula_id IS NULL").fetchone()[0]
        sem_textos = con.execute("SELECT count(*) FROM textos WHERE aula_id IS NULL").fetchone()[0]
    return {"aulas": aulas, "sem_aula": sem, "sem_aula_textos": sem_textos}


def obter(aula_id):
    with bancos.dados() as con:
        r = con.execute("SELECT id, nome FROM aulas WHERE id = ?", (int(aula_id),)).fetchone()
    if not r:
        raise NaoEncontrado("Essa aula não existe mais.")
    return dict(r)


def criar(nome):
    nome = _nome(nome)
    with bancos.dados() as con:
        if con.execute("SELECT 1 FROM aulas WHERE nome = ?", (nome,)).fetchone():
            raise ValueError(f"Já existe uma aula chamada “{nome}”.")
        novo = con.execute("INSERT INTO aulas (nome) VALUES (?)", (nome,)).lastrowid
    return obter(novo)


def renomear(aula_id, nome):
    nome = _nome(nome)
    obter(aula_id)
    with bancos.dados() as con:
        if con.execute("SELECT 1 FROM aulas WHERE nome = ? AND id != ?", (nome, int(aula_id))).fetchone():
            raise ValueError(f"Já existe uma aula chamada “{nome}”.")
        con.execute("UPDATE aulas SET nome = ? WHERE id = ?", (nome, int(aula_id)))
    return obter(aula_id)


def apagar(aula_id):
    """As frases e os textos da aula vão para "Sem aula"."""
    with bancos.dados() as con:
        con.execute("UPDATE favoritos SET aula_id = NULL WHERE aula_id = ?", (int(aula_id),))
        con.execute("UPDATE textos SET aula_id = NULL WHERE aula_id = ?", (int(aula_id),))
        con.execute("DELETE FROM aulas WHERE id = ?", (int(aula_id),))


def frases(aula_id=None):
    """As frases de uma aula (ou as sem aula, com None), na ordem em que foram guardadas."""
    if aula_id is not None:
        obter(aula_id)
    sql = "SELECT * FROM favoritos WHERE " + ("aula_id = ?" if aula_id is not None else "aula_id IS NULL")
    tipos = busca.tipos_das_obras()
    with bancos.dados() as con:
        return [favoritos._dict(r, tipos) for r in con.execute(sql + " ORDER BY criado_em, id",
                                                         [int(aula_id)] if aula_id is not None else [])]


def mover(frase_id, aula_id=None):
    if aula_id is not None:
        obter(aula_id)
    with bancos.dados() as con:
        con.execute("UPDATE favoritos SET aula_id = ? WHERE id = ?",
                    (int(aula_id) if aula_id is not None else None, int(frase_id)))


def anotar(frase_id, nota):
    nota = str(nota or "").strip()[:2000] or None
    with bancos.dados() as con:
        con.execute("UPDATE favoritos SET nota = ? WHERE id = ?", (nota, int(frase_id)))


def _dicas(frase, destaques, arquivo):
    """Para cada trecho destacado, a forma básica do último verbo dele (had lost -> lose), tirada do
    corpus; None se a frase não estiver mais no corpus ou o trecho não tiver verbo. A mesma frase pode
    aparecer mais de uma vez no episódio, com etiquetas diferentes: vale a primeira que tem verbo."""
    with bancos.corpus() as con:
        linhas = busca.frases_do_episodio(con, arquivo, frase, "f.tagged, f.offsets")
    dicas = [None] * len(destaques)
    for r in linhas:
        tokens = [t.rsplit("/", 2) for t in r["tagged"].split()]
        inicios = [int(o) for o in r["offsets"].split()]
        for i, (ini, fim) in enumerate(destaques):
            verbos = [lema for (palavra, lema, tag), pos in zip(tokens, inicios)
                      if ini <= pos < fim and tag.startswith("VB")]
            if dicas[i] is None and verbos:
                dicas[i] = verbos[-1]
    return dicas


def folha(aula_id=None):
    """As frases da aula com o que a folha precisa: {aula, itens: [{…frase, dicas: [...]}]}."""
    aula = obter(aula_id) if aula_id is not None else {"id": None, "nome": "Sem aula"}
    itens = frases(aula_id)
    for x in itens:
        x["dicas"] = _dicas(x["frase"], x["destaques"], x["arquivo"])
    return {"aula": aula, "itens": itens}
