"""Catálogo de estruturas gramaticais (dados.db).

A regra de busca de uma estrutura é o padrão (+ texto/excluir). Quem monta com peças (janela)
manda `blocos`, e o padrão e a exclusão saem deles; quem escreve o padrão direto (Claude, campo
avançado) desliga as peças.
"""
import json
import re
import threading
from contextlib import contextmanager
from pathlib import Path

from . import bancos, blocos
from .grupos import sem_acento
from .padrao import compilar
from .registro import NaoEncontrado, log

SEMENTE = Path(__file__).resolve().parent / "semente_estruturas.json"
CAMPOS = ("nome", "categoria", "nivel", "explicacao", "formula", "padrao", "texto", "excluir",
          "exemplos", "pegadinhas", "blocos", "origem")
REGRA_MANUAL = ("padrao", "texto", "excluir")


def _dict(row):
    d = dict(row)
    d["exemplos"] = json.loads(d["exemplos"] or "[]")
    d["blocos"] = json.loads(d["blocos"]) if d.get("blocos") else None
    d["regra_em_portugues"] = blocos.descrever(d["blocos"]["pecas"]) if d["blocos"] else None
    return d


def _aplicar_blocos(dados):
    """Com `blocos` (peças), o padrão e a exclusão são gerados deles e o texto (regex) sai.
    `blocos` vazio desliga as peças e vale a regra manual."""
    if "blocos" not in dados:
        return dados
    b = dados["blocos"]
    if isinstance(b, str):
        b = json.loads(b) if b.strip() else None
    if isinstance(b, list):
        b = {"pecas": b}
    pecas = (b or {}).get("pecas") or []
    if not pecas:
        dados["blocos"] = None
        return dados
    excluir = [str(x).strip() for x in (b.get("excluir") or []) if str(x).strip()]
    dados.update(padrao=blocos.para_padrao(pecas), excluir=blocos.para_excluir(excluir), texto=None,
                 blocos=json.dumps({"pecas": pecas, "excluir": excluir}, ensure_ascii=False))
    return dados


def regra(dados):
    """(padrao, texto, excluir) que valeriam para esses dados, sem salvar: para o "Testar"."""
    d = _aplicar_blocos({k: dados.get(k) for k in (*REGRA_MANUAL, "blocos") if k in dados})
    _validar(d)
    return d.get("padrao"), d.get("texto"), d.get("excluir")


def _validar(dados):
    if not (dados.get("padrao") or dados.get("texto")):
        raise ValueError("Monte a regra com as peças (ou preencha a regra avançada).")
    if dados.get("padrao"):
        compilar(dados["padrao"])
    for campo in ("texto", "excluir"):
        if dados.get(campo):
            try:
                re.compile(dados[campo])
            except re.error as e:
                raise ValueError(f"regex inválida em {campo}: {e}") from e


def _regra_marcador(r):
    """Regra que não procura nada de verdade: sem padrão e com um texto sem letras (o "-" que a cliente
    pôs porque o formulário exigia alguma coisa)."""
    return not r["padrao"] and not r["blocos"] and not re.search(r"[A-Za-z]", r["texto"] or "")


def _da_semente(s):
    e = _aplicar_blocos({k: v for k, v in s.items() if k in CAMPOS})
    for c in CAMPOS:
        e.setdefault(c, None)
    e.update(origem="semente", exemplos=json.dumps(s.get("exemplos", []), ensure_ascii=False))
    _validar(e)
    return e


def sincronizar_semente(con):
    """Traz o catálogo de fábrica desta versão para o banco sem estragar o que é da cliente:
    - estrutura de fábrica nova entra (a não ser que a cliente já tenha apagado essa antes);
    - a de fábrica que a cliente nunca editou (origem "semente"; editar vira "semente_editada") é
      atualizada (regra melhorada numa versão nova);
    - a da cliente com o mesmo nome fica como está; só se a regra for um marcador sem letras ("-")
      ela recebe a regra de fábrica."""
    aplicadas = {r[0].lower() for r in con.execute("SELECT nome FROM sementes_aplicadas")}
    atuais = {r["nome"].lower(): r for r in con.execute("SELECT * FROM estruturas")}
    for s in json.loads(SEMENTE.read_text(encoding="utf-8")):
        try:
            e = _da_semente(s)
        except ValueError:
            log.exception("estrutura de fábrica com regra inválida: %s", s.get("nome"))
            continue
        atual = atuais.get(s["nome"].lower())
        if atual is None:
            if s["nome"].lower() not in aplicadas:
                cols = [c for c in CAMPOS if e[c] is not None]
                con.execute(f"INSERT INTO estruturas ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                            [e[c] for c in cols])
        elif atual["origem"] == "semente" and atual["atualizado_em"] == atual["criado_em"]:
            mudou = [c for c in CAMPOS if c not in ("nome", "origem") and atual[c] != e[c]]
            if mudou:  # sem mexer em atualizado_em: continua contando como "não editada pela cliente"
                con.execute(f"UPDATE estruturas SET {', '.join(f'{c} = ?' for c in mudou)} WHERE id = ?",
                            [*(e[c] for c in mudou), atual["id"]])
        elif _regra_marcador(atual):
            vazios = [c for c in ("categoria", "nivel", "explicacao", "formula", "pegadinhas") if not atual[c]]
            if atual["exemplos"] in (None, "", "[]"):
                vazios.append("exemplos")
            cols = ["padrao", "texto", "excluir", "blocos", *vazios]
            con.execute(f"UPDATE estruturas SET {', '.join(f'{c} = ?' for c in cols)},"
                        " atualizado_em = datetime('now', 'localtime') WHERE id = ?",
                        [*(e[c] for c in cols), atual["id"]])
            log.info("regra de fábrica aplicada na estrutura da cliente: %s", atual["nome"])
        con.execute("INSERT OR IGNORE INTO sementes_aplicadas (nome) VALUES (?)", (s["nome"],))
    con.commit()


def _chave(categoria):
    return " ".join(sem_acento(categoria).split())


def _unificar_categorias(con):
    """Junta categorias que só diferem em maiúsculas, acentos ou espaços ("Tempos Verbais" e
    "Tempos verbais"): fica a grafia da semente, senão a mais usada."""
    grafias = {}
    for r in con.execute("""SELECT categoria, max(origem = 'semente') AS semente, count(*) AS n
                            FROM estruturas WHERE categoria IS NOT NULL GROUP BY categoria"""):
        grafias.setdefault(_chave(r["categoria"]), []).append((r["semente"], r["n"], r["categoria"]))
    for opcoes in grafias.values():
        if len(opcoes) > 1:
            certa = max(opcoes)[2]
            con.executemany("UPDATE estruturas SET categoria = ? WHERE categoria = ?",
                            [(certa, g) for _, _, g in opcoes if g != certa])


def _categoria_existente(con, categoria):
    """A grafia já usada para essa categoria, se houver; senão a digitada, sem espaços sobrando."""
    categoria = " ".join(str(categoria or "").split()) or None
    if categoria:
        for (existente,) in con.execute("SELECT DISTINCT categoria FROM estruturas WHERE categoria IS NOT NULL"):
            if _chave(existente) == _chave(categoria):
                return existente
    return categoria


_prontos = set()  # bancos já sincronizados com a semente neste processo
_sincronizando = threading.Lock()  # a tela e a thread que prepara o cache abrem ao mesmo tempo


@contextmanager
def _abrir():
    with bancos.dados() as con:
        caminho = str(bancos.caminho_dados())
        if caminho not in _prontos:
            with _sincronizando:
                if caminho not in _prontos:
                    sincronizar_semente(con)
                    _unificar_categorias(con)
                    _prontos.add(caminho)
        yield con


def listar():
    with _abrir() as con:
        return [_dict(r) for r in con.execute(
            "SELECT * FROM estruturas ORDER BY categoria, nivel, nome")]


def obter(estrutura):
    """Por id ou nome (sem distinção de maiúsculas)."""
    with _abrir() as con:
        if isinstance(estrutura, int) or str(estrutura).isdigit():
            r = con.execute("SELECT * FROM estruturas WHERE id = ?", (int(estrutura),)).fetchone()
        else:
            r = con.execute("SELECT * FROM estruturas WHERE nome = ?", (str(estrutura),)).fetchone()
    if not r:
        raise NaoEncontrado(f"estrutura não encontrada: {estrutura!r}")
    return _dict(r)


def criar(**dados):
    dados = _aplicar_blocos(dict(dados))
    _validar(dados)
    dados.setdefault("origem", "usuario")
    dados["exemplos"] = json.dumps(dados.get("exemplos") or [], ensure_ascii=False)
    cols = [c for c in CAMPOS if c in dados]
    with _abrir() as con:
        if "categoria" in dados:
            dados["categoria"] = _categoria_existente(con, dados["categoria"])
        novo_id = con.execute(
            f"INSERT INTO estruturas ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            [dados[c] for c in cols]).lastrowid
    return obter(novo_id)


def editar(estrutura, **mudancas):
    atual = obter(estrutura)
    mudancas = {k: v for k, v in mudancas.items() if k in CAMPOS and k != "origem"}
    if "blocos" in mudancas:
        _aplicar_blocos(mudancas)
    elif any(k in mudancas for k in REGRA_MANUAL):
        mudancas["blocos"] = None  # regra escrita à mão (Claude, avançado): as peças não valem mais
    _validar({**atual, **mudancas})
    if mudancas and atual["origem"] == "semente":
        mudancas["origem"] = "semente_editada"  # daqui em diante a atualização de fábrica não mexe nela
    if "exemplos" in mudancas:
        mudancas["exemplos"] = json.dumps(mudancas["exemplos"] or [], ensure_ascii=False)
    if mudancas:
        sets = ", ".join(f"{k} = ?" for k in mudancas)
        with _abrir() as con:
            if "categoria" in mudancas:
                mudancas["categoria"] = _categoria_existente(con, mudancas["categoria"])
            con.execute(f"UPDATE estruturas SET {sets}, atualizado_em = datetime('now', 'localtime')"
                        " WHERE id = ?", [*mudancas.values(), atual["id"]])
    return obter(atual["id"])


def apagar(estrutura):
    atual = obter(estrutura)
    with _abrir() as con:
        con.execute("DELETE FROM estruturas WHERE id = ?", (atual["id"],))
    return atual


def marcar_falso_positivo(estrutura, arquivo, frase, frase_id=None):
    """Some das buscas seguintes. Com `frase_id`, sai do cache na hora; sem ele, o cache da
    estrutura é descartado e refeito na próxima busca."""
    e = obter(estrutura)
    with _abrir() as con:
        con.execute("INSERT OR IGNORE INTO falsos_positivos (estrutura_id, arquivo, frase) VALUES (?,?,?)",
                    (e["id"], arquivo, frase))
        if frase_id is not None:
            con.execute("DELETE FROM ocorrencias WHERE estrutura_id = ? AND frase_id = ?", (e["id"], frase_id))
        else:
            con.execute("DELETE FROM varreduras WHERE estrutura_id = ?", (e["id"],))


def falsos_positivos(estrutura_id):
    with _abrir() as con:
        return {(r["arquivo"], r["frase"]) for r in con.execute(
            "SELECT arquivo, frase FROM falsos_positivos WHERE estrutura_id = ?", (estrutura_id,))}
