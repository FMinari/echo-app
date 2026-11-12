"""Baixa a letra de uma música do LRCLIB (lrclib.net: grátis, aberto, sem chave) para transcripts/.

Uso: python3 -I ferramentas/baixar_letra.py "Taylor Swift" "Love Story" [--album Fearless] [--id 8202]

Grava `transcripts/<artista>/<Música>.txt` no formato LRC, com o tempo de cada verso:
    [ti:Love Story]
    [ar:Taylor Swift]
    [al:Fearless]
    [length:03:55]
    [00:12.34] We were both young when I first saw you
e cria a entrada do artista no obras.json (tipo "musica") se ainda não houver. Sem letra com tempo, usa a
letra simples (aí o tempo do verso é estimado pelas palavras, como nas séries). Depois: reindexar.
"""
import argparse
import json
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TRANSCRIPTS = RAIZ / "transcripts"
OBRAS = Path(__file__).resolve().parent / "obras.json"
API = "https://lrclib.net/api"
AGENTE = "echo-indexador/1.0 (uso pessoal, github.com/FMinari/echo)"


def pegar(caminho, **params):
    url = f"{API}/{caminho}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": AGENTE}), timeout=30) as r:
        return json.load(r)


def pasta_do_artista(nome):
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")


def nome_de_arquivo(titulo):
    return re.sub(r'[<>:"/\\|?*]', "", titulo).strip() + ".txt"


def achar(artista, musica, album=None, id_=None):
    if id_:
        return pegar(f"get/{id_}")
    if album:
        try:
            return pegar("get", artist_name=artista, track_name=musica, album_name=album)
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
    achados = [x for x in pegar("search", artist_name=artista, track_name=musica) if not x.get("instrumental")]
    if not achados:
        sys.exit(f"o LRCLIB não tem {artista} - {musica}")
    # a com tempo primeiro; entre elas, a que aparece mais vezes com a mesma duração (a versão de estúdio)
    duracoes = [round(x["duration"] or 0) for x in achados]
    return max(achados, key=lambda x: (bool(x.get("syncedLyrics")), duracoes.count(round(x["duration"] or 0))))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("artista")
    ap.add_argument("musica")
    ap.add_argument("--album", help="nome do álbum, para pegar a versão certa")
    ap.add_argument("--id", type=int, help="id do LRCLIB (vence artista, música e álbum)")
    a = ap.parse_args()

    x = achar(a.artista, a.musica, a.album, a.id)
    letra = x.get("syncedLyrics") or x.get("plainLyrics")
    if not letra:
        sys.exit(f"o LRCLIB tem {x['artistName']} - {x['trackName']} sem letra")
    duracao = int(round(x.get("duration") or 0))
    cabecalho = [f"[ti:{x['trackName']}]", f"[ar:{a.artista}]", f"[al:{x.get('albumName') or ''}]",
                 f"[length:{duracao // 60:02d}:{duracao % 60:02d}]", f"[lrclib:{x['id']}]"]

    pasta = pasta_do_artista(a.artista)
    destino = TRANSCRIPTS / pasta / nome_de_arquivo(x["trackName"])
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(cabecalho + letra.strip().splitlines()) + "\n", encoding="utf-8")
    print(f"{destino.relative_to(RAIZ)}: {x['artistName']} - {x['trackName']} ({x.get('albumName')}, "
          f"{'com' if x.get('syncedLyrics') else 'SEM'} tempo por verso)")

    obras = json.loads(OBRAS.read_text(encoding="utf-8"))
    if pasta not in obras:
        obras[pasta] = {"nome": a.artista, "tipo": "musica"}
        OBRAS.write_text(json.dumps(obras, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"obras.json: {pasta} entrou como música")


if __name__ == "__main__":
    main()
