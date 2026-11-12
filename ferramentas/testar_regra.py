"""Testa uma regra de estrutura no corpus inteiro: total, onde mais aparece e uma amostra.

Uso:
  .venv/bin/python -I ferramentas/testar_regra.py --pecas '[{"tipo":"pessoa"},{"tipo":"verbo_passado"}]'
  .venv/bin/python -I ferramentas/testar_regra.py --pecas '...' --excluir 'had to' --excluir 'used to'
  .venv/bin/python -I ferramentas/testar_regra.py --padrao '[l=have t=VBD] [t=RB]* [t=VBN]' --excluir-regex '\\bhad to\\b'

Peças: ver app/nucleo/blocos.py (PECAS). --amostra N (padrão 15), --semente para outra amostra,
--json para saída em JSON (total, por_tipo, amostra).
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from nucleo import blocos, busca  # noqa: E402


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--pecas", help="lista JSON de peças")
    a.add_argument("--excluir", action="append", default=[], help="expressão a tirar (pode repetir)")
    a.add_argument("--padrao", help="padrão na linguagem de padrao.py (em vez de peças)")
    a.add_argument("--excluir-regex", help="regex de exclusão (com --padrao)")
    a.add_argument("--amostra", type=int, default=15)
    a.add_argument("--semente", type=int, default=0)
    a.add_argument("--json", action="store_true")
    args = a.parse_args()

    if args.pecas:
        padrao = blocos.para_padrao(json.loads(args.pecas))
        excluir = blocos.para_excluir(args.excluir)
    else:
        padrao, excluir = args.padrao, args.excluir_regex
    inicio = time.time()
    r = busca.buscar(padrao=padrao, excluir=excluir, limite=args.amostra, semente=args.semente, por_tipo=False)
    amostra = [{"obra": x["obra"], "falante": x["falante"], "frase": x["frase"], "trecho": x["trecho"]}
               for x in r["resultados"]]
    if args.json:
        print(json.dumps({"padrao": padrao, "excluir": excluir, "total": r["total"], "por_tipo": r["por_tipo"],
                          "amostra": amostra}, ensure_ascii=False))
        return
    print(f"padrão:  {padrao}\nexcluir: {excluir}")
    print(f"total: {r['total']}  {r['por_tipo']}  ({time.time() - inicio:.0f} s)")
    top = sorted(r["por_obra"].items(), key=lambda x: -x[1])[:8]
    print("onde mais: " + ", ".join(f"{o} {n}" for o, n in top))
    for x in amostra:
        print(f"- [{x['trecho']}]  {x['obra']} · {x['falante'] or '?'}: {x['frase'][:160]}")


if __name__ == "__main__":
    main()
