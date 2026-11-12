"""Estado do app para a aba Sobre: versão do app, versão do banco, onde ficam os dados e novidades."""
import json
from pathlib import Path

from . import bancos, busca, dicionario

APP = Path(__file__).resolve().parent.parent
NOVIDADES = APP / "novidades.json"


def novidades():
    """Patch notes, da versão mais nova para a mais velha."""
    try:
        return json.loads(NOVIDADES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def numero():
    """Número da versão do app: o da entrada mais nova de novidades.json."""
    lista = novidades()
    return lista[0]["versao"] if lista else "?"


def data():
    """Data da versão instalada (a da entrada mais nova de novidades.json), "2026-10-30"; None sem novidades."""
    lista = novidades()
    return lista[0].get("data") if lista else None


def versao_app():
    """No zip que vai pra cliente, o empacotar.py grava app/VERSAO ("1.0 · data · commit"); aqui no
    desenvolvimento ele não existe."""
    try:
        return (APP / "VERSAO").read_text(encoding="utf-8").strip()
    except OSError:
        return f"{numero()} · dev"


def _banco():
    with bancos.corpus() as con:
        tipos = dict(con.execute("SELECT tipo, count(*) FROM obras GROUP BY tipo").fetchall())
        musicas = con.execute("SELECT count(*) FROM episodios e JOIN obras o ON o.id = e.obra_id"
                              " WHERE o.tipo = 'musica'").fetchone()[0]
        frases = con.execute("SELECT count(*) FROM frases").fetchone()[0]
    return {"rotulo": busca.rotulo_corpus(), "series": tipos.get("serie", 0), "filmes": tipos.get("filme", 0),
            "musicas": musicas, "frases": frases, "tipos": tipos}


def _ultimo_backup():
    copias = sorted((bancos.caminho_dados().parent / "backups").glob("dados-*.db"))
    return copias[-1].stem.removeprefix("dados-") if copias else None


def contato():
    """app/contato.json, sem os campos vazios."""
    try:
        dados = json.loads((APP / "contato.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in dados.items() if v and not k.startswith("_")}


def estado():
    return {
        "contato": contato(),
        "app": {"numero": numero(), "versao": versao_app()},
        "banco": _banco(),
        "dados": str(bancos.caminho_dados().parent),
        "ultimo_backup": _ultimo_backup(),
        "novidades": novidades(),
        "dicionario": dicionario.FONTE,
    }
