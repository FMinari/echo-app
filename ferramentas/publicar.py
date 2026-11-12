"""Publica a versão atual como release no GitHub, para o app da cliente achar e instalar sozinho.

Uso: python3 -I ferramentas/publicar.py

1. Confere que está tudo commitado e que a versão (topo de app/novidades.json) ainda não foi publicada.
2. Roda o empacotar.py (os pacotes levam o token de leitura, ver empacotar.py).
3. Cria e manda a tag v<versão> e a release, com o pacote do app e, se o banco de frases é mais novo que
   o de alguma release que ainda pode atualizar (a partir de atualizacao.MINIMA), o pacote completo
   (~120 MB): o app só oferece a release mais nova, então quem pular a versão que trouxe o banco precisa
   achá-lo nesta. O app só baixa o completo se o banco dele for mais velho. As notas são as novidades da versão, mais os
   metadados que o app lê: <!-- sitcomatica {"numero": ..., "banco": ...} -->
Precisa do `gh` logado na conta do dev.
"""
import json
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
REPO = "FMinari/echo"  # era FMinari/sitcomatica até 30/10/2026 (o GitHub redireciona o nome antigo)
METADADOS = re.compile(r"<!--\s*sitcomatica\s+(\{.*?\})\s*-->", re.S)
sys.path.insert(0, str(RAIZ / "app"))
from nucleo.atualizacao import MINIMA, numero_tupla  # noqa: E402


def rodar(*args, **kw):
    return subprocess.run(args, cwd=RAIZ, check=True, capture_output=True, text=True, **kw).stdout.strip()


def banco_mais_velho_das_releases():
    """O banco mais velho entre as releases de que ainda dá para atualizar (None se não há nenhuma)."""
    releases = json.loads(rodar("gh", "api", f"repos/{REPO}/releases?per_page=100"))
    bancos = [meta["banco"] for rel in releases if (m := METADADOS.search(rel.get("body") or ""))
              and (meta := json.loads(m.group(1))).get("banco") and numero_tupla(meta.get("numero")) >= MINIMA]
    return min(bancos, default=None)


def main():
    if rodar("git", "status", "--porcelain", "--untracked-files=no"):
        sys.exit("Há mudanças sem commit: commite antes de publicar (a versão leva o commit).")
    novidades = json.loads((RAIZ / "app" / "novidades.json").read_text(encoding="utf-8"))
    numero, itens = novidades[0]["versao"], novidades[0]["itens"]
    tag = f"v{numero}"
    if rodar("git", "ls-remote", "--tags", "origin", tag):
        sys.exit(f"A {tag} já existe no GitHub: ponha uma versão nova no topo de app/novidades.json.")
    with sqlite3.connect(f"file:{RAIZ / 'corpus.db'}?mode=ro", uri=True) as con:
        banco = con.execute("SELECT valor FROM meta WHERE chave = 'gerado_em'").fetchone()[0]
    mais_velho = banco_mais_velho_das_releases()
    com_banco = mais_velho is None or banco > mais_velho

    print(rodar(sys.executable, "-I", str(RAIZ / "ferramentas" / "empacotar.py")))
    dist = RAIZ / "dist"
    arquivos = [next(dist.glob(f"*{numero} - atualização.sitcomatica"))]
    if com_banco:
        arquivos.append(next(dist.glob(f"*{numero} - completo.zip")))

    notas = "\n".join(f"- {i}" for i in itens)
    notas += f"\n\n<!-- sitcomatica {json.dumps({'numero': numero, 'banco': banco}, ensure_ascii=False)} -->\n"
    rodar("git", "tag", "-a", tag, "-m", f"Echo {numero}")
    rodar("git", "push", "origin", tag)
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(notas)
    rodar("gh", "release", "create", tag, *map(str, arquivos), "--repo", REPO,
          "--title", f"Echo {numero}", "--notes-file", f.name)
    Path(f.name).unlink()
    print(f"publicada: {tag} ({', '.join(a.name for a in arquivos)})"
          + ("" if com_banco else " (banco igual ao de todas as releases: só o app)"))


if __name__ == "__main__":
    main()
