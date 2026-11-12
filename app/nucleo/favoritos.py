"""Frases guardadas (desde a 1.4, nas aulas: ver aulas.py): cópias das frases, independentes dos ids do
corpus. `aula_id` vazio = "Sem aula"."""
import json

from . import bancos
from .busca import referencia, tempo, tipos_das_obras
from .registro import NaoEncontrado

CAMPOS = ("estrutura", "obra", "temporada", "episodio", "episodio_fim", "titulo", "segundo",
          "falante", "frase", "destaques", "cena", "antes", "depois", "arquivo", "nota", "aula_id")
JSON = ("destaques", "antes", "depois")


def _dict(row, tipos):
    """`tipos`: busca.tipos_das_obras() (a frase guardada não tem o tipo da obra)."""
    d = dict(row)
    for c in JSON:
        d[c] = json.loads(d[c] or "[]")
    d["tipo"] = tipos.get(d["obra"])
    d["referencia"] = referencia(d["temporada"], d["episodio"], d["episodio_fim"], d["tipo"])
    d["tempo"] = tempo(d["segundo"], d["tipo"])
    return d


def guardar(resultado, nota=None, aula_id=None):
    """Recebe um item de busca.buscar()['resultados']. Já guardada: vai para a `aula_id` (e a nota nova,
    se vier)."""
    dados = {c: resultado.get(c) for c in CAMPOS}
    dados["nota"] = nota
    dados["aula_id"] = aula_id
    for c in JSON:
        dados[c] = json.dumps(dados[c] or [], ensure_ascii=False)
    with bancos.dados() as con:
        if aula_id is not None and not con.execute("SELECT 1 FROM aulas WHERE id = ?", (int(aula_id),)).fetchone():
            raise NaoEncontrado("Essa aula não existe mais (foi apagada em outra janela?). Escolha outra em "
                                "“Guardar frases na aula”.")
        cur = con.execute(
            f"INSERT INTO favoritos ({','.join(CAMPOS)}) VALUES ({','.join('?' * len(CAMPOS))})"
            " ON CONFLICT (arquivo, frase) DO UPDATE SET nota = coalesce(excluded.nota, nota), aula_id = excluded.aula_id"
            " RETURNING id", [dados[c] for c in CAMPOS])
        return cur.fetchone()[0]


SEM_AULA = "sem"  # listar(aula=SEM_AULA): só as que não estão em aula nenhuma


def listar(estrutura=None, aula=None):
    """`aula`: id de uma aula, SEM_AULA ou None (todas)."""
    sql, condicoes, args = "SELECT * FROM favoritos", [], []
    if estrutura:
        condicoes.append("estrutura = ? COLLATE NOCASE"); args.append(estrutura)
    if aula == SEM_AULA:
        condicoes.append("aula_id IS NULL")
    elif aula is not None:
        condicoes.append("aula_id = ?"); args.append(int(aula))
    if condicoes:
        sql += " WHERE " + " AND ".join(condicoes)
    tipos = tipos_das_obras()
    with bancos.dados() as con:
        return [_dict(r, tipos) for r in con.execute(sql + " ORDER BY estrutura, criado_em DESC", args)]


def remover(favorito_id):
    with bancos.dados() as con:
        con.execute("DELETE FROM favoritos WHERE id = ?", (favorito_id,))

