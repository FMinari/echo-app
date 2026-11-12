"""Versões publicadas no GitHub (repositório privado do dev), só com a biblioteca padrão.

`app/github.json` = {"repo": "dono/nome", "token": "..."} vem dentro do pacote (empacotar.py copia de
~/.config/echo/github.json; o token é fine-grained, só leitura, só desse repositório). Sem ele,
ou sem internet, tudo aqui devolve vazio e o app segue com Downloads / .sitcomatica.

Cada release (ferramentas/publicar.py) tem a tag `v<versão>`, o asset "… - atualização.sitcomatica"
(só o app), às vezes "… - completo.zip" (app + banco) e, nas notas, os metadados num comentário:
<!-- sitcomatica {"numero": "1.2", "banco": "2026-10-07 09:30:00"} -->
"""
import http.client
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from . import atualizacao, sobre
from .registro import log

APP = Path(__file__).resolve().parent.parent
API = os.environ.get("FRASES_GITHUB_API") or "https://api.github.com"  # a variável é para testes
METADADOS = re.compile(r"<!--\s*sitcomatica\s+(\{.*?\})\s*-->", re.S)

# o que aconteceu na última consulta: "sem_token", "ok", "offline", "token_expirado" ou "erro";
# com "ok", `expira_em` traz a validade do token que o GitHub informa
estado = {"situacao": None, "expira_em": None}


def config():
    try:
        c = json.loads((APP / "github.json").read_text(encoding="utf-8"))
        return c if c.get("repo") and c.get("token") else None
    except (OSError, ValueError):
        return None


def _pedido(url, cfg, aceita="application/vnd.github+json"):
    return urllib.request.Request(url, headers={
        "Authorization": f"Bearer {cfg['token']}", "Accept": aceita,
        "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "Sitcomatica"})


def releases(timeout=8):
    """Releases publicadas, da mais nova para a mais velha: [{numero, banco, notas, data, app, completo}]
    (app/completo = {nome, tamanho, url} do asset, ou None). [] sem token, sem internet ou com erro."""
    cfg = config()
    if not cfg:
        estado.update(situacao="sem_token", expira_em=None)
        return []
    try:
        with urllib.request.urlopen(_pedido(f"{API}/repos/{cfg['repo']}/releases?per_page=50", cfg),
                                    timeout=timeout) as r:
            dados = json.load(r)
            estado.update(situacao="ok", expira_em=r.headers.get("github-authentication-token-expiration"))
    except urllib.error.HTTPError as e:
        # 401: token vencido ou revogado (o GitHub não diferencia); 404: sem acesso ao repositório
        expirado = e.code in (401, 404)
        estado.update(situacao="token_expirado" if expirado else "erro", expira_em=None)
        log.warning("GitHub recusou a consulta (%s): %s", e.code, "token expirado?" if expirado else e.reason)
        return []
    except (urllib.error.URLError, OSError, ValueError) as e:
        estado.update(situacao="offline", expira_em=None)
        log.info("GitHub indisponível: %s", e)  # sem internet é normal: não é erro da cliente
        return []
    saida = []
    for rel in dados:
        if rel.get("draft"):
            continue
        meta = {}
        if m := METADADOS.search(rel.get("body") or ""):
            try:
                meta = json.loads(m.group(1))
            except ValueError:
                pass
        numero = meta.get("numero") or (rel.get("tag_name") or "").lstrip("v")
        assets = {"app": None, "completo": None}
        for a in rel.get("assets", []):
            info = {"nome": a["name"], "tamanho": a["size"], "url": a["url"]}
            if a["name"].endswith(atualizacao.EXTENSAO):
                assets["app"] = info
            elif a["name"].endswith(".zip") and "completo" in a["name"]:
                assets["completo"] = info
        if not assets["app"] and not assets["completo"]:
            continue
        notas = METADADOS.sub("", rel.get("body") or "").strip()
        saida.append({"numero": numero, "banco": meta.get("banco"), "notas": notas,
                      "data": (rel.get("published_at") or "")[:10], **assets})
    saida = [r for r in saida if atualizacao.numero_tupla(r["numero"]) >= atualizacao.MINIMA]
    saida.sort(key=lambda r: atualizacao.numero_tupla(r["numero"]), reverse=True)
    return saida


def pacote_para(release, banco_local):
    """Qual asset baixar: o completo só se o banco da release for mais novo que o instalado (são ~120 MB)."""
    if release["completo"] and (release.get("banco") or "") > (banco_local or ""):
        return release["completo"]
    return release["app"] or release["completo"]


def como_pacote(release, banco_local):
    """No formato do aviso de atualização da janela (o mesmo de atualizacao.ler_pacote)."""
    asset = pacote_para(release, banco_local)
    return {"tipo": "app", "origem": "github", "numero": release["numero"], "versao": release["numero"],
            "arquivo": asset["nome"], "asset": asset, "com_banco": asset is release["completo"],
            "novidades": [{"versao": release["numero"], "itens": _itens(release["notas"])}],
            "mais_novo": atualizacao.numero_tupla(release["numero"]) > atualizacao.numero_tupla(sobre.numero())}


def _itens(notas):
    return [l.lstrip("-*• ").strip() for l in notas.splitlines() if l.strip().startswith(("-", "*", "•"))]


def mais_nova(banco_local):
    """A release mais nova acima da versão instalada, já como pacote para o aviso (ou None)."""
    atual = atualizacao.numero_tupla(sobre.numero())
    for r in releases():
        if atualizacao.numero_tupla(r["numero"]) > atual:
            return como_pacote(r, banco_local)
        break  # a lista vem da mais nova; se a primeira não passa, nenhuma passa
    return None


def versoes(banco_local):
    """Para a lista "Versões": as 5 mais novas + a mais nova da linha (major.minor) anterior à instalada."""
    todas = releases()
    escolhidas = todas[:5]
    linha = atualizacao.numero_tupla(sobre.numero())[:2]
    anterior = next((r for r in todas if atualizacao.numero_tupla(r["numero"])[:2] < linha), None)
    if anterior and anterior not in escolhidas:
        escolhidas.append(anterior)
    return [como_pacote(r, banco_local) | {"data": r["data"], "atual": r["numero"] == sobre.numero()}
            for r in escolhidas]


class _SemAuthNoRedirect(urllib.request.HTTPRedirectHandler):
    """O GitHub redireciona o download para o armazenamento dele; o token não pode ir junto."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        novo = super().redirect_request(req, fp, code, msg, headers, newurl)
        if novo is not None:
            novo.remove_header("Authorization")
        return novo


def baixar(asset, destino, progresso=lambda feito, total: None):
    """Baixa o asset para `destino` (Path), chamando progresso(bytes, total). Devolve o caminho."""
    cfg = config()
    if not cfg:
        raise ValueError("Este app não está ligado ao GitHub.")
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(destino.name + ".baixando")
    abridor = urllib.request.build_opener(_SemAuthNoRedirect)
    try:
        with abridor.open(_pedido(asset["url"], cfg, "application/octet-stream"), timeout=30) as r, \
                open(parcial, "wb") as saida:
            total, feito = int(r.headers.get("Content-Length") or asset.get("tamanho") or 0), 0
            while bloco := r.read(256 * 1024):
                saida.write(bloco)
                feito += len(bloco)
                progresso(feito, total)
        if total and feito != total:
            raise http.client.IncompleteRead(b"", total - feito)
    except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
        parcial.unlink(missing_ok=True)
        raise ValueError(f"O download da atualização parou no meio (a internet caiu?). Tente de novo. ({e!r})") from None
    parcial.replace(destino)
    return destino
