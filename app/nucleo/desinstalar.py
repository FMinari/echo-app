"""Desinstalar o Echo (aba Sobre).

Sai: os atalhos "Echo" (e os "Sitcomática" de antes, na Área de Trabalho e no Menu Iniciar), o tipo de arquivo .sitcomatica no
registro da cliente (HKCU), o que o pacote pôs na pasta do app (python\\, app\\, instalar.bat, LEIA-ME.txt; a
pasta em si só se ficar vazia, porque a cliente pode ter extraído o zip na Área de Trabalho) e o perfil do Edge do app. Os dados da cliente
(estruturas, favoritos, grupos, backups) só saem se a cliente pedir; senão ficam, e só o que é derivado deles
(índice, downloads de atualização) sai.

A pasta do app não pode ser apagada com o app rodando de dentro dela: o registro e os atalhos saem na
hora, e as pastas, por um PowerShell (assinado, comando sem arquivo) que espera o app fechar e tenta de
novo por alguns segundos.
"""
import subprocess
import sys
from pathlib import Path

from . import atualizacao, bancos
from .registro import log

CHAVES = (rf"Software\Classes\{atualizacao.EXTENSAO}", r"Software\Classes\Sitcomatica.Atualizacao")
ATALHOS = ("Echo.lnk", "Sitcomática.lnk")  # o de hoje e o de até a 1.4.1
DO_PACOTE = ("app", "python", "instalar.bat", "LEIA-ME.txt")  # o que o zip põe na pasta


def _conferir_raiz(raiz):
    """Só a pasta de um app instalado: nunca o repositório, a pasta pessoal ou a raiz do disco."""
    raiz = Path(raiz).resolve()
    perigosas = {Path.home().resolve(), *Path.home().resolve().parents}
    if (raiz in perigosas or raiz == Path(raiz.anchor) or not (raiz / "app" / "VERSAO").is_file()
            or not (raiz / "python").is_dir() or not (raiz / "app" / "janela").is_dir()):
        raise ValueError("Só dá para desinstalar o app instalado (a pasta que tem python e app dentro).")
    return raiz


def plano(apagar_dados=False, raiz=None, perfil=None):
    """{"raiz": pasta do app, "pastas": [...], "arquivos": [...], "dados": pasta dos dados, "dados_ficam": bool}.
    A raiz não entra nas pastas: só sai se ficar vazia (ver script_de_limpeza)."""
    raiz = _conferir_raiz(raiz or atualizacao.RAIZ)
    dados = bancos.caminho_dados().parent
    pastas = [raiz / "app", raiz / "python"] + ([Path(perfil)] if perfil else [])
    arquivos = [raiz / nome for nome in DO_PACOTE[2:] if (raiz / nome).exists()]
    if apagar_dados:
        pastas.append(dados)
    else:  # o que é derivado: o índice (refeito sozinho) e os downloads de atualização
        arquivos += sorted(dados.glob("indice-*.db*"))
        pastas += [p for p in (dados / "atualizacoes", dados / "janela") if p.exists()]
    return {"raiz": str(raiz), "pastas": [str(p) for p in pastas], "arquivos": [str(p) for p in arquivos], "dados": str(dados),
            "dados_ficam": not apagar_dados}


def _apagar_chave(raiz, caminho):
    import winreg
    try:
        with winreg.OpenKey(raiz, caminho, 0, winreg.KEY_ALL_ACCESS) as chave:
            while True:
                try:
                    sub = winreg.EnumKey(chave, 0)
                except OSError:
                    break
                _apagar_chave(raiz, rf"{caminho}\{sub}")
        winreg.DeleteKey(raiz, caminho)
    except FileNotFoundError:
        pass


def _ps(texto):  # texto entre aspas simples no PowerShell: ' vira ''
    return "'" + str(texto).replace("'", "''") + "'"


def script_de_limpeza(alvos, raiz=None):
    """PowerShell que apaga os atalhos na hora e as pastas/arquivos quando o app soltar; depois, a `raiz`
    se ela tiver ficado vazia."""
    lista = ", ".join(_ps(a) for a in alvos)
    vazia = (f"$raiz = {_ps(raiz)}\nif ((Test-Path -LiteralPath $raiz) -and -not (Get-ChildItem -LiteralPath $raiz -Force)) "
             "{ Remove-Item -LiteralPath $raiz -Force -ErrorAction SilentlyContinue }\n") if raiz else ""
    return f"""
foreach ($pasta in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {{
  foreach ($atalho in @({", ".join(_ps(a) for a in ATALHOS)})) {{
    Remove-Item -LiteralPath (Join-Path $pasta $atalho) -Force -ErrorAction SilentlyContinue
  }}
}}
$alvos = @({lista})
Start-Sleep -Seconds 4
foreach ($i in 1..15) {{
  foreach ($a in $alvos) {{
    if (Test-Path -LiteralPath $a) {{ Remove-Item -LiteralPath $a -Recurse -Force -ErrorAction SilentlyContinue }}
  }}
  if (-not ($alvos | Where-Object {{ Test-Path -LiteralPath $_ }})) {{ break }}
  Start-Sleep -Seconds 2
}}
{vazia}"""


def executar(apagar_dados=False, perfil=None):
    """Desinstala (só no Windows, só o app instalado). O app precisa fechar logo depois."""
    if sys.platform != "win32":
        raise ValueError("Desinstalar só funciona no Windows.")
    p = plano(apagar_dados, perfil=perfil)
    log.info("desinstalando (apagar dados: %s): %s", apagar_dados, p)
    import ctypes
    import winreg
    for chave in CHAVES:
        _apagar_chave(winreg.HKEY_CURRENT_USER, chave)
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)  # SHCNE_ASSOCCHANGED
    subprocess.Popen(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
         "-Command", script_de_limpeza(p["pastas"] + p["arquivos"], p["raiz"])],
        cwd=str(Path.home()), creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
    return p
