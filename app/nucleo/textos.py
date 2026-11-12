"""Textos: o que a cliente escreve para ler em voz alta e salvar o áudio (audio.py), numa aula ou em "Sem aula".

O título não precisa ser único: o arquivo de áudio nunca sobrescreve outro ("nome (2).mp3"). Apagar a aula
não apaga o texto: ele vai para "Sem aula", como as frases.
"""
from . import aulas, bancos
from .registro import NaoEncontrado

LIMITE = 20000  # uns 20 minutos de leitura

_TODAS = object()


def _titulo(titulo):
    titulo = " ".join(str(titulo or "").split())
    if not titulo:
        raise ValueError("Dê um título para o texto.")
    if len(titulo) > 120:
        raise ValueError("Título comprido demais (até 120 letras).")
    return titulo


def _corpo(corpo):
    """Do jeito que a cliente escreveu (parágrafos e linhas em branco ficam), sem espaço sobrando no começo e no fim."""
    corpo = str(corpo or "").replace("\r\n", "\n").strip()
    if len(corpo) > LIMITE:
        raise ValueError(f"Texto comprido demais (até {LIMITE:,} letras).".replace(",", "."))
    return corpo


def _aula(aula_id):
    if aula_id is None or aula_id == "":
        return None
    return aulas.obter(aula_id)["id"]


_CAMPOS = """t.id, t.titulo, t.aula_id, a.nome AS aula, t.criado_em, t.atualizado_em"""


def obter(texto_id):
    with bancos.dados() as con:
        r = con.execute(f"SELECT {_CAMPOS}, t.corpo FROM textos t LEFT JOIN aulas a ON a.id = t.aula_id "
                        "WHERE t.id = ?", (int(texto_id),)).fetchone()
    if not r:
        raise NaoEncontrado("Esse texto não existe mais.")
    return dict(r)


def listar(aula_id=_TODAS):
    """Sem o corpo, com o começo dele (`comeco`), os editados por último primeiro. Com `aula_id`, só os
    daquela aula; com None, só os de "Sem aula"."""
    sql = (f"SELECT {_CAMPOS}, substr(t.corpo, 1, 200) AS comeco FROM textos t "
           "LEFT JOIN aulas a ON a.id = t.aula_id")
    parametros = []
    if aula_id is None:
        sql += " WHERE t.aula_id IS NULL"
    elif aula_id is not _TODAS:
        sql += " WHERE t.aula_id = ?"
        parametros.append(int(aula_id))
    with bancos.dados() as con:
        lista = [dict(r) for r in con.execute(sql + " ORDER BY t.atualizado_em DESC, t.id DESC", parametros)]
    for x in lista:
        x["comeco"] = " ".join(x["comeco"].split())[:120]
    return lista


def criar(titulo, corpo, aula_id=None):
    titulo, corpo, aula_id = _titulo(titulo), _corpo(corpo), _aula(aula_id)
    with bancos.dados() as con:
        novo = con.execute("INSERT INTO textos (titulo, corpo, aula_id) VALUES (?, ?, ?)",
                           (titulo, corpo, aula_id)).lastrowid
    return obter(novo)


def salvar(texto_id, titulo, corpo, aula_id=None):
    titulo, corpo, aula_id = _titulo(titulo), _corpo(corpo), _aula(aula_id)
    obter(texto_id)
    with bancos.dados() as con:
        con.execute("""UPDATE textos SET titulo = ?, corpo = ?, aula_id = ?,
                       atualizado_em = datetime('now', 'localtime') WHERE id = ?""",
                    (titulo, corpo, aula_id, int(texto_id)))
    return obter(texto_id)


def apagar(texto_id):
    with bancos.dados() as con:
        con.execute("DELETE FROM textos WHERE id = ?", (int(texto_id),))
