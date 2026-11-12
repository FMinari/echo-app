"""Espelha o código deste repositório (privado) no FMinari/echo-app (público, portfólio).

Uso: python3 -I ferramentas/espelhar_publico.py [pasta do clone do echo-app]   (padrão: ../echo-app)

Copia o `git archive HEAD` menos EXCLUIR, põe por cima o que está em publico/ (README, licença,
transcrição de exemplo, obras.json de exemplo...), roda o gitleaks e a busca de e-mail/telefone e, se
tudo estiver limpo, commita no clone. Não dá push: confira e rode `git -C <clone> push`.
Nada aqui mexe no echo, nas releases nem no token: só lê o HEAD e escreve no clone.
"""
import fnmatch
import io
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

# O que nunca vai para o público (caminho a partir da raiz; pasta = ela inteira; aceita * e ?).
EXCLUIR = [
    "transcripts",        # transcrições de séries, filmes e músicas (direito autoral)
    "*.db", "*.db-*",     # corpus.db, dados.db, índices
    "dist", "pacote",     # pacotes entregues e o instalador da cliente
    "app/contato.json",   # e-mail e telefone (no público vai o contato.example.json)
    "app/github.json",    # token de leitura das releases
    "CORPUS.md",          # histórico dos bancos mandados
    "CLAUDE.md", "docs",  # notas de desenvolvimento, falam da cliente e do PC da cliente
    "graphify-out",
    "publico",            # é a fonte do que vai por cima, não entra como pasta
]
# Identidade dos commits do público: o endereço noreply do GitHub, nunca o e-mail pessoal.
AUTOR = ["-c", "user.name=FMinari", "-c", "user.email=42005196+FMinari@users.noreply.github.com"]
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
TELEFONE = re.compile(r"\+55|\(?\b\d{2}\)?[\s.-]?9\d{4}[\s.-]?\d{4}\b|wa\.me/\d")
SO_TEXTO = {".gz", ".ico", ".png", ".jpg", ".svg"}  # binários (e svg, só desenho) ficam fora da busca

RAIZ = Path(__file__).resolve().parent.parent


def excluido(caminho):
    partes = caminho.split("/")
    return any(fnmatch.fnmatch("/".join(partes[:i]), p) or fnmatch.fnmatch(partes[i - 1], p)
               for p in EXCLUIR for i in range(1, len(partes) + 1))


def copiar(destino):
    for item in destino.iterdir():
        if item.name != ".git":
            shutil.rmtree(item) if item.is_dir() else item.unlink()
    tar = subprocess.run(["git", "-C", RAIZ, "archive", "--format=tar", "HEAD"],
                         check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        t.extractall(destino, members=[m for m in t if not excluido(m.name.rstrip("/"))], filter="data")
    shutil.copytree(RAIZ / "publico", destino, dirs_exist_ok=True)


def conferir(destino):
    """Lista de problemas (vazia = pode commitar)."""
    problemas = []
    vieram_de_publico = {p.relative_to(RAIZ / "publico").as_posix()
                         for p in (RAIZ / "publico").rglob("*") if p.is_file()}
    for p in destino.rglob("*"):
        rel = p.relative_to(destino).as_posix()
        if ".git" in p.relative_to(destino).parts or not p.is_file():
            continue
        if excluido(rel) and rel not in vieram_de_publico:
            problemas.append(f"excluído mas presente: {rel}")
        # uv.lock: só hashes e URLs do PyPI; este script: tem os próprios padrões e o noreply
        if p.suffix not in SO_TEXTO and rel not in ("app/uv.lock", "ferramentas/espelhar_publico.py"):
            texto = p.read_text(encoding="utf-8", errors="ignore")
            for achado in EMAIL.findall(texto) + TELEFONE.findall(texto):
                problemas.append(f"{rel}: {achado}")
    gitleaks = shutil.which("gitleaks")
    if not gitleaks:
        problemas.append("gitleaks não encontrado no PATH")
    else:
        r = subprocess.run([gitleaks, "dir", destino, "--no-banner", "--redact"], capture_output=True, text=True)
        if r.returncode:
            problemas.append("gitleaks:\n" + r.stdout + r.stderr)
    return problemas


def main():
    destino = Path(sys.argv[1] if len(sys.argv) > 1 else RAIZ.parent / "echo-app").resolve()
    assert destino != RAIZ and RAIZ not in destino.parents, "o destino não pode ser o próprio echo"
    if not (destino / ".git").is_dir():
        destino.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-q", "-b", "main", destino], check=True)
    copiar(destino)
    problemas = conferir(destino)
    if problemas:
        print("Não commitei. Problemas:\n" + "\n".join(problemas), file=sys.stderr)
        sys.exit(1)
    git = ["git", *AUTOR, "-C", destino]
    subprocess.run([*git, "add", "-A"], check=True)
    if not subprocess.run([*git, "diff", "--cached", "--quiet"]).returncode:
        print("Nada mudou no público.")
        return
    commit = subprocess.run(["git", "-C", RAIZ, "rev-parse", "--short", "HEAD"],
                            check=True, capture_output=True, text=True).stdout.strip()
    subprocess.run([*git, "commit", "-q", "-m", f"Código do Echo (espelho de {commit})"], check=True)
    print(f"Commit feito em {destino}. Confira e rode: git -C {destino} push")


if __name__ == "__main__":
    assert excluido("transcripts/friends/x.txt") and excluido("corpus.db") and excluido("app/x/i.db-wal")
    assert excluido("docs/superpowers/handoff.md") and excluido("app/contato.json")
    assert not excluido("app/contato.example.json") and not excluido("app/nucleo/busca.py")
    main()
