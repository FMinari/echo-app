"""Os métodos que a tela chama: cada um vira POST /api/<método> (ver servidor.py)."""
import os
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path

from janela import APP, UI
from janela.edge import perfil_do_edge
from nucleo import (atualizacao, audio, aulas, bancos, blocos, busca, catalogo, desinstalar, dicionario, favoritos,
                    github, grupos, indice, livre, registro, sobre, textos)
from nucleo.registro import NaoEncontrado, log


def _seguro(func):
    """Erros viram {"erro": mensagem} para a interface mostrar. Os previstos (NaoEncontrado,
    ValueError) já vêm com texto para a cliente; os inesperados vão para o log com traceback e chegam
    com `inesperado`, para a tela oferecer a pasta de erros."""
    def envolvida(self, *args):
        try:
            return func(self, *args)
        except (NaoEncontrado, ValueError) as e:
            return {"erro": str(e)}
        except sqlite3.IntegrityError as e:
            if "UNIQUE" in str(e):
                return {"erro": "Já existe uma estrutura com esse nome."}
            log.exception("erro em %s%r", func.__name__, args)
            return {"erro": registro.explicar(e), "inesperado": True}
        except Exception as e:  # noqa: BLE001 — a interface mostra qualquer falha
            log.exception("erro em %s%r", func.__name__, args)
            return {"erro": registro.explicar(e), "inesperado": True}
    envolvida.__name__ = func.__name__
    return envolvida


class Api:
    def __init__(self, pedido=None):
        self._servidor = None  # o Servidor desta janela (None nos testes do núcleo)
        self._pedido = pedido  # arquivo de atualização com que o app foi aberto (dois cliques nele)
        self._download = None  # progresso do download de uma versão do GitHub

    @_seguro
    def inicio(self):
        return {"estruturas": catalogo.listar(), "obras": busca.listar_obras(),
                "grupos": grupos.listar(), "versao": sobre.numero(), "data": sobre.data(),
                "pecas": blocos.catalogo_de_pecas(), "acervo": bancos.estado_acervo()}

    @_seguro
    def ligar_acervo(self, ligado):
        """Interruptor "Acervo livre": a escolha fica guardada; a tela recarrega com o banco novo."""
        busca._AVULSAS.clear()  # buscas avulsas guardam ids de frase do banco de antes
        estado = bancos.ligar_acervo(ligado)
        threading.Thread(target=indice.construir, name="indice", daemon=True).start()
        return estado

    @_seguro
    def sobre(self):
        return sobre.estado()

    @_seguro
    def falantes(self, obras):
        return busca.listar_falantes(obras or None, minimo=15)

    @_seguro
    def buscar(self, p):
        """Com `texto`, é a busca escrita (livre.py: nada fica salvo); senão, a estrutura do catálogo."""
        filtros = dict(obras=p.get("obras") or None, falante=p.get("falante") or None,
                       temporada=p.get("temporada") or None, limite=int(p.get("por_pagina") or 10),
                       semente=int(p.get("semente") or 0), pagina=p.get("pagina") or 1,
                       filtro=p.get("filtro") or None, por_tipo=True)
        if p.get("texto"):
            r = livre.buscar(p["texto"], outras_formas=p.get("outras_formas", True),
                             tempo=p.get("tempo") or None, **filtros)
        else:
            r = busca.buscar(estrutura=p["estrutura"], **filtros)
        self._marcar_guardadas(r["resultados"])
        return r

    @_seguro
    def phrasal_verbs(self, p):
        """Os phrasal verbs do verbo que a cliente escreveu (uma palavra só), com as mesmas obras e filtros."""
        return livre.phrasal_verbs(p.get("texto") or "", tempo=p.get("tempo") or None,
                                   obras=p.get("obras") or None, falante=p.get("falante") or None,
                                   temporada=p.get("temporada") or None)

    @staticmethod
    def _marcar_guardadas(resultados):
        """Cada resultado diz se já está guardado (`favorito`) e em qual aula (`aula`: nome ou None)."""
        nomes = {a["id"]: a["nome"] for a in aulas.listar()["aulas"]}
        guardadas = {(f["arquivo"], f["frase"]): f["aula_id"] for f in favoritos.listar()}
        for x in resultados:
            chave = (x["arquivo"], x["frase"])
            x["favorito"] = chave in guardadas
            x["aula"] = nomes.get(guardadas.get(chave)) if x["favorito"] else None

    def registrar_erro_js(self, dados):
        """Erro da interface (window.onerror / promessa rejeitada sem tratamento)."""
        dados = dados if isinstance(dados, dict) else {"mensagem": str(dados)}
        log.error("JS: %s\n%s", str(dados.get("mensagem"))[:500], str(dados.get("pilha") or "")[:2000])
        return {"ok": True}

    @_seguro
    def abrir_pasta_erros(self):
        pasta = registro.pasta_erros()
        pasta.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(pasta)  # noqa: S606 — abre o Explorador na pasta
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(pasta)])
        return {"pasta": str(pasta)}

    # ---------- atualização ----------
    @_seguro
    def procurar_atualizacao(self):
        """O arquivo com que o app foi aberto (dois cliques num .sitcomatica), na primeira vez; senão,
        o pacote mais novo em Downloads (ou None)."""
        if self._pedido:
            pedido, self._pedido = self._pedido, None
            pacote = atualizacao.ler_pacote(pedido)
            pacote["mais_novo"] = atualizacao.e_mais_novo(pacote)
            return pacote
        local = atualizacao.procurar()
        remoto = github.mais_nova(atualizacao._gerado_em_local())
        if remoto and (not local or local["tipo"] != "app"
                       or atualizacao.numero_tupla(remoto["numero"]) > atualizacao.numero_tupla(local["numero"])):
            return remoto
        return local

    @_seguro
    def estado_github(self):
        """Situação da última consulta ao GitHub (a tela avisa quando o token expirou)."""
        if github.estado["situacao"] is None:
            github.releases()
        return dict(github.estado)

    @_seguro
    def abrir_link(self, url):
        """E-mail e páginas do Contato abrem no programa padrão do sistema, fora da janela do app."""
        import webbrowser
        if not str(url).startswith(("mailto:", "https://")):
            raise ValueError("Link não permitido.")
        webbrowser.open(url)
        return {"ok": True}

    @_seguro
    def versoes(self):
        """Versões publicadas no GitHub para escolher (vazio sem token ou sem internet)."""
        versoes = github.versoes(atualizacao._gerado_em_local())
        return {"ligado": github.config() is not None, "situacao": github.estado["situacao"], "versoes": versoes}

    @_seguro
    def baixar_atualizacao(self, pacote):
        """Começa a baixar uma versão do GitHub numa thread; a tela acompanha por progresso_download."""
        destino = bancos.caminho_dados().parent / "atualizacoes" / pacote["asset"]["nome"]
        self._download = {"feito": 0, "total": pacote["asset"].get("tamanho") or 0, "arquivo": None, "erro": None}

        def baixar():
            try:
                arquivo = github.baixar(pacote["asset"], destino,
                                        lambda feito, total: self._download.update(feito=feito, total=total))
                self._download["arquivo"] = str(arquivo)
                log.info("baixado do GitHub: %s", arquivo)
            except Exception as e:  # noqa: BLE001 — a tela mostra
                log.exception("download do GitHub")
                self._download["erro"] = str(e) if isinstance(e, ValueError) else registro.explicar(e)
        threading.Thread(target=baixar, name="download", daemon=True).start()
        return {"ok": True}

    @_seguro
    def progresso_download(self):
        return self._download or {}

    def receber_atualizacao(self, caminho):
        """Arquivo escolhido em "Escolher arquivo…" (a tela manda o conteúdo; o servidor grava)."""
        pacote = atualizacao.conferir_minima(atualizacao.ler_pacote(caminho))
        pacote["mais_novo"] = atualizacao.e_mais_novo(pacote)
        return pacote

    def receber_pedido(self, arquivo):
        """Dois cliques num .sitcomatica com o app já aberto: a outra abertura passa o arquivo para cá."""
        self._pedido = arquivo
        return {"ok": True}

    @_seguro
    def aplicar_atualizacao(self, arquivo):
        log.info("aplicando atualização: %s", arquivo)
        r = atualizacao.aplicar(arquivo)
        log.info("atualização aplicada: %s", r)
        baixados = bancos.caminho_dados().parent / "atualizacoes"
        if Path(arquivo).parent == baixados:  # o que veio do GitHub não precisa ficar ocupando espaço
            Path(arquivo).unlink(missing_ok=True)
        return r

    @_seguro
    def reiniciar(self):
        """Reabre o app depois de uma atualização: um processo novo (com o código novo) abre outra
        janela, e este solta a porta logo depois de responder. A tela velha se fecha sozinha."""
        if self._servidor is None or self._servidor.desenvolvimento:
            return {"ok": True, "sem_janela": True}
        argumentos = [sys.executable, str(UI.parent / "app.py"), "--depois-de-atualizar"]
        if sys.platform == "win32":
            try:  # deixa a janela nova vir para a frente (o Windows só deixa quem está na frente passar a vez)
                import ctypes
                ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY
            except Exception:  # noqa: BLE001
                log.exception("AllowSetForegroundWindow")
            subprocess.Popen(argumentos, cwd=APP,
                             creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            subprocess.Popen(argumentos, cwd=APP, start_new_session=True)
        log.info("reabrindo o app depois da atualização")
        threading.Timer(0.5, self._servidor.parar).start()
        return {"ok": True}

    # ---------- desinstalar ----------
    @_seguro
    def plano_desinstalar(self):
        """Para a aba Sobre mostrar o que sai (ou por que não dá, ex.: fora do app instalado)."""
        try:
            return {"pode": sys.platform == "win32", **desinstalar.plano(perfil=perfil_do_edge()),
                    "motivo": None if sys.platform == "win32" else "Desinstalar só funciona no Windows."}
        except ValueError as e:
            return {"pode": False, "motivo": str(e)}

    @_seguro
    def desinstalar(self, apagar_dados=False):
        r = desinstalar.executar(bool(apagar_dados), perfil=perfil_do_edge())
        if self._servidor is not None and not self._servidor.desenvolvimento:
            threading.Timer(1.0, self._servidor.parar).start()  # o app fecha e solta a pasta
        return r

    @_seguro
    def criar_grupo(self, nome, obras):
        grupos.criar(nome, obras)
        return grupos.listar()

    @_seguro
    def apagar_grupo(self, grupo_id):
        grupos.apagar(grupo_id)
        return grupos.listar()

    @_seguro
    def favoritar(self, resultado, aula_id=None):
        """Guarda a frase na aula (None = "Sem aula"); já guardada, muda para essa aula."""
        return {"id": favoritos.guardar(resultado, aula_id=aula_id)}

    @_seguro
    def desfavoritar(self, arquivo, frase):
        for f in favoritos.listar():
            if (f["arquivo"], f["frase"]) == (arquivo, frase):
                favoritos.remover(f["id"])
        return {"ok": True}

    @_seguro
    def falso_positivo(self, estrutura, resultado):
        catalogo.marcar_falso_positivo(estrutura, resultado["arquivo"], resultado["frase"],
                                       resultado.get("frase_id"))
        return {"ok": True}

    @_seguro
    def estruturas(self):
        return catalogo.listar()

    @_seguro
    def salvar_estrutura(self, dados):
        dados = {k: (v if v != "" else None) for k, v in dados.items()}
        dados["exemplos"] = [l.strip() for l in (dados.get("exemplos") or "").splitlines() if l.strip()]
        if dados.get("id"):
            e = catalogo.editar(dados.pop("id"), **dados)
        else:
            dados.pop("id", None)
            e = catalogo.criar(**dados, origem="usuario")
        return e

    @_seguro
    def guardar_busca(self, p):
        """A busca escrita vira estrutura do catálogo (Buscar → Escrever → "Guardar como estrutura")."""
        return livre.guardar(p.get("texto") or "", outras_formas=p.get("outras_formas", True),
                             tempo=p.get("tempo") or None, nome=p.get("nome"), categoria=p.get("categoria"))

    @_seguro
    def apagar_estrutura(self, id_):
        catalogo.apagar(id_)
        return {"ok": True}

    @_seguro
    def testar_regra(self, dados):
        padrao, texto, excluir = catalogo.regra({k: (v or None) for k, v in dados.items()})
        r = busca.buscar(padrao=padrao, texto=texto, excluir=excluir, limite=6,
                         semente=int(dados.get("semente") or 0))
        return r

    @_seguro
    def favoritos(self):
        return favoritos.listar()

    @_seguro
    def dicionario(self, palavra):
        return dicionario.procurar(palavra)

    @_seguro
    def salvar_audio(self, x, voz=None, velocidade="normal"):
        """A frase num .wav em Músicas › Echo, com a voz do "Ouvir" (se for do Windows)."""
        return audio.salvar(x, voz, velocidade)

    @_seguro
    def mostrar_audio(self, arquivo):
        audio.mostrar(arquivo)
        return {"ok": True}

    # ---------- aulas ----------
    @_seguro
    def aulas(self):
        return aulas.listar()

    @_seguro
    def criar_aula(self, nome):
        return aulas.criar(nome)

    @_seguro
    def renomear_aula(self, aula_id, nome):
        return aulas.renomear(aula_id, nome)

    @_seguro
    def apagar_aula(self, aula_id):
        aulas.apagar(aula_id)
        return {"ok": True}

    @_seguro
    def frases_da_aula(self, aula_id=None):
        return aulas.frases(aula_id)

    @_seguro
    def mover_frase(self, frase_id, aula_id=None):
        aulas.mover(frase_id, aula_id)
        return {"ok": True}

    @_seguro
    def anotar_frase(self, frase_id, nota):
        aulas.anotar(frase_id, nota)
        return {"ok": True}

    @_seguro
    def folha(self, aula_id=None):
        return aulas.folha(aula_id)

    # ---------- textos ----------
    @_seguro
    def textos(self, aula_id="todas"):
        """Todos ("todas"), os de uma aula, ou os de "Sem aula" (None); sem o corpo."""
        return textos.listar() if aula_id == "todas" else textos.listar(aula_id)

    @_seguro
    def texto(self, texto_id):
        return textos.obter(texto_id)

    @_seguro
    def salvar_texto(self, dados):
        """Sem `id`, cria; com `id`, regrava título, corpo e aula."""
        campos = (dados.get("titulo"), dados.get("corpo"), dados.get("aula_id"))
        return textos.salvar(dados["id"], *campos) if dados.get("id") else textos.criar(*campos)

    @_seguro
    def salvar_audio_texto(self, texto_id, ajustes=None):
        """O texto como está guardado num .mp3 em Músicas › Echo (ou .wav, se o MP3 não sair), com a
        voz, a velocidade, o tom e o volume escolhidos na tela agora ({voz, taxa, tom, volume})."""
        return audio.salvar_texto(textos.obter(texto_id), ajustes if isinstance(ajustes, dict) else None)

    @_seguro
    def apagar_texto(self, texto_id):
        textos.apagar(texto_id)
        return {"ok": True}

    @_seguro
    def remover_favorito(self, id_):
        favoritos.remover(id_)
        return {"ok": True}
