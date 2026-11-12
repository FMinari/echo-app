"""Grava no corpus.db o cache das estruturas de fábrica (app/nucleo/semente_estruturas.json).

Sem ele, cada PC varre o corpus inteiro para cada estrutura (186 × ~10 s aqui, bem mais no da cliente) na
primeira vez e de novo a cada corpus novo. Com ele, o app copia os achados prontos, e só as
estruturas que a cliente criou precisam ser varridas lá.

O cache é por regra (o mesmo hash do cache do app), então é incremental: só calcula as regras que
ainda não estão no banco e apaga as que saíram da semente. O empacotar.py roda isto antes de montar o
zip; depois de reindexar, rode de novo (o indexar.py recria o banco do zero).

Uso: .venv/bin/python -I ferramentas/cache_fabrica.py [caminho do corpus.db]
"""
import json
import sqlite3
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "app"))

from nucleo import busca, catalogo  # noqa: E402

POR_PASSADA = 20

SCHEMA = """
CREATE TABLE IF NOT EXISTS fabrica_regras (regra TEXT PRIMARY KEY, nome TEXT, total INTEGER);
CREATE TABLE IF NOT EXISTS fabrica_ocorrencias (
    regra TEXT, frase_id INTEGER, obra_id INTEGER, temporada INTEGER, falante TEXT, palavras INTEGER,
    destaques TEXT);
CREATE INDEX IF NOT EXISTS fabrica_oc_regra ON fabrica_ocorrencias(regra, obra_id);
"""


def regras_da_semente():
    """{hash da regra: (nome, estrutura)} de cada estrutura de fábrica, como o app vai vê-la."""
    regras = {}
    for s in json.loads(catalogo.SEMENTE.read_text(encoding="utf-8")):
        e = catalogo._da_semente(s)
        regras[busca.hash_regra(e)] = (s["nome"], e)
    return regras


def faltando(banco):
    """Quantas regras de fábrica ainda não estão no cache desse corpus.db."""
    with sqlite3.connect(f"file:{banco}?mode=ro", uri=True) as con:
        try:
            prontas = {r[0] for r in con.execute("SELECT regra FROM fabrica_regras")}
        except sqlite3.OperationalError:
            prontas = set()
    return len(regras_da_semente().keys() - prontas)


def main(banco):
    inicio = time.time()
    con = sqlite3.connect(banco)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    regras = regras_da_semente()
    prontas = {r["regra"] for r in con.execute("SELECT regra FROM fabrica_regras")}
    for velha in prontas - regras.keys():
        con.execute("DELETE FROM fabrica_ocorrencias WHERE regra = ?", (velha,))
        con.execute("DELETE FROM fabrica_regras WHERE regra = ?", (velha,))
    novas = [h for h in regras if h not in prontas]
    obras = [r["id"] for r in con.execute("SELECT id FROM obras")]
    print(f"{len(regras)} regras de fábrica: {len(novas)} para calcular, {len(prontas - regras.keys())} apagadas",
          flush=True)
    for i in range(0, len(novas), POR_PASSADA):
        lote = [(h, busca._compilar(regras[h][1]["padrao"], regras[h][1]["texto"], regras[h][1]["excluir"]), [])
                for h in novas[i:i + POR_PASSADA]]
        for r in busca._linhas(con, obras):
            for h, rxs, achados in lote:
                destaques = busca._casar_linha(r, *rxs)
                if destaques is not None:
                    achados.append((h, r["id"], r["obra_id"], r["temporada"], r["falante"],
                                    len(r["texto"].split()), json.dumps(destaques)))
        for h, _, achados in lote:
            con.executemany("INSERT INTO fabrica_ocorrencias VALUES (?,?,?,?,?,?,?)", achados)
            con.execute("INSERT INTO fabrica_regras VALUES (?,?,?)", (h, regras[h][0], len(achados)))
        con.commit()
        print(f"  {min(i + POR_PASSADA, len(novas))}/{len(novas)} ({time.time() - inicio:.0f} s)", flush=True)
    total = con.execute("SELECT count(*) FROM fabrica_ocorrencias").fetchone()[0]
    con.close()
    print(f"pronto: {total} achados de {len(regras)} regras em {banco} ({time.time() - inicio:.0f} s)")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "corpus.db")
