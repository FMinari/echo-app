"""Confere o interruptor "Acervo livre" (nucleo/bancos.py) com dois bancos de mentira: qual banco a busca usa
com um, com outro e com os dois, a escolha guardada, a junção (ids do próprio iguais, os do acervo
deslocados, cache de fábrica só das regras dos dois) e o acervo.db.gz descompactado na primeira vez.

Uso: python3 -I ferramentas/testar_acervo.py
"""
import gzip
import importlib
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="echo-acervo-"))
os.environ["FRASES_DADOS"] = str(TMP / "dados" / "dados.db")
os.environ.pop("FRASES_CORPUS", None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
from nucleo import bancos  # noqa: E402

falhas = []


def caso(nome, cond, detalhe=""):
    print(("ok  " if cond else "ERRO"), nome, detalhe)
    if not cond:
        falhas.append(nome)


def banco(caminho, versao, obras, regras):
    """obras: [(nome, tipo, [frases])]; regras: {regra: [índice da frase achada]}."""
    con = sqlite3.connect(caminho)
    con.executescript("""
        CREATE TABLE meta (chave TEXT PRIMARY KEY, valor TEXT);
        CREATE TABLE obras (id INTEGER PRIMARY KEY, nome TEXT,
            tipo TEXT CHECK (tipo IN ('serie', 'filme', 'musica')), ano INTEGER, pasta TEXT);
        CREATE TABLE episodios (id INTEGER PRIMARY KEY, obra_id INTEGER, temporada INTEGER, episodio INTEGER,
            episodio_fim INTEGER, titulo TEXT, arquivo TEXT, duracao_min REAL, palavras INTEGER);
        CREATE TABLE linhas (id INTEGER PRIMARY KEY, episodio_id INTEGER, n INTEGER, tipo TEXT, falante TEXT,
            texto TEXT, cena TEXT, segundo REAL);
        CREATE TABLE frases (id INTEGER PRIMARY KEY, linha_id INTEGER, texto TEXT, tagged TEXT, offsets TEXT);
        CREATE TABLE grupos (nome TEXT, ordem INTEGER, obra_id INTEGER);
        CREATE TABLE fabrica_regras (regra TEXT PRIMARY KEY, nome TEXT, total INTEGER);
        CREATE TABLE fabrica_ocorrencias (regra TEXT, frase_id INTEGER, obra_id INTEGER, temporada INTEGER,
            falante TEXT, palavras INTEGER, destaques TEXT);""")
    con.execute("INSERT INTO meta VALUES ('versao', ?), ('gerado_em', '2026-11-12 10:00:00')", (versao,))
    con.execute("PRAGMA ignore_check_constraints = ON")  # o acervo tem tipo "livro"
    frases = []
    for nome, tipo, textos in obras:
        o = con.execute("INSERT INTO obras (nome, tipo, pasta) VALUES (?,?,?)", (nome, tipo, nome.lower())).lastrowid
        e = con.execute("INSERT INTO episodios (obra_id, arquivo) VALUES (?,?)", (o, f"{nome}/1.txt")).lastrowid
        con.execute("INSERT INTO grupos VALUES (?, 0, ?)", (f"Grupo {nome}", o))
        for n, texto in enumerate(textos):
            li = con.execute("INSERT INTO linhas (episodio_id, n, tipo, texto) VALUES (?,?,'fala',?)", (e, n, texto)).lastrowid
            frases.append((con.execute("INSERT INTO frases (linha_id, texto) VALUES (?,?)", (li, texto)).lastrowid, o))
    for regra, achadas in regras.items():
        con.execute("INSERT INTO fabrica_regras VALUES (?, ?, ?)", (regra, regra, len(achadas)))
        con.executemany("INSERT INTO fabrica_ocorrencias VALUES (?,?,?,NULL,NULL,3,'[]')",
                        [(regra, frases[i][0], frases[i][1]) for i in achadas])
    con.commit()
    con.close()


APP = TMP / "repo" / "app"
APP.mkdir(parents=True)
bancos.APP = APP  # o "repositório" de mentira: app/ e a pasta de cima
proprio, acervo = APP.parent / "corpus.db", APP.parent / "acervo.db"
banco(proprio, "p1", [("Minha Série", "serie", ["I had gone.", "She has seen it."])], {"r1": [0], "r2": [1]})
banco(TMP / "acervo-fonte.db", "a1", [("Emma", "livro", ["He had left.", "They will go.", "I was there."])],
      {"r1": [0, 2], "r3": [1]})

# só o acervo, compactado (como vem no repositório público)
with open(TMP / "acervo-fonte.db", "rb") as f, gzip.open(APP.parent / "acervo.db.gz", "wb") as z:
    shutil.copyfileobj(f, z)
proprio_guardado = proprio.rename(TMP / "proprio.db")
caso("só o acervo: descompacta e usa ele", bancos.caminho_corpus() == acervo and acervo.exists())
caso("só o acervo: sem interruptor", bancos.estado_acervo()["disponivel"] is False)

# os dois: começa ligado e usa o combinado
proprio_guardado.rename(proprio)
caso("os dois: interruptor aparece, ligado", bancos.estado_acervo() == {"disponivel": True, "ligado": True})
combinado = bancos.caminho_corpus()
caso("ligado: busca no combinado", combinado.name == "combinado.db", str(combinado))
con = sqlite3.connect(combinado)
obras = con.execute("SELECT id, nome FROM obras ORDER BY id").fetchall()
caso("combinado tem as obras dos dois", [n for _, n in obras] == ["Minha Série", "Emma"], str(obras))
caso("ids do próprio não mudam", con.execute("SELECT id FROM frases WHERE texto = 'I had gone.'").fetchone()[0] == 1)
caso("ids do acervo deslocados", con.execute("SELECT min(id) FROM frases WHERE id > 2").fetchone()[0] == 3
     and con.execute("""SELECT o.nome FROM frases f JOIN linhas l ON l.id = f.linha_id JOIN episodios e
                        ON e.id = l.episodio_id JOIN obras o ON o.id = e.obra_id WHERE f.texto = 'He had left.'""").fetchone()[0] == "Emma")
caso("cache de fábrica só das regras dos dois", [r for (r,) in con.execute("SELECT regra FROM fabrica_regras")] == ["r1"]
     and con.execute("SELECT total FROM fabrica_regras").fetchone()[0] == 3
     and con.execute("SELECT count(*) FROM fabrica_ocorrencias WHERE regra = 'r1'").fetchone()[0] == 3
     and con.execute("SELECT count(*) FROM fabrica_ocorrencias WHERE regra <> 'r1'").fetchone()[0] == 0)
caso("grupos dos dois, apontando para as obras certas",
     con.execute("SELECT g.nome, o.nome FROM grupos g JOIN obras o ON o.id = g.obra_id ORDER BY g.ordem").fetchall()
     == [("Grupo Minha Série", "Minha Série"), ("Grupo Emma", "Emma")])
caso("versão do combinado = as duas", con.execute("SELECT valor FROM meta WHERE chave = 'versao'").fetchone()[0] == "p1+a1")
con.close()
mtime = combinado.stat().st_mtime_ns
bancos._cache.clear()
caso("combinado não é refeito à toa", bancos.caminho_corpus().stat().st_mtime_ns == mtime)

# desligado: só o próprio, e a escolha vale ao reabrir
caso("desligar", bancos.ligar_acervo(False) == {"disponivel": True, "ligado": False})
caso("desligado: busca só no próprio", bancos.caminho_corpus() == proprio)
importlib.reload(bancos)
bancos.APP = APP
caso("reaberto: continua desligado", bancos.acervo_ligado() is False and bancos.caminho_corpus() == proprio)
bancos.ligar_acervo(True)
caso("religado: volta o combinado", bancos.caminho_corpus().name == "combinado.db")

# próprio vazio: como se não houvesse (sem interruptor, só o acervo)
proprio.unlink()
banco(proprio, "p2", [], {})
bancos._cache.clear()
caso("próprio sem frases: sem interruptor, só o acervo", bancos.estado_acervo()["disponivel"] is False
     and bancos.caminho_corpus() == acervo)

if falhas:
    print(f"\n{len(falhas)} falha(s): {', '.join(falhas)}")
    sys.exit(1)
print("\ntudo certo")
