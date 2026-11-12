"""Busca frases no corpus por estrutura do catálogo, padrão gramatical e/ou texto.

Uso:
  .venv/bin/python -I ferramentas/buscar.py --estrutura "past perfect" --obra emma
  .venv/bin/python -I ferramentas/buscar.py --padrao '[l=have t=VBD] [t=RB]* [t=VBN]' --limite 10
  .venv/bin/python -I ferramentas/buscar.py --texto '\\bused to\\b' --falante Elizabeth
  .venv/bin/python -I ferramentas/buscar.py --listar

A linguagem do --padrao está em app/nucleo/padrao.py. O catálogo de estruturas é o mesmo
do app (dados.db do usuário; veja app/nucleo/bancos.py).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from nucleo import busca, catalogo  # noqa: E402
from nucleo.padrao import __doc__ as AJUDA_PADRAO  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__ + "\n" + AJUDA_PADRAO,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listar", action="store_true", help="lista o catálogo de estruturas e as obras")
    ap.add_argument("--estrutura", help="nome ou id de uma estrutura do catálogo")
    ap.add_argument("--padrao", help="padrão gramatical sobre os tokens etiquetados")
    ap.add_argument("--texto", help="regex sobre o texto da frase (sem distinção de maiúsculas)")
    ap.add_argument("--excluir", help="regex: descarta frases cujo texto case com ela")
    ap.add_argument("--obra", action="append", help="nome da obra; pode repetir (ex.: --obra emma)")
    ap.add_argument("--tipo", choices=["serie", "filme", "musica"])
    ap.add_argument("--temporada", type=int)
    ap.add_argument("--falante", help="nome do personagem (ex.: Elizabeth)")
    ap.add_argument("--min-palavras", type=int, default=4)
    ap.add_argument("--limite", type=int, default=30, help="quantos resultados mostrar (amostra aleatória)")
    ap.add_argument("--semente", type=int, default=0)
    a = ap.parse_args()

    if a.listar:
        for o in busca.listar_obras():
            print(f"obra: {o['nome']} ({o['tipo']}, {o['episodios']} episódios)")
        for e in catalogo.listar():
            print(f"[{e['id']}] {e['nome']} · {e['categoria']} · {e['nivel']} · {e['formula']}")
        return
    if not (a.estrutura or a.padrao or a.texto):
        ap.error("informe --estrutura, --padrao e/ou --texto")

    r = busca.buscar(padrao=a.padrao, texto=a.texto, excluir=a.excluir, estrutura=a.estrutura,
                     obras=a.obra, tipo=a.tipo, temporada=a.temporada, falante=a.falante,
                     min_palavras=a.min_palavras, limite=a.limite, semente=a.semente)
    top = ", ".join(f"{t['falante']} {t['frases']}" for t in r["top_falantes"])
    print(f"{r['total']} frases casaram {r['por_obra']}; mostrando {len(r['resultados'])}.")
    print(f"quem mais usa: {top}\n")
    for i, x in enumerate(r["resultados"], 1):
        onde = (x["obra"] if x["tipo"] == "filme" else f"{x['obra']} \"{x['titulo']}\"" if x["tipo"] == "musica"
                else f"{x['obra']} {x['referencia']} \"{x['titulo']}\"")
        print(f"## {i}. {onde} {x['tempo']}")
        print(f"frase: {x['falante'] or '?'}: {x['frase']}")
        print(f"trecho: {x['trecho']}")
        print(f"cena: {x['cena'] or '(transcrição sem marcação de cena)'}")
        for v in x["antes"]:
            print(f"  antes: {v['falante'] or '?'}: {v['texto']}")
        for v in x["depois"][:1]:
            print(f"  depois: {v['falante'] or '?'}: {v['texto']}")
        print(f"  (arquivo: {x['arquivo']})\n")


if __name__ == "__main__":
    main()
