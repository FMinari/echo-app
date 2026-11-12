"""O que é do Windows: o tipo de arquivo .sitcomatica, os atalhos da época do Sitcomática e a mensagem de erro
quando nem a janela abre."""
import sys
from pathlib import Path

from janela import ICONE, PASTA
from nucleo import atualizacao, registro
from nucleo.registro import log


def registrar_tipo_de_arquivo():
    """Dois cliques num .sitcomatica abrem o app com o arquivo (Windows). Fica na parte do registro
    que é da cliente (HKCU), sem pedir administrador, e é refeito a cada abertura: se a pasta do app mudar
    de lugar, o "abrir com" acompanha. Feito pelo app, e não pelo instalador, porque a atualização
    pelo app não roda o instalador."""
    import ctypes
    import winreg
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    comando = f'"{pythonw if pythonw.exists() else sys.executable}" "{PASTA / "app.py"}" "%1"'
    chaves = {
        rf"Software\Classes\{atualizacao.EXTENSAO}": "Sitcomatica.Atualizacao",
        r"Software\Classes\Sitcomatica.Atualizacao": "Atualização do Echo",
        r"Software\Classes\Sitcomatica.Atualizacao\DefaultIcon": str(ICONE),
        r"Software\Classes\Sitcomatica.Atualizacao\shell\open\command": comando,
    }
    mudou = False
    for caminho, valor in chaves.items():
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, caminho) as chave:
            try:
                atual = winreg.QueryValue(chave, None)
            except OSError:
                atual = None
            if atual != valor:
                winreg.SetValue(chave, None, winreg.REG_SZ, valor)
                mudou = True
    if mudou:
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)  # SHCNE_ASSOCCHANGED: atualiza os ícones
        log.info("tipo .sitcomatica registrado: %s", comando)


def _pastas_dos_atalhos():
    """Área de Trabalho e Menu Iniciar › Programas da cliente (as de verdade, mesmo se estiverem no OneDrive): as mesmas
    do GetFolderPath('Desktop'/'Programs') que o instalar.py usa para criar os atalhos."""
    import ctypes
    pastas = []
    for csidl in (0x10, 0x02):  # CSIDL_DESKTOPDIRECTORY, CSIDL_PROGRAMS
        caminho = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, caminho) == 0:
            pastas.append(Path(caminho.value))
    return pastas


def renomear_atalhos_antigos(pastas=None):
    """Até a 1.4.1 o app se chamava Sitcomática. A atualização pelo app não roda o instalador, então é o app que
    troca, ao abrir, o "Sitcomática.lnk" da cliente por "Echo.lnk": o mesmo atalho (mesmo alvo; o ícone vem do
    icone.ico novo), só com o nome novo. Se a cliente já tiver os dois (rodou o instalador da 2.0), o velho sai."""
    for pasta in pastas if pastas is not None else _pastas_dos_atalhos():
        velho, novo = Path(pasta) / "Sitcomática.lnk", Path(pasta) / "Echo.lnk"
        if not velho.exists():
            continue
        try:
            if novo.exists():
                velho.unlink()
            else:
                velho.rename(novo)
            log.info("atalho %s virou %s", velho, novo)
        except OSError:
            log.warning("renomear o atalho %s", velho, exc_info=True)


def avisar_falha_ao_abrir(erro):
    """Sem janela não tem onde mostrar o erro: no Windows, uma caixa de mensagem nativa."""
    texto = (f"O Echo não conseguiu abrir.\n\n{registro.explicar(erro)}\n\n"
             f"Pasta de erros:\n{registro.pasta_erros()}")
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, texto, "Echo", 0x10)  # ícone de erro
    else:
        print(texto, file=sys.__stderr__ or sys.stderr)
