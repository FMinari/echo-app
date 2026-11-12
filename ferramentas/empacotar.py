"""Monta os pacotes para o PC da cliente (Windows), em dist/:

  "Echo <versão> - completo.zip"             app + corpus.db (instalação nova ou banco novo)
  "Echo <versão> - atualização.sitcomatica"  sem o corpus.db: pequeno, quando as frases não mudaram;
                                             dois cliques nele abrem o app e instalam
  O app se chamava Sitcomática até a 1.4.1 (virou Echo na 2.0). A extensão .sitcomatica fica: é por ela que
  as versões instaladas reconhecem a atualização. A pasta raiz do zip também fica "Sitcomatica": o conserto
  documentado é extrair o completo de novo por cima, e com outro nome sairia uma segunda instalação ao lado.
  Com --atualizacao-em-zip, a atualização sai como "Sitcomatica <versão> - atualização.zip": é o que
  a 1.1 entende (ela não conhece .sitcomatica e procura nomes começando com "Sitcomatica", sem acento).

  Sitcomatica/
    instalar.bat                  (CRLF)
    LEIA-ME.txt                   (CRLF + BOM, para o Bloco de Notas mostrar os acentos)
    python/                       só no completo: o Python "embeddable" do python.org (assinado pela PSF;
                                  o Controle Inteligente de Aplicativos do Windows barra Python sem
                                  assinatura). Baixado uma vez, conferido pelo SHA-256 e guardado em ~/.cache.
    app/                          código do app (+ corpus.db no completo), sem .venv, caches, dados.db,
                                  nem o que é só do PC do dev (MCP, uv)

A cliente instala uma atualização abrindo o app com o arquivo em Downloads (ver nucleo/atualizacao.py), ou
o app acha a release no GitHub (ver nucleo/github.py e publicar.py). O token de leitura do GitHub vai
dentro dos pacotes como app/github.json, copiado de ~/.config/echo/github.json (nunca do git).
Uso: python3 -I ferramentas/empacotar.py [--atualizacao-em-zip]
"""
import json
import sqlite3
import sys
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GITHUB = Path.home() / ".config" / "echo" / "github.json"
# Python embutido. Versão nova: troque os dois, confira a assinatura sigstore do python.org
# (python -m sigstore verify identity --bundle <zip>.sigstore …) e anote o SHA-256 aqui.
PYTHON_VERSAO = "3.13.16"
PYTHON_SHA256 = "97dae5274cc54867065e8d5a3226e48c35017ed332a0fdb0e27d5b5821961297"
PYTHON_CACHE = Path.home() / ".cache" / "sitcomatica"
APP = RAIZ / "app"
DIST = RAIZ / "dist"
PASTA = "Sitcomatica"  # a pasta que a cliente extrai: o mesmo nome de antes, para reinstalar por cima
FORA = {".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
EXTENSOES_FORA = {".pyc", ".db", ".png"}
# só do PC do dev: o servidor do Claude (o Claude saiu do PC da cliente) e o ambiente do uv
SO_DESENVOLVIMENTO = {"mcp_server.py", "pyproject.toml", "uv.lock", ".python-version"}


def arquivos_do_app():
    for p in sorted(APP.rglob("*")):
        rel = p.relative_to(APP)
        if (p.is_file() and not FORA.intersection(rel.parts) and p.suffix not in EXTENSOES_FORA
                and str(rel) not in SO_DESENVOLVIMENTO):
            yield p, rel


def python_embutido():
    """O zip do Python embeddable (baixa do python.org na primeira vez) e confere o SHA-256."""
    import hashlib
    import urllib.request
    zipado = PYTHON_CACHE / f"python-{PYTHON_VERSAO}-embed-amd64.zip"
    if not zipado.exists():
        PYTHON_CACHE.mkdir(parents=True, exist_ok=True)
        url = f"https://www.python.org/ftp/python/{PYTHON_VERSAO}/{zipado.name}"
        print(f"baixando {url}", flush=True)
        with urllib.request.urlopen(url, timeout=60) as r:
            zipado.with_suffix(".parcial").write_bytes(r.read())
        zipado.with_suffix(".parcial").rename(zipado)
    if hashlib.sha256(zipado.read_bytes()).hexdigest() != PYTHON_SHA256:
        zipado.unlink()
        sys.exit(f"ERRO: o SHA-256 de {zipado.name} não confere (apaguei; rode de novo)")
    return zipado


def versao():
    """Número (de app/novidades.json) + data + commit, gravado em app/VERSAO dentro do zip: aparece
    na aba Sobre e no começo de cada log da cliente."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True).stdout.strip()
    commit = git("rev-parse", "--short", "HEAD") or "sem-git"
    sujo = "+mudanças" if git("status", "--porcelain", "--untracked-files=no", "--", "app") else ""
    numero = json.loads((APP / "novidades.json").read_text(encoding="utf-8"))[0]["versao"]
    return f"{numero} · {datetime.now():%d/%m/%Y %H:%M} · {commit}{sujo}"


def main():
    corpus = RAIZ / "corpus.db"
    # sem o cache de fábrica completo, o PC da cliente varreria o corpus para cada estrutura
    sys.path.insert(0, str(RAIZ / "ferramentas"))
    import cache_fabrica
    if faltam := cache_fabrica.faltando(corpus):
        print(f"cache de fábrica: faltam {faltam} regras, calculando (alguns minutos)…", flush=True)
        cache_fabrica.main(corpus)
    with sqlite3.connect(f"file:{corpus}?mode=ro", uri=True) as con:
        gerado = con.execute("SELECT valor FROM meta WHERE chave = 'gerado_em'").fetchone()[0]
        obras = [r[0] for r in con.execute("SELECT nome FROM obras ORDER BY nome")]

    DIST.mkdir(exist_ok=True)
    for velho in [*DIST.glob("Sitcom*.zip"), *DIST.glob("Echo*.zip"), *DIST.glob("*.sitcomatica")]:
        velho.unlink()
    rotulo = versao()
    numero = rotulo.split("·")[0].strip()
    atualizacao = (DIST / f"Sitcomatica {numero} - atualização.zip" if "--atualizacao-em-zip" in sys.argv
                   else DIST / f"Echo {numero} - atualização.sitcomatica")
    python = python_embutido()
    for destino, completo in ((DIST / f"Echo {numero} - completo.zip", True), (atualizacao, False)):
        with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            # CRLF garantido aqui: com LF, o cmd.exe pode não achar o rótulo do "goto erro"
            bat = (RAIZ / "pacote" / "instalar.bat").read_bytes().replace(b"\r\n", b"\n")
            z.writestr(f"{PASTA}/instalar.bat", bat.replace(b"\n", b"\r\n"))
            conteudo = (RAIZ / "pacote" / "LEIA-ME.txt").read_text(encoding="utf-8").replace("\r\n", "\n")
            z.writestr(f"{PASTA}/LEIA-ME.txt", "\ufeff" + conteudo.replace("\n", "\r\n"))
            if completo:
                with zipfile.ZipFile(python) as zp:
                    for item in zp.infolist():
                        z.writestr(f"{PASTA}/python/{item.filename}", zp.read(item))
            n = 0
            for p, rel in arquivos_do_app():
                z.write(p, f"{PASTA}/app/{rel.as_posix()}")
                n += 1
            if completo:
                z.write(corpus, f"{PASTA}/app/corpus.db")
            z.writestr(f"{PASTA}/app/VERSAO", rotulo + "\n")
            if GITHUB.exists():
                z.write(GITHUB, f"{PASTA}/app/github.json")
        print(f"{destino.name}: {destino.stat().st_size / 1e6:.1f} MB")
    print(f"versão {rotulo}; {n} arquivos do app; banco de {gerado[:16]} ({len(obras)} obras, anote em CORPUS.md)")
    print("Mande o completo se o corpus.db mudou desde a última entrega; senão, a atualização basta.")
    if not GITHUB.exists():
        print(f"ATENÇÃO: sem {GITHUB}: estes pacotes não buscam atualizações no GitHub.")


if __name__ == "__main__":
    main()
