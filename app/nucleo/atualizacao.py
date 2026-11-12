"""Atualização do app a partir de um arquivo que o dev manda (vai parar em Downloads).

Pacotes aceitos:
- `.sitcomatica` (o zip do empacotar.py com outra extensão: dois cliques nele abrem o app, ver
  janela/app.py) — é o formato das atualizações da 1.1.1 em diante;
- zip do empacotar.py ("Echo <versão> - completo.zip"; até a 1.4.1, "Sitcomatica …"): uma pasta
  raiz com `app/VERSAO` ("<versão> · data · commit") dentro;
- `corpus.db` sozinho: só as frases.

`aplicar` troca arquivo por arquivo na pasta instalada. O `.venv` e os dados da cliente (`%APPDATA%`) não
estão no pacote, então não são tocados.
"""
import json
import os
import shutil
import sqlite3
import threading
import time
import zipfile
from pathlib import Path

from . import bancos, sobre

EXTENSAO = ".sitcomatica"
# A 1.3 trocou o pywebview e o Python do uv pelo Python embutido e o Edge (F16): versão anterior não abre
# nessa instalação, então não é oferecida nem instalada.
MINIMA = (1, 3)
APP = Path(__file__).resolve().parent.parent
RAIZ = APP.parent  # pasta que a cliente extraiu (Sitcomatica), com instalar.bat e app/
# uma instalação por vez (duas janelas abertas mostram o mesmo aviso e a cliente pode clicar nas duas)
_INSTALANDO = threading.Lock()


def pasta_downloads():
    """$FRASES_DOWNLOADS troca a pasta (testes)."""
    return Path(os.environ.get("FRASES_DOWNLOADS") or Path.home() / "Downloads")


def numero_tupla(numero):
    """'1.10' -> (1, 10), para comparar versões; texto estranho vira (0,)."""
    try:
        return tuple(int(p) for p in str(numero).split("."))
    except ValueError:
        return (0,)


def instalado():
    """Só no app instalado (o zip traz app/VERSAO); no desenvolvimento, atualizar sobrescreveria o repositório."""
    return (APP / "VERSAO").exists()


def _raiz_do_zip(z):
    raizes = {n.split("/", 1)[0] for n in z.namelist() if n.strip("/")}
    if len(raizes) != 1:
        raise ValueError("Esse arquivo não é uma atualização do Echo.")
    raiz = raizes.pop()
    for n in z.namelist():
        partes = Path(n).parts
        if n.startswith(("/", "\\")) or ".." in partes or ":" in n:
            raise ValueError("Esse arquivo de atualização tem caminhos estranhos; não vou usar.")
    if f"{raiz}/app/VERSAO" not in z.namelist():
        raise ValueError("Esse arquivo não é uma atualização do Echo.")
    return raiz


def ler_pacote(caminho):
    """O que tem no arquivo: {tipo: "app"|"banco", arquivo, numero, versao, novidades, com_banco,
    rotulo, gerado_em}. ValueError se não for um pacote do Echo."""
    caminho = Path(caminho)
    if caminho.suffix.lower() in (".zip", EXTENSAO):
        try:
            with zipfile.ZipFile(caminho) as z:
                raiz = _raiz_do_zip(z)
                versao = z.read(f"{raiz}/app/VERSAO").decode("utf-8").strip()
                try:
                    novidades = json.loads(z.read(f"{raiz}/app/novidades.json").decode("utf-8"))
                except (KeyError, ValueError):
                    novidades = []
                com_banco = f"{raiz}/app/corpus.db" in z.namelist()
        except zipfile.BadZipFile:
            raise ValueError("Esse arquivo de atualização está estragado (talvez o download não terminou).") from None
        numero = versao.split("·")[0].strip()
        return {"tipo": "app", "arquivo": str(caminho), "numero": numero, "versao": versao,
                "novidades": [n for n in novidades if numero_tupla(n.get("versao")) > numero_tupla(sobre.numero())],
                "com_banco": com_banco}
    if caminho.suffix.lower() == ".db":
        try:
            with sqlite3.connect(bancos.so_leitura(caminho), uri=True) as con:
                gerado = con.execute("SELECT valor FROM meta WHERE chave = 'gerado_em'").fetchone()[0]
                n = con.execute("SELECT count(*) FROM obras").fetchone()[0]
        except (sqlite3.DatabaseError, TypeError):
            raise ValueError("Esse arquivo não é um banco de frases do Echo.") from None
        data, _, hora = gerado.partition(" ")
        a, m, d = data.split("-")
        return {"tipo": "banco", "arquivo": str(caminho), "gerado_em": gerado,
                "rotulo": f"{d}/{m}/{a} {hora[:5]} · {n} obras"}
    raise ValueError("Escolha o arquivo .sitcomatica (ou .zip, ou corpus.db) que o desenvolvedor mandou.")


def _gerado_em_local():
    try:
        with bancos.corpus() as con:
            return con.execute("SELECT valor FROM meta WHERE chave = 'gerado_em'").fetchone()[0]
    except Exception:  # noqa: BLE001 — sem banco local, qualquer banco serve
        return ""


def conferir_minima(pacote):
    """ValueError se for uma versão do app anterior à MINIMA (ela não abre nesta instalação)."""
    if pacote["tipo"] == "app" and numero_tupla(pacote["numero"]) < MINIMA:
        raise ValueError(f"A versão {pacote['numero']} não funciona mais neste computador. "
                         f"Use a {'.'.join(map(str, MINIMA))} ou mais nova.")
    return pacote


def e_mais_novo(pacote):
    if pacote["tipo"] == "app":
        return numero_tupla(pacote["numero"]) > numero_tupla(sobre.numero())
    return pacote["gerado_em"] > _gerado_em_local()


def procurar(pastas=None):
    """O pacote mais novo que o instalado nas pastas (Downloads, por padrão), ou None. Versão de app
    ganha de banco sozinho; entre iguais, o arquivo mais recente."""
    candidatos = []
    for pasta in pastas or [pasta_downloads()]:
        pasta = Path(pasta)
        if not pasta.is_dir():
            continue
        nomes = (f"*{EXTENSAO}", "Echo*.zip", "Sitcomatica*.zip", "Sitcomática*.zip", "corpus*.db")
        for arq in dict.fromkeys(a for padrao in nomes for a in pasta.glob(padrao)):
            try:
                p = ler_pacote(arq)
            except (ValueError, OSError):
                continue
            if e_mais_novo(p):
                p["modificado"] = arq.stat().st_mtime
                candidatos.append(p)
    if not candidatos:
        return None
    return max(candidatos, key=lambda p: (p["tipo"] == "app", numero_tupla(p.get("numero", "0")),
                                          p.get("gerado_em", ""), p["modificado"]))


def _trocar(origem, destino, tentativas=40):
    """os.replace com novas tentativas: o corpus.db pode estar aberto por um instante (uma busca)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    for i in range(tentativas):
        try:
            os.replace(origem, destino)
            return
        except PermissionError:
            if i == tentativas - 1:
                raise ValueError(f"{destino.name} está em uso por outro programa: reinicie o computador e "
                                 "tente de novo.") from None
            time.sleep(0.5)


def _ordem(arq):
    """VERSAO e novidades.json por último (só dizem "versão nova" se o resto entrou); o corpus.db depois
    de tudo: se ele estiver preso, o app continua inteiro na versão de antes."""
    return (arq.name == "corpus.db", arq.name in ("VERSAO", "novidades.json"), str(arq))


def aplicar(caminho, raiz=None):
    """Instala o pacote na pasta do app. Devolve {tipo, numero} ou {tipo, rotulo} (só o banco). O Python
    embutido (python/) não é tocado nem quando vem no pacote completo: está em uso pelo próprio app, e o
    Windows não deixa trocar. Se um arquivo não puder ser trocado, desfaz o que já foi (nada de app pela
    metade)."""
    if not _INSTALANDO.acquire(blocking=False):
        raise ValueError("Já tem uma atualização sendo instalada. Espere ela terminar.")
    try:
        return _aplicar(caminho, Path(raiz or RAIZ))
    finally:
        _INSTALANDO.release()


def _aplicar(caminho, raiz):
    if raiz == RAIZ and not instalado():
        raise ValueError("A atualização só funciona no app instalado, não no modo de desenvolvimento.")
    pacote = conferir_minima(ler_pacote(caminho))
    if pacote["tipo"] == "banco":
        temporario = raiz / "app" / "corpus.db.novo"
        shutil.copyfile(caminho, temporario)
        _trocar(temporario, raiz / "app" / "corpus.db")
        return {"tipo": "banco", "rotulo": pacote["rotulo"]}

    temporaria = raiz.parent / f".{raiz.name}-atualizando"
    anteriores = raiz.parent / f".{raiz.name}-anterior"  # os arquivos de antes, para desfazer
    for pasta in (temporaria, anteriores):
        shutil.rmtree(pasta, ignore_errors=True)
    trocados = []  # (destino, cópia de antes ou None se o arquivo é novo)
    try:
        try:
            with zipfile.ZipFile(caminho) as z:
                origem = _raiz_do_zip(z)
                z.extractall(temporaria)
        except zipfile.BadZipFile:
            raise ValueError("Esse arquivo de atualização está estragado (talvez o download não terminou).") from None
        base = temporaria / origem
        arquivos = sorted((p for p in base.rglob("*")
                           if p.is_file() and p.relative_to(base).parts[0] != "python"), key=_ordem)
        try:
            for arq in arquivos:
                rel = arq.relative_to(base)
                destino, copia = raiz / rel, None
                if destino.exists():
                    copia = anteriores / rel
                    _trocar(destino, copia)
                trocados.append((destino, copia))
                _trocar(arq, destino)
        except BaseException:
            _desfazer(trocados)
            raise
    finally:
        shutil.rmtree(temporaria, ignore_errors=True)
        shutil.rmtree(anteriores, ignore_errors=True)
    return {"tipo": "app", "numero": pacote["numero"]}


def _desfazer(trocados):
    """Põe de volta os arquivos de antes (e tira os que eram novos), do último para o primeiro."""
    from .registro import log
    log.warning("atualização interrompida: desfazendo %d arquivo(s)", len(trocados))
    for destino, copia in reversed(trocados):
        try:
            if copia is None:
                destino.unlink(missing_ok=True)
            elif copia.exists():
                os.replace(copia, destino)
        except OSError:
            log.exception("não consegui pôr de volta %s", destino)
