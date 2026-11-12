"""Confere as aulas (app/nucleo/aulas.py) com o corpus de verdade e um dados.db de teste: criar, guardar,
mover, anotar, a folha com as dicas, apagar (as frases vão para "Sem aula") e as migrações do dados.db
(um banco da 1.0 até a versão atual, com a cópia de antes; um banco novo, sem cópia).

Uso: app/.venv/bin/python -I ferramentas/testar_aulas.py
"""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

DADOS = Path(tempfile.mkdtemp(prefix="sitcomatica-aulas-")) / "dados.db"
os.environ["FRASES_DADOS"] = str(DADOS)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
from nucleo import aulas, bancos, busca, favoritos  # noqa: E402

falhas = []


def caso(nome, cond, detalhe=""):
    print(("ok  " if cond else "ERRO"), nome, detalhe)
    if not cond:
        falhas.append(nome)


def erro(fn, *args):
    try:
        fn(*args)
    except ValueError as e:
        return str(e)
    return None


# um dados.db "da 1.0": estruturas sem blocos, favoritos sem aula_id, uma estrutura da cliente e uma frase guardada
sqlite3.connect(DADOS).executescript("""
    CREATE TABLE estruturas (id INTEGER PRIMARY KEY, nome TEXT NOT NULL UNIQUE COLLATE NOCASE,
      categoria TEXT, nivel TEXT, explicacao TEXT, formula TEXT, padrao TEXT, texto TEXT, excluir TEXT,
      exemplos TEXT NOT NULL DEFAULT '[]', pegadinhas TEXT, origem TEXT NOT NULL DEFAULT 'usuario',
      criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
      atualizado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
      CHECK (padrao IS NOT NULL OR texto IS NOT NULL));
    INSERT INTO estruturas (nome, padrao) VALUES ('Minha estrutura velha', '[l=wish]');
    CREATE TABLE favoritos (id INTEGER PRIMARY KEY, estrutura TEXT, obra TEXT, temporada INTEGER,
      episodio INTEGER, episodio_fim INTEGER, titulo TEXT, segundo REAL, falante TEXT, frase TEXT NOT NULL,
      destaques TEXT NOT NULL DEFAULT '[]', cena TEXT, antes TEXT NOT NULL DEFAULT '[]',
      depois TEXT NOT NULL DEFAULT '[]', arquivo TEXT, nota TEXT,
      criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')), UNIQUE (arquivo, frase));
    INSERT INTO favoritos (frase, arquivo) VALUES ('frase velha', 'x.txt');
""")
caso("migração: a frase de antes fica em Sem aula", aulas.listar()["sem_aula"] == 1)
with sqlite3.connect(DADOS) as con:
    versao = con.execute("PRAGMA user_version").fetchone()[0]
    colunas = {r[1] for r in con.execute("PRAGMA table_info(estruturas)")}
    velha = con.execute("SELECT count(*) FROM estruturas WHERE nome = 'Minha estrutura velha'").fetchone()[0]
caso("migração: banco na versão atual", versao == bancos.VERSAO_DADOS, f"user_version {versao}")
caso("migração: estruturas ganhou blocos e a da cliente continua", "blocos" in colunas and velha == 1)
copias = sorted((DADOS.parent / "backups").glob("migracao-v*.db"))
caso("migração: cópia de antes guardada", len(copias) == 1, copias[0].name if copias else "nenhuma")
with sqlite3.connect(copias[0]) as con:
    antes = {r[1] for r in con.execute("PRAGMA table_info(favoritos)")}
    frase = con.execute("SELECT frase FROM favoritos").fetchone()[0]
caso("migração: a cópia é o banco de antes, intacto", "aula_id" not in antes and frase == "frase velha")
caso("migração: abrir de novo não migra outra vez", bancos.preparar_dados() == [])
novo = DADOS.parent / "novo" / "dados.db"
feitas = bancos.preparar_dados(novo)
with sqlite3.connect(novo) as con:
    versao_novo = con.execute("PRAGMA user_version").fetchone()[0]
# uma migração que quebra no meio: nada fica pela metade (nem a versão sobe)
def _quebra(con):
    con.execute("ALTER TABLE aulas ADD COLUMN cor TEXT")
    raise RuntimeError("quebrou no meio")


bancos.MIGRACOES.append((99, "teste que quebra", _quebra))
try:
    bancos.preparar_dados()
    quebrou = False
except RuntimeError:
    quebrou = True
bancos.MIGRACOES.pop()
with sqlite3.connect(DADOS) as con:
    versao = con.execute("PRAGMA user_version").fetchone()[0]
    cor = "cor" in {r[1] for r in con.execute("PRAGMA table_info(aulas)")}
caso("migração que quebra desfaz tudo", quebrou and versao == bancos.VERSAO_DADOS and not cor,
     f"user_version {versao}, coluna nova: {cor}")
# uma cópia de antes que ficou pela metade (disco cheio, app caiu) não vale: é refeita antes de migrar
outro = DADOS.parent / "outro" / "dados.db"
outro.parent.mkdir()
with sqlite3.connect(DADOS) as origem, sqlite3.connect(outro) as copia:
    origem.backup(copia)
(outro.parent / "backups").mkdir()
pela_metade = outro.parent / "backups" / f"migracao-v98-{__import__('datetime').date.today():%Y-%m-%d}.db"
pela_metade.write_bytes(b"")
bancos.MIGRACOES.append((98, "teste que não muda nada", lambda con: None))
try:
    bancos.preparar_dados(outro)
finally:
    bancos.MIGRACOES.pop()
caso("cópia de antes pela metade é refeita", bancos._copia_boa(pela_metade), f"{pela_metade.stat().st_size} bytes")
caso("banco novo nasce na versão atual, sem cópia",
     versao_novo == bancos.VERSAO_DADOS and not (novo.parent / "backups").exists(), str(feitas))

r = busca.buscar(estrutura="Past perfect", limite=3)["resultados"]
a = aulas.criar("  Aula 3   present perfect ")
caso("criar aula (nome limpo)", a["nome"] == "Aula 3 present perfect", a["nome"])
caso("nome repetido dá erro", "Já existe" in (erro(aulas.criar, "aula 3 PRESENT perfect") or ""))
caso("nome vazio dá erro", erro(aulas.criar, "   ") is not None)

for x in r:
    favoritos.guardar(x, aula_id=a["id"])
caso("guardar na aula", len(aulas.frases(a["id"])) == 3)
favoritos.guardar(r[0], aula_id=None)
caso("guardar de novo muda de aula", len(aulas.frases(a["id"])) == 2 and aulas.listar()["sem_aula"] == 2)
aulas.mover(aulas.frases(None)[-1]["id"], a["id"])
caso("mover para a aula", len(aulas.frases(a["id"])) == 3)

f = aulas.frases(a["id"])[0]
aulas.anotar(f["id"], "  usar no começo  ")
caso("nota", aulas.frases(a["id"])[0]["nota"] == "usar no começo")

folha = aulas.folha(a["id"])
dicas = [d for x in folha["itens"] for d in x["dicas"]]
caso("folha: uma dica por trecho", all(len(x["dicas"]) == len(x["destaques"]) for x in folha["itens"]))
caso("folha: dicas na forma básica", dicas and all(d is None or d.isalpha() and d == d.lower() for d in dicas), str(dicas))
caso("folha de past perfect não dá 'have' como dica", "have" not in dicas, str(dicas))

b = aulas.renomear(a["id"], "Aula 4")
caso("renomear", b["nome"] == "Aula 4")
aulas.apagar(a["id"])
caso("apagar a aula manda as frases para Sem aula", aulas.listar() == {"aulas": [], "sem_aula": 4, "sem_aula_textos": 0})

print(f"\n{'tudo certo' if not falhas else f'{len(falhas)} falha(s)'}")
sys.exit(1 if falhas else 0)
