"""Servidor local da tela: só a biblioteca padrão do Python (no PC da cliente não há outra, ver F16)."""
import hashlib
import hmac
import json
import mimetypes
import re
import secrets
import sys
import threading
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from janela import UI
from nucleo import bancos, registro, sobre
from nucleo.registro import NaoEncontrado, log

# A tela usa módulos JS, que o navegador só aceita com o tipo certo; no Windows o Python tira o tipo
# do registro, que às vezes diz que .js é text/plain (e aí a tela ficaria em branco).
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")

PORTA = 47321  # sempre a mesma: as preferências da tela (localStorage) são guardadas por endereço
SEM_SINAL = 150  # segundos sem notícia da tela para o app fechar (janela minimizada avisa 1 vez/minuto)
FECHANDO = 8  # depois que a tela avisa que está fechando, espera isso (pode ser só um recarregar)
PAUSA_MAXIMA = 3600  # a tela pode pedir para não contar o tempo (a impressão trava o JS do Edge)
ACORDOU = 15  # o vigia confere a cada 2 s: um buraco maior que isso é o computador voltando da suspensão
LIMITE_ARQUIVO = 1_000_000_000


class _HTTP(ThreadingHTTPServer):
    # no Windows, SO_REUSEADDR deixaria um segundo app "roubar" a porta de quem já está aberto
    allow_reuse_address = sys.platform != "win32"
    daemon_threads = True


class Servidor:
    """Servidor HTTP da janela. Só aceita 127.0.0.1 com o nome certo no Host (outro site não consegue
    se passar pelo app) e, nos pedidos à Api, a senha da sessão: no cabeçalho X-Sitcomatica, que o
    navegador não deixa outro site mandar sem pedir licença, ou no endereço (o aviso de "fechando")."""

    def __init__(self, api, porta=PORTA, desenvolvimento=False):
        self.api = api
        api._servidor = self
        self.desenvolvimento = desenvolvimento
        self.senha = secrets.token_urlsafe(24)
        # janela (id que cada página sorteia) -> último sinal; o app fecha quando nenhuma der sinal
        self.janelas = {}
        self.inicio = time.monotonic() + 60  # o Edge pode demorar para abrir na primeira vez
        self._trava = threading.Lock()
        self.http = _HTTP(("127.0.0.1", porta), self._handler())
        self.porta = self.http.server_address[1]
        self.hosts = {f"127.0.0.1:{self.porta}", f"localhost:{self.porta}"}

    @property
    def endereco(self):
        # a versão no endereço: quem vem de uma versão antiga não reaproveita a tela guardada
        marca = hashlib.sha1(sobre.versao_app().encode()).hexdigest()[:10]
        return f"http://127.0.0.1:{self.porta}/?v={marca}&t={self.senha}"

    def sinal(self, janela="", fechando=False, pausa=0):
        """A janela `janela` está viva (ou fechando: sobra FECHANDO segundos para ela, que pode ser só um
        recarregar; ou vai ficar `pausa` segundos sem poder dar sinal)."""
        agora = time.monotonic()
        with self._trava:
            if fechando:
                self.janelas[janela] = agora - (SEM_SINAL - FECHANDO)
            else:
                self.janelas[janela] = max(agora + min(max(pausa, 0), PAUSA_MAXIMA), self.janelas.get(janela, 0))

    def aberta(self, agora=None):
        agora = time.monotonic() if agora is None else agora
        with self._trava:
            return agora < self.inicio or any(agora - t < SEM_SINAL for t in self.janelas.values())

    def _acordou(self):
        """Depois da suspensão as janelas ainda não tiveram tempo de dar sinal: conta como se tivessem."""
        agora = time.monotonic()
        with self._trava:
            self.janelas = {j: max(t, agora - SEM_SINAL + 60) for j, t in self.janelas.items()}

    def rodar(self):
        if not self.desenvolvimento:
            threading.Thread(target=self._vigiar, name="vigia", daemon=True).start()
        self.http.serve_forever()

    def parar(self):
        threading.Thread(target=self.http.shutdown, daemon=True).start()

    def _vigiar(self):
        antes = time.monotonic()
        while True:
            time.sleep(2)
            agora = time.monotonic()
            if agora - antes > ACORDOU:
                log.info("o computador voltou da suspensão (%.0f s parado)", agora - antes)
                self._acordou()
            antes = agora
            if not self.aberta(agora):
                break
        log.info("a janela fechou: fechando o app")
        self.http.shutdown()

    def _handler(self):
        servidor, api = self, self.api

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *a, **k):
                super().__init__(*a, directory=str(UI), **k)

            def _host_ok(self):
                if self.headers.get("Host") in servidor.hosts:
                    return True
                self.send_error(403)
                return False

            def do_GET(self):  # noqa: N802
                if self._host_ok():
                    super().do_GET()

            def do_HEAD(self):  # noqa: N802
                if self._host_ok():
                    super().do_HEAD()

            def do_POST(self):  # noqa: N802
                if not self._host_ok():
                    return
                url = urlsplit(self.path)
                senha = self.headers.get("X-Sitcomatica") or parse_qs(url.query).get("t", [""])[0]
                if not hmac.compare_digest(senha.encode(), servidor.senha.encode()):
                    self.send_error(403)
                    return
                metodo = url.path.removeprefix("/api/")
                try:
                    tamanho = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    self.send_error(400)
                    return
                janela = self.headers.get("X-Janela") or parse_qs(url.query).get("j", [""])[0]
                servidor.sinal(janela)
                if metodo == "enviar_atualizacao":
                    return self._json(self._receber_arquivo(tamanho))
                if metodo.startswith("_") or not (metodo in ("sinal", "fechando") or callable(getattr(api, metodo, None))):
                    self.send_error(404)
                    return
                try:
                    args = json.loads(self.rfile.read(tamanho) or "[]")
                except ValueError:
                    self.send_error(400)
                    return
                if metodo in ("sinal", "fechando"):
                    pausa = args[0].get("pausa", 0) if args and isinstance(args[0], dict) else 0
                    servidor.sinal(janela, fechando=metodo == "fechando",
                                   pausa=pausa if isinstance(pausa, (int, float)) else 0)
                    return self._json({"ok": True})
                if not isinstance(args, list):
                    args = [args]
                try:
                    resposta = getattr(api, metodo)(*args)
                except Exception as e:  # noqa: BLE001 — argumentos errados num método sem @_seguro
                    log.exception("erro em %s", metodo)
                    resposta = {"erro": registro.explicar(e), "inesperado": True}
                self._json(resposta)

            def _receber_arquivo(self, tamanho):
                """O arquivo de atualização escolhido na tela, gravado em <dados>/atualizacoes (e apagado se
                não for uma atualização)."""
                destino = None
                try:
                    if not 0 < tamanho <= LIMITE_ARQUIVO:
                        raise ValueError("Esse arquivo não é uma atualização do Echo.")
                    nome = Path(urllib.request.unquote(self.headers.get("X-Nome") or "")).name
                    nome = re.sub(r'[\\/:*?"<>|]', "_", nome) or "atualizacao"
                    if Path(nome).suffix.lower() not in (".sitcomatica", ".zip", ".db"):
                        raise ValueError("Escolha o arquivo .sitcomatica (ou .zip, ou corpus.db) que o desenvolvedor mandou.")
                    destino = bancos.caminho_dados().parent / "atualizacoes" / nome
                    destino.parent.mkdir(parents=True, exist_ok=True)
                    with open(destino, "wb") as f:
                        falta = tamanho
                        while falta:
                            pedaco = self.rfile.read(min(falta, 1 << 20))
                            if not pedaco:
                                raise ValueError("O envio do arquivo parou no meio. Tente de novo.")
                            f.write(pedaco)
                            falta -= len(pedaco)
                    return api.receber_atualizacao(str(destino))
                except (NaoEncontrado, ValueError) as e:
                    self._apagar(destino)
                    return {"erro": str(e)}
                except Exception as e:  # noqa: BLE001
                    log.exception("receber arquivo de atualização")
                    self._apagar(destino)
                    return {"erro": registro.explicar(e), "inesperado": True}

            @staticmethod
            def _apagar(destino):
                try:
                    if destino:
                        destino.unlink(missing_ok=True)
                except OSError:
                    log.warning("apagar o arquivo recusado %s", destino, exc_info=True)

            def _json(self, dados):
                corpo = json.dumps(dados, ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)

            def end_headers(self):
                # sem isso, depois de uma atualização a janela podia reaproveitar módulos JS antigos
                self.send_header("Cache-Control", "no-store")
                super().end_headers()

            def log_message(self, *a):
                pass

        return Handler
