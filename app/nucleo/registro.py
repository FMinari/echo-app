"""Registro de erros, offline e só com a biblioteca padrão.

Cada processo grava num arquivo em <pasta de dados>/erros/ (janela.log, mcp.log, instalar.log), com
data e hora e rotação de 1 MB × 3. Quando algo der errado, a cliente manda essa pasta pro dev.
"""
import logging
import logging.handlers
import platform
import sqlite3
import sys
import threading
from . import bancos

log = logging.getLogger("sitcomatica")


AVISO = "Os detalhes foram para a pasta de erros: mande ela pro desenvolvedor."


class NaoEncontrado(KeyError):
    """Algo que a cliente pediu não existe (estrutura, frase). A mensagem é para a cliente, não é bug."""

    def __str__(self):
        return str(self.args[0]) if self.args else ""


def pasta_erros():
    return bancos.caminho_dados().parent / "erros"


class _ParaOLog:
    """No atalho (pythonw) stdout e stderr são None: o que bibliotecas escreverem ali vira linha no log."""

    def __init__(self, nivel):
        self.nivel, self.resto = nivel, ""

    def write(self, texto):
        self.resto += texto
        *linhas, self.resto = self.resto.split("\n")
        for linha in linhas:
            if linha.strip():
                log.log(self.nivel, linha)
        return len(texto)

    def flush(self):
        pass

    def isatty(self):
        return False


def configurar(nome):
    """Chame uma vez, logo no começo do processo. `nome` vira o arquivo: erros/<nome>.log."""
    formato = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    try:
        pasta = pasta_erros()
        pasta.mkdir(parents=True, exist_ok=True)
        saida = logging.handlers.RotatingFileHandler(
            pasta / f"{nome}.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8", delay=True)
    except OSError:  # sem como gravar: melhor seguir sem arquivo do que não abrir
        saida = logging.StreamHandler(sys.stderr) if sys.stderr else logging.NullHandler()
    saida.setFormatter(formato)
    # falha ao gravar o log (disco cheio, arquivo preso na rotação) não pode virar erro: com o stderr
    # apontando para o próprio log (pythonw), cada falha geraria outra, sem fim
    logging.raiseExceptions = False
    log.handlers[:] = [saida]
    log.setLevel(logging.INFO)
    log.propagate = False
    if sys.stdout is None:
        sys.stdout = _ParaOLog(logging.INFO)
    if sys.stderr is None:
        sys.stderr = _ParaOLog(logging.WARNING)
    sys.excepthook = lambda tipo, valor, tb: log.critical("erro não tratado", exc_info=(tipo, valor, tb))
    threading.excepthook = lambda a: log.error(
        "erro na tarefa %s", a.thread.name if a.thread else "?", exc_info=(a.exc_type, a.exc_value, a.exc_traceback))
    log.info("%s aberto · app %s · banco %s · %s · Python %s",
             nome, _versao_app(), _rotulo_corpus(), platform.platform(), platform.python_version())
    return log


def _versao_app():
    try:
        from . import sobre  # aqui dentro: sobre importa busca, que importa este módulo
        return sobre.versao_app()
    except Exception as e:  # noqa: BLE001 — é só informação para o log
        return f"indisponível ({e})"


def _rotulo_corpus():
    try:
        from . import busca
        return busca.rotulo_corpus()
    except Exception as e:  # noqa: BLE001 — é só informação para o log
        return f"indisponível ({e})"


def explicar(erro):
    """Texto para a cliente sobre um erro inesperado (o traceback já foi para o log)."""
    texto = str(erro).lower()
    if isinstance(erro, sqlite3.OperationalError) and "locked" in texto:
        return "O banco está ocupado (talvez o Claude esteja usando ao mesmo tempo). Tente de novo daqui a pouco."
    if isinstance(erro, sqlite3.DatabaseError) and ("not a database" in texto or "malformed" in texto):
        return "Um dos arquivos do app parece estragado. " + AVISO
    if isinstance(erro, FileNotFoundError) and "corpus.db" in texto:
        return "Não achei o arquivo de frases (corpus.db) na pasta do app. Peça um novo pro desenvolvedor."
    return "Algo deu errado. " + AVISO
