"""Confere a troca de arquivos da atualização (app/nucleo/atualizacao.py `aplicar`) numa instalação de
mentira: o normal, o python/ do pacote completo que não é tocado, a troca que quebra no meio (tudo volta
como era), o zip estragado e duas instalações ao mesmo tempo.

Uso: app/.venv/bin/python -I ferramentas/testar_atualizacao.py
"""
import os
import sys
import tempfile
import threading
import zipfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="sitcomatica-atualizacao-"))
os.environ["FRASES_DADOS"] = str(TMP / "dados" / "dados.db")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
from nucleo import atualizacao  # noqa: E402

falhas = []


def caso(nome, cond, detalhe=""):
    print(("ok  " if cond else "ERRO"), nome, detalhe)
    if not cond:
        falhas.append(nome)


def instalacao(nome):
    raiz = TMP / nome / "Sitcomatica"
    for rel, texto in {"app/VERSAO": "1.4 · 2026-10-12 · abc", "app/nucleo/busca.py": "velho",
                       "app/novidades.json": "[]", "python/python.exe": "python velho"}.items():
        (raiz / rel).parent.mkdir(parents=True, exist_ok=True)
        (raiz / rel).write_text(texto)
    return raiz


def pacote(nome, extras=None):
    caminho = TMP / f"{nome}.sitcomatica"
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("Sitcomatica/app/VERSAO", "9.9 · 2026-10-13 · def")
        z.writestr("Sitcomatica/app/novidades.json", '[{"versao": "9.9", "itens": []}]')
        z.writestr("Sitcomatica/app/nucleo/busca.py", "novo")
        z.writestr("Sitcomatica/app/nucleo/audio.py", "novo")
        for rel, texto in (extras or {}).items():
            z.writestr(f"Sitcomatica/{rel}", texto)
    return caminho


ler = lambda raiz, rel: (raiz / rel).read_text() if (raiz / rel).exists() else None  # noqa: E731

# normal, com o python/ do pacote completo
raiz = instalacao("normal")
r = atualizacao.aplicar(pacote("completo", {"python/python.exe": "python novo"}), raiz)
caso("instala", r == {"tipo": "app", "numero": "9.9"} and ler(raiz, "app/nucleo/busca.py") == "novo"
     and ler(raiz, "app/nucleo/audio.py") == "novo" and ler(raiz, "app/VERSAO").startswith("9.9"))
caso("python/ do pacote completo não é tocado", ler(raiz, "python/python.exe") == "python velho")
caso("não sobra pasta de trabalho", sorted(p.name for p in raiz.parent.iterdir()) == ["Sitcomatica"])

# quebra no meio: o arquivo do VERSAO (que vai por último) não pode ser trocado
raiz = instalacao("quebra")
original = atualizacao._trocar


def trocar_que_quebra(origem, destino, tentativas=40):
    if destino.name == "novidades.json" and "atualizando" in str(origem):
        raise ValueError("novidades.json está em uso por outro programa")
    return original(origem, destino, tentativas)


atualizacao._trocar = trocar_que_quebra
try:
    atualizacao.aplicar(pacote("quebra"), raiz)
    caso("quebra no meio avisa", False)
except ValueError as e:
    caso("quebra no meio avisa", "em uso" in str(e), str(e))
finally:
    atualizacao._trocar = original
caso("quebra no meio: tudo volta como era", ler(raiz, "app/nucleo/busca.py") == "velho"
     and ler(raiz, "app/VERSAO").startswith("1.4") and ler(raiz, "app/novidades.json") == "[]")
caso("quebra no meio: arquivo novo sai", ler(raiz, "app/nucleo/audio.py") is None)
caso("quebra no meio: não sobra pasta de trabalho", sorted(p.name for p in raiz.parent.iterdir()) == ["Sitcomatica"])

# zip estragado
estragado = TMP / "estragado.sitcomatica"
estragado.write_bytes(pacote("bom").read_bytes()[:-200])
try:
    atualizacao.aplicar(estragado, instalacao("estragado"))
    caso("zip estragado recusado", False)
except ValueError as e:
    caso("zip estragado recusado", "estragado" in str(e) or "não é uma atualização" in str(e), str(e))

# duas ao mesmo tempo
raiz = instalacao("duas")
dentro, solta = threading.Event(), threading.Event()


def trocar_devagar(origem, destino, tentativas=40):
    dentro.set()
    solta.wait(5)
    return original(origem, destino, tentativas)


atualizacao._trocar = trocar_devagar
primeira = threading.Thread(target=atualizacao.aplicar, args=(pacote("primeira"), raiz))
primeira.start()
dentro.wait(5)
try:
    atualizacao.aplicar(pacote("segunda"), raiz)
    caso("segunda instalação ao mesmo tempo é recusada", False)
except ValueError as e:
    caso("segunda instalação ao mesmo tempo é recusada", "Já tem uma atualização" in str(e), str(e))
finally:
    solta.set()
    primeira.join()
    atualizacao._trocar = original
caso("a primeira termina", ler(raiz, "app/nucleo/busca.py") == "novo")

# 2.0: o app virou Echo; os atalhos "Sitcomática" da cliente viram "Echo" ao abrir (a atualização não roda o instalador)
from janela.sistema import renomear_atalhos_antigos  # noqa: E402

so_velho, os_dois, nenhum = TMP / "atalhos-velho", TMP / "atalhos-dois", TMP / "atalhos-nenhum"
for pasta in (so_velho, os_dois, nenhum):
    pasta.mkdir()
(so_velho / "Sitcomática.lnk").write_bytes(b"alvo")
(os_dois / "Sitcomática.lnk").write_bytes(b"velho")
(os_dois / "Echo.lnk").write_bytes(b"novo")
renomear_atalhos_antigos([so_velho, os_dois, nenhum, TMP / "nao-existe"])
caso("atalho Sitcomática vira Echo, com o mesmo conteúdo", not (so_velho / "Sitcomática.lnk").exists()
     and (so_velho / "Echo.lnk").read_bytes() == b"alvo")
caso("com os dois, o velho sai e o Echo fica", sorted(p.name for p in os_dois.iterdir()) == ["Echo.lnk"]
     and (os_dois / "Echo.lnk").read_bytes() == b"novo")
caso("sem atalho, nada muda", not any(nenhum.iterdir()))

if falhas:
    print(f"\n{len(falhas)} falha(s): {', '.join(falhas)}")
    sys.exit(1)
print("\ntudo certo")
