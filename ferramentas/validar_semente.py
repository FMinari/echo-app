"""Roda cada estrutura da semente e mostra o total e uma amostra, para conferir as regras.

Uso: .venv/bin/python -I ferramentas/validar_semente.py [nome-da-estrutura ...] [--n 10] [--semente 0]
"""
import argparse
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP))

from nucleo import busca  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("nomes", nargs="*")
ap.add_argument("--n", type=int, default=10)
ap.add_argument("--semente", type=int, default=0)
a = ap.parse_args()

for e in json.loads((APP / "nucleo/semente_estruturas.json").read_text(encoding="utf-8")):
    if a.nomes and e["nome"].lower() not in [n.lower() for n in a.nomes]:
        continue
    r = busca.buscar(padrao=e.get("padrao"), texto=e.get("texto"), excluir=e.get("excluir"),
                     limite=a.n, semente=a.semente)
    print(f"=== {e['nome']}: {r['total']} frases  {r['por_obra']}")
    for x in r["resultados"]:
        frase = x["frase"]
        for ini, fim in reversed(x["destaques"]):
            frase = frase[:ini] + "[" + frase[ini:fim] + "]" + frase[fim:]
        print(f"  - {frase[:220]}")
    print()
