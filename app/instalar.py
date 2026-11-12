r"""Instalação no Windows, chamada pelo instalar.bat com o Python que vem na pasta python\ (o oficial do
python.org, assinado: o Controle Inteligente de Aplicativos barra Python sem assinatura).

1. Tira a "marca da internet" dos arquivos da pasta (o Controle Inteligente barra o atalho se os
   arquivos que ele abre vieram marcados do zip).
2. Confere o corpus.db.
3. Cria atalhos "Echo" na Área de Trabalho e no Menu Iniciar, apontando para python\pythonw.exe.
4. (O cache das buscas é preparado pelo próprio app, em segundo plano.)

Pode rodar de novo à vontade (por exemplo, se a pasta mudar de lugar).
"""
import os
import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent
sys.path.insert(0, str(APP))

from nucleo import registro  # noqa: E402
from nucleo.registro import log  # noqa: E402
NOME = "Echo"
NOMES_ANTIGOS = ["Frases das Séries", "Sitcomática"]  # atalhos de versões anteriores, apagados ao instalar


def passo(texto):
    log.info("passo: %s", texto)
    print(f"\n» {texto}", flush=True)


def python_embutido():
    """O pythonw.exe (sem janela preta) da pasta python ao lado da pasta app. Fora do Windows (testes),
    o Python que está rodando."""
    if sys.platform == "win32":
        return APP.parent / "python" / "pythonw.exe"
    return Path(sys.executable)


def criar_atalhos():
    if sys.platform != "win32":
        print("  (atalhos só no Windows; pulado)")
        return
    def ps(caminho):  # texto entre aspas simples no PowerShell: ' vira ''
        return str(caminho).replace("'", "''")

    alvo = ps(python_embutido())
    icone = ps(APP / "janela" / "icone.ico")
    app_py, pasta_app = ps(APP / "janela" / "app.py"), ps(APP)
    antigos = ", ".join(f"'{ps(n)}'" for n in NOMES_ANTIGOS)
    script = f"""
$s = New-Object -ComObject WScript.Shell
foreach ($pasta in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {{
  foreach ($antigo in @({antigos})) {{ Remove-Item -LiteralPath (Join-Path $pasta "$antigo.lnk") -ErrorAction SilentlyContinue }}
  $a = $s.CreateShortcut((Join-Path $pasta '{NOME}.lnk'))
  $a.TargetPath = '{alvo}'
  $a.Arguments = '"{app_py}"'
  $a.WorkingDirectory = '{pasta_app}'
  $a.IconLocation = '{icone}'
  $a.Description = 'Material de aula: frases de séries e filmes, aulas e textos em áudio'
  $a.Save()
}}
"""
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], check=True)
    print("  Atalhos criados na Área de Trabalho e no Menu Iniciar.")


def tirar_marca_da_internet(raiz=None):
    """O Windows marca o que veio da internet (fluxo "Zone.Identifier" de cada arquivo), e ao extrair
    um zip a marca passa para todos os arquivos. Com ela, o Controle Inteligente de Aplicativos bloqueia
    o atalho do app. Apagar o fluxo é o que o "Desbloquear" das Propriedades e o Unblock-File fazem, só
    que aqui na pasta do app inteira. Devolve quantos arquivos estavam marcados."""
    if sys.platform != "win32":
        print("  (só no Windows; pulado)")
        return 0
    raiz = Path(raiz or APP.parent)
    marcados = 0
    for p in [raiz, *raiz.rglob("*")]:
        try:
            os.remove(f"{p}:Zone.Identifier")
            marcados += 1
        except FileNotFoundError:
            pass
        except OSError as e:
            log.warning("não consegui tirar a marca de %s: %s", p, e)
    print(f"  {marcados} arquivos estavam marcados como vindos da internet: liberados." if marcados
          else "  Nenhum arquivo marcado.")
    return marcados


def main():
    print(f"Instalando {NOME} em {APP}")

    passo("Liberando os arquivos do app")
    tirar_marca_da_internet()

    passo("Conferindo as frases das séries")
    from nucleo import bancos, busca
    corpus = bancos.caminho_corpus()
    obras = busca.listar_obras()
    print(f"  {corpus.name}: {', '.join(o['nome'] for o in obras)}")

    passo("Criando os atalhos")
    criar_atalhos()

    # preparar o cache de todas as estruturas aqui levaria muitos minutos: o app faz isso em segundo
    # plano quando abre, e cada busca nova se prepara na hora
    print(f"  Seus dados ficam em {bancos.caminho_dados().parent}")

    print(f"""
Tudo certo!
- Para abrir: clique em "{NOME}" na Área de Trabalho.
- A janela do app abre no Microsoft Edge, sem barra de endereço. Ela é só do app.
""")


if __name__ == "__main__":
    registro.configurar("instalar")
    try:
        main()
    except Exception as e:  # noqa: BLE001 — o instalar.bat mostra a mensagem e pede o print
        log.exception("instalação falhou")
        print(f"\nERRO: {registro.explicar(e)}\nPasta de erros: {registro.pasta_erros()}")
        sys.exit(1)
