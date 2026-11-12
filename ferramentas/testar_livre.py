"""Confere a busca escrita (app/nucleo/livre.py) no corpus de verdade, com um dados.db de teste: primeiro
sem o índice das frases (como nos primeiros segundos do app), depois com ele (indice.py), e confere que
os dois dão os mesmos números.

Uso: app/.venv/bin/python -I ferramentas/testar_livre.py
Sai com erro se algum caso falhar.
"""
import os
import sys
import tempfile
from pathlib import Path

DADOS = Path(tempfile.mkdtemp(prefix="sitcomatica-livre-")) / "dados.db"
os.environ["FRASES_DADOS"] = str(DADOS)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
from nucleo import bancos, indice, livre  # noqa: E402

falhas = []


def caso(nome, cond, detalhe=""):
    print(("ok  " if cond else "ERRO"), nome, detalhe)
    if not cond:
        falhas.append(nome)


def trechos(r):
    return [x["trecho"].lower() for x in r["resultados"]]


def tudo(texto, **kw):
    return livre.buscar(texto, limite=100000, **kw)


def contagem_dados():
    with bancos.dados() as con:
        return {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("ocorrencias", "varreduras")}


def casos(rotulo):
    """Os casos; devolve os números para comparar com e sem índice."""
    global caso
    _caso = caso

    def caso(nome, cond, detalhe=""):  # noqa: F811 — prefixa o nome com "sem índice"/"com índice"
        _caso(f"[{rotulo}] {nome}", cond, detalhe)
    numeros = {}

    r = tudo("take off")
    ts = trechos(r)
    caso("take off acha outras formas", any(t.startswith("took") for t in ts) and any(t.startswith("taking") for t in ts),
         f"{r['total']} frases")
    caso("take off acha com o objeto no meio", any(len(t.split()) > 2 for t in ts))
    caso("o verbo é take", r["livre"]["verbo"] == "take")
    caso("o rótulo diz o que a cliente escreveu", r["resultados"][0]["estrutura"] == "Busca: take off")

    r = tudo("took off", outras_formas=False)
    ts = trechos(r)
    caso("sem outras formas: só 'took off'", r["total"] and all(t == "took off" for t in ts), f"{r['total']} frases")

    r = tudo("take off", tempo="passado")
    ts = trechos(r)
    # o spaCy às vezes etiqueta particípio como passado ("taken off" com VBD): tolera 5%
    caso("tempo passado: só took", r["total"] and sum(t.startswith("took") for t in ts) >= 0.95 * len(ts),
         f"{r['total']} frases")

    r = tudo("I wish I had")
    caso("frase comum", r["total"] > 10 and r["livre"]["verbo"] == "wish", f"{r['total']} frases")

    r = tudo("don't")
    caso("contração", r["total"] > 1000, f"{r['total']} frases")

    r = tudo("I'm")
    caso("contração de 3 letras (I'm) se separa como no corpus", r["total"] > 10000, f"{r['total']} frases")
    for texto in ("ex-wife", "e-mail", "fiancé", "Mr. Geller"):
        r = tudo(texto)
        caso(f"{texto}: hífen, acento e abreviação como no corpus", r["total"] > 0, f"{r['total']} frases")
    r = tudo("plan", tempo="passado")
    ts = trechos(r)
    caso("tempo do verbo em palavra mais substantivo que verbo (plan → planned)",
         r["total"] and all(t.startswith("planned") for t in ts), f"{r['total']} frases")
    try:
        livre.montar("the cat", tempo="passado")
        caso("tempo sem verbo avisa", False)
    except ValueError as e:
        caso("tempo sem verbo avisa", "verbo" in str(e))

    r = livre.buscar("take off", limite=5, por_tipo=True, pagina={"serie": 2})
    caso("página 2", len(r["resultados"]) > 0 and r["pagina"]["serie"] == 2)

    # músicas (F22): o artista é a obra, a música o título, e o tempo é o do verso (sem "~")
    r = livre.buscar("if I were a boy", limite=10, por_tipo=True, tipo="musica")
    x = r["resultados"][0] if r["resultados"] else {}
    caso("música: acha o verso", x.get("obra") == "Beyoncé" and x.get("titulo") == "If I Were a Boy", f"{r['total']} frases")
    caso("música: tempo exato e artista como falante",
         x.get("tempo", "~")[0] != "~" and x.get("falante") == "Beyoncé" and x.get("referencia") == "música", x.get("tempo"))
    caso("música: refrão não repete", r["total"] == len({y["frase"].lower() for y in tudo("if I were a boy", tipo="musica")["resultados"]}))
    r = livre.buscar("if I were a boy", limite=5, por_tipo=True)
    caso("música: seção própria", r["por_tipo"].get("musica", 0) > 0 and r["pagina"].get("musica") == 1, f"{r['por_tipo']}")

    pv = {p["texto"]: p["frases"] for p in livre.phrasal_verbs("get")}
    caso("phrasal verbs de get", {"get up", "get out", "get in", "get over", "get out of"} <= set(pv), f"{len(pv)} achados")
    pv = {p["texto"] for p in livre.phrasal_verbs("be")}
    caso("phrasal verbs de be", {"be over", "be up", "be back", "be up to"} <= pv, f"{len(pv)} achados")
    pv = {p["texto"] for p in livre.phrasal_verbs("took")}
    caso("de 'took' saem os de take", "take off" in pv)
    caso("palavra que não é verbo: nada", livre.phrasal_verbs("coffee") == [])
    caso("duas palavras: nada", livre.phrasal_verbs("get up") == [])
    pv = livre.phrasal_verbs("get", obras=["Friends"], falante="Ross")
    caso("filtro de obra e personagem", pv and pv[0]["frases"] < 100, f"{pv[:3]}")

    try:
        livre.montar("   !!  ")
        caso("texto vazio dá erro", False)
    except ValueError as e:
        caso("texto vazio dá erro", True, str(e))


    for t in ("take off", "I wish I had", "come up with"):
        numeros[t] = tudo(t)["total"]
    numeros["get"] = livre.phrasal_verbs("get")
    numeros["be passado"] = livre.phrasal_verbs("be", tempo="passado")
    caso = _caso
    return numeros


# o dicionário do balão: a forma mais comum no corpus primeiro, e as partes da contração
from nucleo import dicionario  # noqa: E402
r = dicionario.procurar("saw")
caso("dicionário: saw → see (e saw depois)", r["lema"] == "see" and [t["lema"] for t in r["tambem"]] == ["saw"])
r = dicionario.procurar("didn't")
caso("dicionário: didn't → do + not", r["lema"] == "do" and [t["lema"] for t in r["tambem"]] == ["not"])
caso("dicionário: let's fica inteiro", dicionario.procurar("let's")["lema"] == "let's")
caso("dicionário: sem frase em inglês no lugar da tradução",
     not any("bench" in t for e in dicionario.procurar("would")["entradas"] for s in e["sentidos"] for t in s["traducoes"]))

# coringas vizinhos (Palavras no meio + Até 3 palavras) viram um só: sem isso, ~20 s no corpus
from nucleo.padrao import compilar  # noqa: E402
caso("coringas vizinhos se juntam", compilar("[t=PRP]+ ... ... []{0,3} [t=MD]").pattern.count("[^ ]+ )") == 1)

antes = contagem_dados()
sem = casos("sem índice")
caso("o índice monta", indice.construir().exists())
livre._uso.cache_clear()
com = casos("com índice")
caso("com e sem índice dão os mesmos números", sem == com,
     "" if sem == com else str({k: (sem[k], com[k]) for k in sem if sem[k] != com[k]})[:300])
caso("nada gravado no dados.db", contagem_dados() == antes)

print(f"\n{'tudo certo' if not falhas else f'{len(falhas)} falha(s)'}")
sys.exit(1 if falhas else 0)
