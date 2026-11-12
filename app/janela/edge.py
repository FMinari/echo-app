"""Abre a tela no Microsoft Edge em modo aplicativo (assinado e já instalado no Windows)."""
import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

from nucleo.registro import log


def perfil_do_edge():
    """O Edge do app usa um perfil só dele: não mistura com o navegador da cliente. Fica em %LOCALAPPDATA%
    (é grande e não precisa ir junto com o perfil do Windows)."""
    if sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "FrasesSeries" / "edge"
    return Path.home() / ".cache" / "frases-series" / "navegador"


def achar_edge():
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        if base and (edge := Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe").exists():
            return edge
    return None


def abrir_janela(endereco):
    """Edge em modo aplicativo, com perfil próprio. Sem Edge (ou fora do Windows), um Chrome/Chromium
    em modo aplicativo; sem nenhum, o navegador padrão."""
    perfil = perfil_do_edge()
    opcoes = [f"--app={endereco}", f"--user-data-dir={perfil}", "--no-first-run",
              "--no-default-browser-check", "--window-size=1180,820"]
    if sys.platform == "win32":
        if edge := achar_edge():
            subprocess.Popen([str(edge), *opcoes],
                             creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
            return
    else:
        for nome in ("microsoft-edge", "chromium", "google-chrome", "chromium-browser"):
            if programa := shutil.which(nome):
                subprocess.Popen([programa, *opcoes], start_new_session=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
    log.warning("sem Edge: abrindo no navegador padrão")
    webbrowser.open(endereco)
