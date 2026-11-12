"""Confere os textos da cliente (app/nucleo/textos.py) num dados.db de teste: a migração 3 (banco da 1.4 e banco
novo), criar, editar, mudar de aula, apagar e apagar a aula (os textos vão para "Sem aula").

Uso: app/.venv/bin/python -I ferramentas/testar_textos.py
"""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

DADOS = Path(tempfile.mkdtemp(prefix="sitcomatica-textos-")) / "dados.db"
os.environ["FRASES_DADOS"] = str(DADOS)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
from nucleo import aulas, bancos, textos  # noqa: E402
from nucleo.registro import NaoEncontrado  # noqa: E402

falhas = []


def caso(nome, cond, detalhe=""):
    print(("ok  " if cond else "ERRO"), nome, detalhe)
    if not cond:
        falhas.append(nome)


def erro(fn, *args, **kw):
    try:
        fn(*args, **kw)
    except (ValueError, NaoEncontrado) as e:
        return str(e)
    return None


# um dados.db "da 1.4" (versão 2): tem aulas, não tem textos
bancos.preparar_dados(DADOS)
with sqlite3.connect(DADOS) as con:
    con.execute("DROP TABLE textos")
    con.execute("PRAGMA user_version = 2")
    con.execute("INSERT INTO aulas (nome) VALUES ('Aula velha')")
feitas = bancos.preparar_dados(DADOS)
with sqlite3.connect(DADOS) as con:
    versao = con.execute("PRAGMA user_version").fetchone()[0]
    tem = con.execute("SELECT count(*) FROM sqlite_master WHERE name = 'textos'").fetchone()[0]
caso("migração 3: banco da 1.4 ganha a tabela textos", tem == 1 and versao == bancos.VERSAO_DADOS == 3,
     str(feitas))
caso("migração 3: a aula de antes continua", [a["nome"] for a in aulas.listar()["aulas"]] == ["Aula velha"])
novo = DADOS.parent / "novo" / "dados.db"
bancos.preparar_dados(novo)
with sqlite3.connect(novo) as con:
    caso("banco novo já nasce com textos",
         con.execute("SELECT count(*) FROM sqlite_master WHERE name = 'textos'").fetchone()[0] == 1)

aula = aulas.criar("Aula 5")
t = textos.criar("  My   weekend ", "I went to the beach.\n\nIt was sunny.  ", aula["id"])
caso("criar: título limpo, texto guardado como a cliente escreveu (sem espaço no fim)",
     t["titulo"] == "My weekend" and t["corpo"] == "I went to the beach.\n\nIt was sunny.", repr(t["corpo"]))
caso("criar: na aula", t["aula_id"] == aula["id"] and t["aula"] == "Aula 5")
caso("título vazio dá erro", "título" in (erro(textos.criar, "  ", "x", None) or ""))
caso("título comprido dá erro", erro(textos.criar, "a" * 121, "x", None) is not None)
caso("texto comprido demais dá erro", "comprido" in (erro(textos.criar, "Longo", "a" * 20001, None) or ""))
caso("aula que não existe dá erro", erro(textos.criar, "Sem casa", "x", 9999) is not None)
rascunho = textos.criar("Rascunho", "", None)
caso("texto vazio pode ser guardado (rascunho), em Sem aula", rascunho["corpo"] == "" and rascunho["aula_id"] is None)

e = textos.salvar(t["id"], "My weekend (2)", "I went to the park.", None)
caso("editar: título, texto e aula", e["titulo"] == "My weekend (2)" and e["corpo"] == "I went to the park."
     and e["aula_id"] is None and e["aula"] is None)
caso("editar muda o atualizado_em", e["atualizado_em"] >= t["atualizado_em"])
caso("editar texto que não existe dá erro", erro(textos.salvar, 9999, "x", "y", None) is not None)

textos.salvar(t["id"], "My weekend", "I went to the park.", aula["id"])
lista = textos.listar()
caso("listar: todos, sem o corpo, com o começo do texto",
     len(lista) == 2 and "corpo" not in lista[0] and any(x["comeco"] == "I went to the park." for x in lista))
caso("listar por aula", [x["titulo"] for x in textos.listar(aula["id"])] == ["My weekend"])
caso("listar Sem aula", [x["titulo"] for x in textos.listar(None)] == ["Rascunho"])
caso("aulas: contagem de textos", next(a for a in aulas.listar()["aulas"] if a["id"] == aula["id"])["textos"] == 1)

aulas.apagar(aula["id"])
caso("apagar a aula manda os textos para Sem aula", sorted(x["titulo"] for x in textos.listar(None))
     == ["My weekend", "Rascunho"])
textos.apagar(rascunho["id"])
caso("apagar o texto", [x["titulo"] for x in textos.listar()] == ["My weekend"])
caso("abrir texto apagado dá erro", erro(textos.obter, rascunho["id"]) is not None)

# o que a tela chama
from janela.api import Api  # noqa: E402

api = Api()
criado = api.salvar_texto({"titulo": "Pela tela", "corpo": "Hello.", "aula_id": ""})
caso("api: criar sem aula (o seletor manda vazio)", criado.get("aula_id") is None and criado["titulo"] == "Pela tela")
editado = api.salvar_texto({"id": criado["id"], "titulo": "Pela tela 2", "corpo": "Hi.", "aula_id": None})
caso("api: editar pelo id", editado["id"] == criado["id"] and editado["corpo"] == "Hi.")
caso("api: listar todos, Sem aula e por aula",
     len(api.textos()) == 2 and len(api.textos(None)) == 2 and api.textos(9999) == [])
if sys.platform != "win32":
    caso("api: salvar áudio do texto fora do Windows avisa",
         api.salvar_audio_texto(criado["id"]) == {"erro": "Salvar o áudio só funciona no Windows."})
caso("api: salvar áudio de texto apagado avisa", api.salvar_audio_texto(9999) == {"erro": "Esse texto não existe mais."})
caso("api: erro vira mensagem para a cliente", api.salvar_texto({"titulo": ""}) == {"erro": "Dê um título para o texto."})
caso("api: texto apagado vira mensagem", api.apagar_texto(criado["id"]) == {"ok": True}
     and api.texto(criado["id"]) == {"erro": "Esse texto não existe mais."})

print(f"\n{'tudo certo' if not falhas else f'{len(falhas)} falha(s)'}")
sys.exit(1 if falhas else 0)
