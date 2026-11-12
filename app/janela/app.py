"""Ponto de partida da janela (ver janela/__init__.py): o atalho, os dois cliques num .sitcomatica
e o modo de desenvolvimento.

Rodar:  python janela/app.py [arquivo de atualização]
Dev:    python janela/app.py --navegador [--porta 8765]   (só o servidor: abra o endereço que ele mostra)
"""
import json
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

# o Python embutido do PC da cliente não põe a pasta do script no caminho: nucleo e janela vêm de app/
APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))



def _falhou_ao_carregar():
    """O código do app não carregou (atualização pela metade, arquivo apagado): sem isso, pelo atalho
    (pythonw) a cliente não veria nada. Grava o erro no log sem depender do resto do app e avisa numa caixa."""
    import traceback
    texto = traceback.format_exc()
    base = Path(os.environ.get("APPDATA") or Path.home()) / "FrasesSeries" if sys.platform == "win32" \
        else Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "frases-series"
    try:
        (base / "erros").mkdir(parents=True, exist_ok=True)
        with open(base / "erros" / "janela.log", "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} CRITICAL o app não carregou\n{texto}\n")
    except OSError:
        pass
    aviso = ("O Echo não conseguiu abrir: falta um pedaço do app (talvez uma atualização não "
             "terminou). Baixe o pacote completo de novo e instale por cima; seus dados ficam.")
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, aviso, "Echo", 0x10)
    else:
        print(aviso, texto, file=sys.__stderr__ or sys.stderr)
    sys.exit(1)


try:
    from janela.api import Api
    from janela.edge import abrir_janela
    from janela.servidor import PORTA, Servidor
    from janela.sistema import avisar_falha_ao_abrir, registrar_tipo_de_arquivo, renomear_atalhos_antigos
    from nucleo import atualizacao, bancos, busca, indice, registro
    from nucleo.registro import log
except Exception:  # noqa: BLE001
    _falhou_ao_carregar()


def preparar_em_segundo_plano():
    """Backup do dia, índice das frases e cache das buscas, numa thread para a janela abrir logo. Falha
    aqui só vai para o log: nada disso impede de usar o app."""
    def preparar():
        try:
            if copia := bancos.fazer_backup():
                log.info("backup: %s", copia)
        except Exception:  # noqa: BLE001
            log.exception("backup do dados.db falhou")
        if sys.platform == "win32":
            try:
                registrar_tipo_de_arquivo()
            except Exception:  # noqa: BLE001 — sem isso a cliente só perde o "dois cliques"
                log.exception("registrar o tipo .sitcomatica")
            try:
                renomear_atalhos_antigos()
            except Exception:  # noqa: BLE001 — sem isso o atalho só continua com o nome antigo
                log.exception("renomear os atalhos do Sitcomática")
        try:
            indice.construir()  # ~10 s na primeira vez depois de uma atualização do banco; depois, nada
        except Exception:  # noqa: BLE001 — sem índice a busca só fica mais lenta
            log.exception("montar o índice das frases")
        busca.aquecer()  # erro aqui cai no threading.excepthook, que grava no log
    threading.Thread(target=preparar, name="preparar", daemon=True).start()


def pasta_janela():
    return bancos.caminho_dados().parent / "janela"


def _pedir_ao_aberto(aberto, metodo, *args):
    pedido = urllib.request.Request(
        f"http://127.0.0.1:{aberto['porta']}/api/{metodo}", data=json.dumps(args).encode(), method="POST",
        headers={"X-Sitcomatica": aberto["senha"], "Content-Type": "application/json"})
    with urllib.request.urlopen(pedido, timeout=3) as r:
        return json.loads(r.read())


def reaproveitar_aberto(pedido):
    """Já tem um Echo aberto? Abre outra janela nele (e passa o arquivo de atualização, se veio
    um) e devolve True."""
    arquivo = pasta_janela() / "aberto.json"
    try:
        aberto = json.loads(arquivo.read_text(encoding="utf-8"))
        _pedir_ao_aberto(aberto, "sinal")
    except (OSError, ValueError, KeyError):
        return False
    if pedido:
        _pedir_ao_aberto(aberto, "receber_pedido", pedido)
    abrir_janela(aberto["endereco"])
    log.info("já estava aberto (porta %s): só abri outra janela", aberto["porta"])
    return True


def criar_servidor(api, esperar):
    """Na porta de sempre; depois de uma atualização, espera o app velho soltá-la. Ocupada por outro
    programa: uma porta qualquer (aí a tela não lembra as preferências desta vez)."""
    limite = time.time() + esperar
    while True:
        try:
            return Servidor(api)
        except OSError:
            if time.time() > limite:
                log.warning("porta %s ocupada: usando outra", PORTA)
                return Servidor(api, porta=0)
            time.sleep(0.3)


def rodar_janela(pedido=None, depois_de_atualizar=False):
    if not depois_de_atualizar and reaproveitar_aberto(pedido):
        return
    api = Api(pedido)
    servidor = criar_servidor(api, esperar=15 if depois_de_atualizar else 0)
    pasta_janela().mkdir(parents=True, exist_ok=True)
    aberto = pasta_janela() / "aberto.json"
    aberto.write_text(json.dumps({"porta": servidor.porta, "senha": servidor.senha, "endereco": servidor.endereco,
                                  "pid": os.getpid()}), encoding="utf-8")
    preparar_em_segundo_plano()
    abrir_janela(servidor.endereco)
    log.info("servidor da janela na porta %s", servidor.porta)
    try:
        servidor.rodar()
    finally:
        try:
            if json.loads(aberto.read_text(encoding="utf-8")).get("pid") == os.getpid():
                aberto.unlink()
        except (OSError, ValueError):
            pass


def rodar_navegador(porta):
    """Modo de desenvolvimento: só o servidor, sem fechar sozinho; o endereço vai para o terminal."""
    servidor = Servidor(Api(), porta=porta, desenvolvimento=True)
    preparar_em_segundo_plano()
    print(servidor.endereco, flush=True)
    servidor.rodar()


if __name__ == "__main__":
    registro.configurar("janela")
    if "--navegador" in sys.argv:
        i = sys.argv.index("--porta") + 1 if "--porta" in sys.argv else None
        rodar_navegador(int(sys.argv[i]) if i else 8765)
    else:
        # dois cliques num .sitcomatica: o Windows abre o app com o caminho do arquivo
        pedido = next((a for a in sys.argv[1:] if not a.startswith("--") and Path(a).suffix.lower()
                       in (atualizacao.EXTENSAO, ".zip", ".db") and Path(a).is_file()), None)
        if pedido:
            log.info("aberto com o arquivo %s", pedido)
        try:
            rodar_janela(pedido, depois_de_atualizar="--depois-de-atualizar" in sys.argv)
        except Exception as e:  # noqa: BLE001 — sem isso, pelo atalho a cliente não veria nada
            log.critical("a janela não abriu", exc_info=True)
            avisar_falha_ao_abrir(e)
            sys.exit(1)
