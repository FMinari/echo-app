"""Índice das frases, montado pelo próprio app no PC da cliente: `<pasta de dados>/indice-<corpus>-<formato>.db`.

- `palavras` (FTS5 sem conteúdo, detail=none): o lema (`1take`) e a palavra (`2took`) de cada frase, só
  os que são letras e números. Separa na hora as frases que têm as palavras da busca escrita.
- `phrasal`: cada phrasal verb de cada frase (ver phrasal.py), para contar as fichas com um GROUP BY.

É derivado do corpus.db (que é só leitura): fica fora do dados.db e do backup, é montado num arquivo
temporário e só ganha o nome certo quando termina. O nome leva a versão do corpus e do formato, então
corpus novo ou índice de outro formato = arquivo novo; os velhos são apagados quando der. Sem índice
(montando, ou se falhar), a busca continua do jeito antigo.
"""
import os
import re
import sqlite3
import threading
import time

from . import bancos, phrasal
from .registro import log

FORMATO = "1"  # mude quando o conteúdo do índice mudar: ele é refeito
_ALNUM = re.compile(r"^[a-z0-9]+$")
_trava = threading.Lock()
_pronto = {}  # (corpus, mtime do corpus) -> caminho do índice ou None
_quebrados = set()  # índices que não abriram (arquivo estragado): não são usados e são refeitos


def _versao_corpus():
    con = sqlite3.connect(bancos.so_leitura(bancos.caminho_corpus()), uri=True)
    try:
        r = con.execute("SELECT valor FROM meta WHERE chave = 'versao'").fetchone()
        return r[0] if r else "sem-versao"
    finally:
        con.close()


def _arquivo(versao):
    seguro = re.sub(r"[^0-9A-Za-z_.-]", "_", versao)
    return bancos.caminho_dados().parent / f"indice-{seguro}-{FORMATO}.db"


def pronto():
    """Caminho do índice deste corpus, se já está montado; senão None."""
    corpus = bancos.caminho_corpus()
    chave = (str(corpus), corpus.stat().st_mtime)
    if _pronto.get(chave):
        return _pronto[chave]
    arquivo = _arquivo(_versao_corpus())
    if arquivo.exists() and arquivo not in _quebrados and not _abre(arquivo):
        _quebrou(arquivo)
    _pronto[chave] = arquivo if arquivo.exists() and arquivo not in _quebrados else None
    return _pronto[chave]


def _abre(arquivo):
    """O índice abre e é deste formato (uma vez por processo, em pronto())."""
    try:
        con = sqlite3.connect(bancos.so_leitura(arquivo), uri=True)
        try:
            r = con.execute("SELECT valor FROM meta WHERE chave = 'formato'").fetchone()
            con.execute("SELECT rowid FROM palavras WHERE palavras MATCH '\"1be\"' LIMIT 1").fetchall()
            return bool(r) and r[0] == FORMATO
        finally:
            con.close()
    except sqlite3.DatabaseError:
        return False


def _quebrou(arquivo):
    """Índice estragado (o PC desligou logo depois de montar): não é usado e é montado de novo."""
    log.warning("o índice %s não abre: montando de novo", arquivo.name)
    _quebrados.add(arquivo)
    _pronto.clear()
    threading.Thread(target=_remontar, name="indice", daemon=True).start()


def termo(prefixo, palavra):
    """Termo do FTS ("1take") ou None se a palavra não entra no índice (n't, 's…)."""
    return f'"{prefixo}{palavra}"' if _ALNUM.match(palavra) else None


def _linhas_do_indice(corpus):
    for fid, texto, tagged in corpus.execute("SELECT id, texto, tagged FROM frases"):
        termos = set()
        for token in tagged.split():
            partes = token.rsplit("/", 2)
            if len(partes) != 3:
                continue
            if _ALNUM.match(partes[1]):
                termos.add("1" + partes[1])
            if _ALNUM.match(partes[0]):
                termos.add("2" + partes[0])
        achados = {(lema, tag, combo) for lema, tag, combos in phrasal.achar(tagged) for combo in combos}
        yield fid, " ".join(termos), len(texto.split()), achados


def construir():
    """Monta o índice do corpus atual (se ainda não existe). Devolve o caminho."""
    with _trava:
        versao = _versao_corpus()
        destino = _arquivo(versao)
        if destino.exists() and destino not in _quebrados:
            return destino
        inicio = time.time()
        temporario = destino.with_name(destino.name + ".montando")
        temporario.unlink(missing_ok=True)
        destino.parent.mkdir(parents=True, exist_ok=True)
        corpus = sqlite3.connect(bancos.so_leitura(bancos.caminho_corpus()), uri=True)
        con = sqlite3.connect(temporario)
        try:
            con.executescript("""
                PRAGMA journal_mode = OFF; PRAGMA synchronous = OFF;
                CREATE VIRTUAL TABLE palavras USING fts5(t, content='', detail=none, columnsize=0,
                                                         tokenize='unicode61 remove_diacritics 0');
                CREATE TABLE phrasal (frase_id INTEGER NOT NULL, lema TEXT NOT NULL, tag TEXT NOT NULL,
                                      combo TEXT NOT NULL, palavras INTEGER NOT NULL);
                CREATE TABLE meta (chave TEXT PRIMARY KEY, valor TEXT);
            """)
            lote_p, lote_f = [], []
            for fid, termos, palavras, achados in _linhas_do_indice(corpus):
                lote_p.append((fid, termos))
                lote_f += [(fid, lema, tag, combo, palavras) for lema, tag, combo in achados]
                if len(lote_p) >= 20000:
                    con.executemany("INSERT INTO palavras(rowid, t) VALUES (?, ?)", lote_p)
                    con.executemany("INSERT INTO phrasal VALUES (?, ?, ?, ?, ?)", lote_f)
                    lote_p, lote_f = [], []
            con.executemany("INSERT INTO palavras(rowid, t) VALUES (?, ?)", lote_p)
            con.executemany("INSERT INTO phrasal VALUES (?, ?, ?, ?, ?)", lote_f)
            con.executescript("""
                CREATE INDEX phrasal_lema ON phrasal(lema, combo);
                INSERT INTO palavras(palavras) VALUES ('optimize');
            """)
            con.executemany("INSERT INTO meta VALUES (?, ?)", [("corpus", versao), ("formato", FORMATO)])
            con.commit()
        finally:
            con.close()
            corpus.close()
        with open(temporario, "rb+") as f:  # montado sem diário: no disco antes de ganhar o nome certo
            os.fsync(f.fileno())
        destino.unlink(missing_ok=True)  # um quebrado de antes
        os.replace(temporario, destino)
        _quebrados.discard(destino)
        _pronto.clear()
        log.info("índice montado em %.0f s: %s", time.time() - inicio, destino.name)
        _apagar_velhos(destino)
        return destino


def _apagar_velhos(atual):
    for velho in atual.parent.glob("indice-*.db*"):
        if velho != atual:
            try:
                velho.unlink()
            except OSError:  # aberto por uma busca agora: fica para a próxima vez
                pass


def anexar(con):
    """ATTACH do índice como `ix` numa conexão do corpus (se pronto). Devolve se anexou. Índice que não
    abre (estragado: o PC desligou logo depois de montar) deixa de ser usado e é montado de novo."""
    caminho = pronto()
    if not caminho:
        return False
    try:
        con.execute("ATTACH DATABASE ? AS ix", (bancos.so_leitura(caminho),))
        con.execute("SELECT valor FROM ix.meta WHERE chave = 'formato'").fetchone()
    except sqlite3.DatabaseError:
        try:
            con.execute("DETACH DATABASE ix")
        except sqlite3.DatabaseError:
            pass
        _quebrou(caminho)
        return False
    return True


def _remontar():
    try:
        construir()
    except Exception:  # noqa: BLE001 — sem índice a busca só fica mais lenta
        log.exception("montar o índice das frases de novo")
