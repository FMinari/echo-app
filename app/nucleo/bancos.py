"""Onde ficam os dois bancos e como abri-los.

- corpus.db: frases das obras. Só leitura; é trocado inteiro quando entra obra nova.
  Procurado em $FRASES_CORPUS, depois em app/corpus.db, depois na pasta acima de app/; sem nenhum,
  o acervo.db (acervo público, ver publico/ACERVO.md) da pasta acima de app/. Com um próprio e o acervo,
  o interruptor "Acervo livre" da busca decide se os dois vão juntos (combinado.db, na pasta de dados).
- dados.db: o que é da pessoa (estruturas, favoritos, falsos positivos, grupos de obras). Fica na pasta de dados
  do usuário para sobreviver a atualizações: %APPDATA%\\FrasesSeries no Windows,
  ~/.local/share/frases-series no Linux. $FRASES_DADOS troca o caminho.
"""
import gzip
import json
import os
import shutil
import sqlite3
import sys
import threading
from contextlib import contextmanager
from datetime import date
from pathlib import Path

APP = Path(__file__).resolve().parent.parent


def caminho_corpus():
    """O banco que a busca usa. Com um corpus.db próprio (com frases) e o acervo público ao mesmo tempo,
    o interruptor "Acervo livre" da busca escolhe: ligado, os dois juntos (combinado.db na pasta de
    dados); desligado, só o próprio. Com um só, é ele."""
    if os.environ.get("FRASES_CORPUS"):
        caminho = Path(os.environ["FRASES_CORPUS"])
        if not caminho.exists():
            raise FileNotFoundError(f"corpus.db não encontrado em {caminho}")
        return caminho
    proprio, acervo = _proprio(), _acervo()
    if proprio and acervo and not _tem_frases(proprio):
        proprio = None  # banco próprio vazio: fica o acervo
    if proprio and acervo and acervo_ligado():
        return _combinado(proprio, acervo)
    if proprio or acervo:
        return proprio or acervo
    raise FileNotFoundError("corpus.db não encontrado (coloque-o na pasta do app)")


def _proprio():
    return next((c for c in (APP / "corpus.db", APP.parent / "corpus.db") if c.exists()), None)


def _acervo():
    """acervo.db: o acervo público (domínio público), para quem clonou o código. O repositório traz ele
    compactado (acervo.db.gz): na primeira vez, descompacta."""
    acervo = APP.parent / "acervo.db"
    compactado = APP.parent / "acervo.db.gz"
    if not acervo.exists() and compactado.exists():
        with _trava:
            if not acervo.exists():
                parcial = compactado.with_name("acervo.db.parcial")
                with gzip.open(compactado) as origem, open(parcial, "wb") as destino:
                    shutil.copyfileobj(origem, destino)
                parcial.replace(acervo)
    return acervo if acervo.exists() else None


_trava = threading.Lock()
_cache = {}  # (o que, arquivo, mtime, tamanho...) -> resposta; o arquivo mudou = chave nova
_ligado = None  # o interruptor "Acervo livre" (acervo.json na pasta de dados), lido uma vez


def _marca(caminho):
    s = caminho.stat()
    return (str(caminho), s.st_mtime_ns, s.st_size)


def _tem_frases(caminho):
    chave = ("frases", *_marca(caminho))
    if chave not in _cache:
        con = sqlite3.connect(so_leitura(caminho), uri=True)
        try:
            _cache[chave] = con.execute("SELECT 1 FROM frases LIMIT 1").fetchone() is not None
        except sqlite3.Error:
            _cache[chave] = False
        finally:
            con.close()
    return _cache[chave]


def acervo_ligado():
    global _ligado
    if _ligado is None:
        try:
            _ligado = json.loads((caminho_dados().parent / "acervo.json").read_text(encoding="utf-8"))["ligado"] is not False
        except (OSError, ValueError, KeyError, TypeError):
            _ligado = True  # começa ligado
    return _ligado


def estado_acervo():
    """Para o interruptor da busca: ele só aparece com os dois bancos e o próprio com frases."""
    proprio, acervo = (None, None) if os.environ.get("FRASES_CORPUS") else (_proprio(), _acervo())
    return {"disponivel": bool(proprio and acervo and _tem_frases(proprio)), "ligado": acervo_ligado()}


def ligar_acervo(ligado):
    """Guarda a escolha (vale nas próximas aberturas) e já prepara o banco que a busca vai usar."""
    global _ligado
    arquivo = caminho_dados().parent / "acervo.json"
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps({"ligado": bool(ligado)}), encoding="utf-8")
    _ligado = bool(ligado)
    caminho_corpus()  # junta os dois aqui, com a tela esperando, e não na primeira busca
    return estado_acervo()


def _versao(caminho):
    con = sqlite3.connect(so_leitura(caminho), uri=True)
    try:
        r = con.execute("SELECT valor FROM meta WHERE chave = 'versao'").fetchone()
        return r[0] if r else "sem-versao"
    except sqlite3.Error:
        return None
    finally:
        con.close()


def _combinado(proprio, acervo):
    chave = ("combinado", *_marca(proprio), *_marca(acervo))
    if chave not in _cache:
        with _trava:
            if chave not in _cache:
                destino = caminho_dados().parent / "combinado.db"
                versao = f"{_versao(proprio)}+{_versao(acervo)}"
                if not (destino.exists() and _versao(destino) == versao):
                    juntar(proprio, acervo, destino, versao)
                _cache[chave] = destino
    return _cache[chave]


def juntar(proprio, acervo, destino, versao):
    """Cópia do próprio + o acervo com os ids deslocados. Os ids do próprio não mudam: as frases guardadas,
    os falsos positivos e o cache continuam valendo. Monta num .parcial e só troca no fim."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(destino.name + ".parcial")
    shutil.copyfile(proprio, parcial)
    con = sqlite3.connect(parcial.resolve().as_uri(), uri=True)
    try:
        con.execute("PRAGMA ignore_check_constraints = ON")  # corpus de antes dos tipos livro, peça...
        con.execute("ATTACH DATABASE ? AS b", (so_leitura(acervo),))
        o, e, li, f = (con.execute(f"SELECT coalesce(max(id), 0) FROM main.{t}").fetchone()[0]
                       for t in ("obras", "episodios", "linhas", "frases"))
        con.execute(f"""INSERT INTO obras (id, nome, tipo, ano, pasta)
                        SELECT id + {o}, nome, tipo, ano, pasta FROM b.obras""")
        con.execute(f"""INSERT INTO episodios (id, obra_id, temporada, episodio, episodio_fim, titulo, arquivo,
                                               duracao_min, palavras)
                        SELECT id + {e}, obra_id + {o}, temporada, episodio, episodio_fim, titulo, arquivo,
                               duracao_min, palavras FROM b.episodios""")
        con.execute(f"""INSERT INTO linhas (id, episodio_id, n, tipo, falante, texto, cena, segundo)
                        SELECT id + {li}, episodio_id + {e}, n, tipo, falante, texto, cena, segundo FROM b.linhas""")
        con.execute(f"""INSERT INTO frases (id, linha_id, texto, tagged, offsets)
                        SELECT id + {f}, linha_id + {li}, texto, tagged, offsets FROM b.frases""")
        tabelas = lambda banco: {r[0] for r in con.execute(f"SELECT name FROM {banco}.sqlite_master WHERE type = 'table'")}  # noqa: E731
        nos_dois = tabelas("main") & tabelas("b")
        if "grupos" in tabelas("b"):
            con.execute("CREATE TABLE IF NOT EXISTS grupos (nome TEXT, ordem INTEGER, obra_id INTEGER REFERENCES obras)")
            ordem = con.execute("SELECT coalesce(max(ordem), -1) + 1 FROM main.grupos").fetchone()[0]
            con.execute(f"INSERT INTO grupos (nome, ordem, obra_id) SELECT nome, ordem + {ordem}, obra_id + {o} FROM b.grupos")
        if {"fabrica_regras", "fabrica_ocorrencias"} <= nos_dois:
            # cache de fábrica só das regras que os dois têm: com só um, a regra acharia só metade
            con.execute("DELETE FROM fabrica_ocorrencias WHERE regra NOT IN (SELECT regra FROM b.fabrica_regras)")
            con.execute("DELETE FROM fabrica_regras WHERE regra NOT IN (SELECT regra FROM b.fabrica_regras)")
            con.execute(f"""INSERT INTO fabrica_ocorrencias (regra, frase_id, obra_id, temporada, falante, palavras, destaques)
                            SELECT regra, frase_id + {f}, obra_id + {o}, temporada, falante, palavras, destaques
                            FROM b.fabrica_ocorrencias WHERE regra IN (SELECT regra FROM main.fabrica_regras)""")
            con.execute("""UPDATE fabrica_regras SET total = total + coalesce(
                               (SELECT r.total FROM b.fabrica_regras r WHERE r.regra = fabrica_regras.regra), 0)""")
        else:
            con.execute("DROP TABLE IF EXISTS fabrica_ocorrencias")
            con.execute("DROP TABLE IF EXISTS fabrica_regras")
        con.execute("INSERT OR REPLACE INTO meta (chave, valor) VALUES ('versao', ?)", (versao,))
        con.commit()
    finally:
        con.close()
    parcial.replace(destino)


def caminho_dados():
    if os.environ.get("FRASES_DADOS"):
        return Path(os.environ["FRASES_DADOS"])
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home())) / "FrasesSeries"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "frases-series"
    return base / "dados.db"


def so_leitura(caminho):
    """URI do SQLite para abrir só para ler. O caminho vai escapado: uma pasta "Turma #2" cortaria o
    caminho no # (e %xx viraria outro caractere)."""
    return Path(caminho).resolve().as_uri() + "?mode=ro"


def _abrir_corpus():
    """Só leitura; com o índice das frases (indice.py) anexado como `ix` quando ele já está montado."""
    from . import indice  # indice usa bancos
    con = sqlite3.connect(so_leitura(caminho_corpus()), uri=True)
    con.row_factory = sqlite3.Row
    try:
        indice.anexar(con)
    except (sqlite3.Error, OSError):  # sem índice a busca só fica mais lenta
        from .registro import log
        log.exception("anexar o índice")
    return con


SCHEMA_DADOS = """
CREATE TABLE IF NOT EXISTS estruturas (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE COLLATE NOCASE,
    categoria TEXT, nivel TEXT, explicacao TEXT, formula TEXT,
    padrao TEXT, texto TEXT, excluir TEXT,
    exemplos TEXT NOT NULL DEFAULT '[]',      -- lista JSON de frases-modelo
    pegadinhas TEXT,
    blocos TEXT,                               -- regra montada com peças (JSON, ver blocos.py)
    origem TEXT NOT NULL DEFAULT 'usuario',    -- semente | semente_editada | usuario | busca | claude
    criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    CHECK (padrao IS NOT NULL OR texto IS NOT NULL)
);
-- frases são identificadas por (arquivo do episódio, texto), porque os ids do corpus mudam a cada reindexação
CREATE TABLE IF NOT EXISTS falsos_positivos (
    estrutura_id INTEGER NOT NULL REFERENCES estruturas ON DELETE CASCADE,
    arquivo TEXT NOT NULL, frase TEXT NOT NULL,
    criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    PRIMARY KEY (estrutura_id, arquivo, frase)
);
-- cache de buscas por estrutura: quais obras já foram varridas, com qual regra e qual corpus
CREATE TABLE IF NOT EXISTS varreduras (
    estrutura_id INTEGER NOT NULL REFERENCES estruturas ON DELETE CASCADE,
    obra_id INTEGER NOT NULL,
    regra TEXT NOT NULL,       -- hash de padrao/texto/excluir no momento da varredura
    corpus TEXT NOT NULL,      -- versão do corpus.db (tabela meta)
    total INTEGER NOT NULL,
    feita_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    PRIMARY KEY (estrutura_id, obra_id)
);
-- os achados de cada varredura; frase_id só vale para a versão de corpus da varredura
CREATE TABLE IF NOT EXISTS ocorrencias (
    estrutura_id INTEGER NOT NULL REFERENCES estruturas ON DELETE CASCADE,
    frase_id INTEGER NOT NULL,
    obra_id INTEGER NOT NULL, temporada INTEGER, falante TEXT, palavras INTEGER NOT NULL,
    destaques TEXT NOT NULL,
    PRIMARY KEY (estrutura_id, frase_id)
);
CREATE INDEX IF NOT EXISTS ocorrencias_obra ON ocorrencias(estrutura_id, obra_id);
-- aulas da cliente: as frases guardadas (favoritos) ficam numa aula ou em "Sem aula" (aula_id vazio)
CREATE TABLE IF NOT EXISTS aulas (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE COLLATE NOCASE,
    criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS favoritos (
    id INTEGER PRIMARY KEY,
    estrutura TEXT,
    obra TEXT, temporada INTEGER, episodio INTEGER, episodio_fim INTEGER, titulo TEXT,
    segundo REAL, falante TEXT, frase TEXT NOT NULL,
    destaques TEXT NOT NULL DEFAULT '[]',     -- [[inicio, fim], ...] em caracteres da frase
    cena TEXT, antes TEXT NOT NULL DEFAULT '[]', depois TEXT NOT NULL DEFAULT '[]',
    arquivo TEXT, nota TEXT,
    aula_id INTEGER REFERENCES aulas ON DELETE SET NULL,
    criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (arquivo, frase)
);
-- textos escritos pela cliente (para ler em voz alta e salvar o áudio), numa aula ou em "Sem aula"
CREATE TABLE IF NOT EXISTS textos (
    id INTEGER PRIMARY KEY,
    titulo TEXT NOT NULL,
    corpo TEXT NOT NULL DEFAULT '',
    aula_id INTEGER REFERENCES aulas ON DELETE SET NULL,
    criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
-- estruturas de fábrica que já passaram por este banco: se a cliente apagar uma, ela não volta
CREATE TABLE IF NOT EXISTS sementes_aplicadas (
    nome TEXT PRIMARY KEY COLLATE NOCASE,
    em TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
-- grupos de obras montados pela cliente; a obra vai pela pasta, que não muda entre versões do corpus
CREATE TABLE IF NOT EXISTS meus_grupos (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE COLLATE NOCASE,
    criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS meus_grupos_obras (
    grupo_id INTEGER NOT NULL REFERENCES meus_grupos ON DELETE CASCADE,
    pasta TEXT NOT NULL,
    PRIMARY KEY (grupo_id, pasta)
);
"""


def _m1_pecas(con):
    if "blocos" not in _colunas(con, "estruturas"):
        con.execute("ALTER TABLE estruturas ADD COLUMN blocos TEXT")


def _m2_aulas(con):
    con.execute("""CREATE TABLE IF NOT EXISTS aulas (
        id INTEGER PRIMARY KEY, nome TEXT NOT NULL UNIQUE COLLATE NOCASE,
        criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')))""")
    if "aula_id" not in _colunas(con, "favoritos"):
        con.execute("ALTER TABLE favoritos ADD COLUMN aula_id INTEGER REFERENCES aulas ON DELETE SET NULL")


def _m3_textos(con):
    con.execute("""CREATE TABLE IF NOT EXISTS textos (
        id INTEGER PRIMARY KEY, titulo TEXT NOT NULL, corpo TEXT NOT NULL DEFAULT '',
        aula_id INTEGER REFERENCES aulas ON DELETE SET NULL,
        criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        atualizado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')))""")


# Migrações do dados.db, em ordem: (número, o que faz, função). O número da última aplicada fica no
# PRAGMA user_version do banco, e ao abrir só rodam as que faltam, numa transação. Antes, o app copia o
# banco para <pasta de dados>/backups/migracao-v<N>-<data>.db (fora da limpeza dos backups diários).
# Nunca mude uma que já saiu numa versão: acrescente outra no fim. Cada uma também precisa funcionar num
# banco novo (o SCHEMA_DADOS já cria tudo no formato atual) e num de antes da numeração (1.3 ou anterior,
# user_version 0), por isso conferem antes de mexer.
MIGRACOES = [
    (1, "regra montada com peças (estruturas.blocos, 1.1)", _m1_pecas),
    (2, "aulas (tabela aulas e favoritos.aula_id, 1.4)", _m2_aulas),
    (3, "textos da cliente, com o áudio da leitura (tabela textos, 1.5)", _m3_textos),
]
VERSAO_DADOS = MIGRACOES[-1][0]
_prontos = set()  # bancos já conferidos neste processo: o esquema e as migrações rodam uma vez só


def _colunas(con, tabela):
    return {r[1] for r in con.execute(f"PRAGMA table_info({tabela})")}


def _copia_boa(arquivo):
    """A cópia abre, passa no quick_check e tem as tabelas dela (uma cópia que parou no meio não conta)."""
    try:
        con = sqlite3.connect(so_leitura(arquivo), uri=True)
        try:
            return (con.execute("PRAGMA quick_check").fetchone()[0] == "ok"
                    and con.execute("SELECT count(*) FROM sqlite_master WHERE name = 'favoritos'").fetchone()[0])
        finally:
            con.close()
    except sqlite3.DatabaseError:
        return False


def _copia_antes_de_migrar(caminho, versao):
    """Cópia do banco como estava, antes de qualquer migração (API de backup do SQLite). Vai para um
    .tmp e só ganha o nome final depois de conferida."""
    pasta = caminho.parent / "backups"
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"migracao-v{versao}-{date.today():%Y-%m-%d}.db"
    if destino.exists() and _copia_boa(destino):
        return destino
    temporario = destino.with_suffix(".tmp")
    temporario.unlink(missing_ok=True)
    origem = sqlite3.connect(caminho, timeout=30)
    try:
        copia = sqlite3.connect(temporario)
        try:
            origem.backup(copia)
        finally:
            copia.close()
    finally:
        origem.close()
    if not _copia_boa(temporario):
        temporario.unlink(missing_ok=True)
        raise sqlite3.DatabaseError("a cópia de antes de mudar os dados não ficou boa: nada foi mudado")
    temporario.replace(destino)
    return destino


def preparar_dados(caminho=None):
    """Cria as tabelas que faltam e aplica as migrações pendentes (com cópia antes, se o banco já
    tinha dados). Devolve as migrações aplicadas: [(número, descrição)]."""
    caminho = Path(caminho or caminho_dados())
    caminho.parent.mkdir(parents=True, exist_ok=True)
    existia = caminho.exists() and caminho.stat().st_size > 0
    con = sqlite3.connect(caminho, timeout=30)
    try:
        versao = con.execute("PRAGMA user_version").fetchone()[0]
        pendentes = [m for m in MIGRACOES if m[0] > versao]
        if not pendentes:
            con.executescript(SCHEMA_DADOS)  # versão atual: só garante as tabelas (rápido, nada muda)
            return []
        if existia and con.execute("SELECT count(*) FROM sqlite_master").fetchone()[0]:
            con.close()
            _copia_antes_de_migrar(caminho, pendentes[-1][0])
            con = sqlite3.connect(caminho, timeout=30)
        con.executescript(SCHEMA_DADOS)
        con.isolation_level = None
        con.execute("BEGIN IMMEDIATE")  # duas aberturas ao mesmo tempo: uma espera a outra
        try:
            versao = con.execute("PRAGMA user_version").fetchone()[0]
            feitas = []
            for numero, descricao, migrar in MIGRACOES:
                if numero > versao:
                    migrar(con)
                    feitas.append((numero, descricao))
            con.execute(f"PRAGMA user_version = {MIGRACOES[-1][0]}")
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
        if feitas:
            from .registro import log
            log.info("dados.db migrado para a versão %s: %s", MIGRACOES[-1][0], feitas)
        return feitas
    finally:
        con.close()


def _abrir_dados():
    caminho = caminho_dados()
    if str(caminho) not in _prontos:
        preparar_dados(caminho)
        _prontos.add(str(caminho))
    con = sqlite3.connect(caminho, timeout=30)  # a janela aquece o cache numa thread à parte
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode = WAL")  # janela e Claude escrevem ao mesmo tempo sem se travar
    con.execute("PRAGMA foreign_keys = ON")
    return con


@contextmanager
def _sessao(abrir):
    con = abrir()
    try:
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()


def fazer_backup(manter=7):
    """Uma cópia do dados.db por dia em <pasta de dados>/backups/, guardando as `manter` mais novas.

    Usa a API de backup do SQLite (segura com o banco aberto) e só copia se o `quick_check` passar,
    para um banco estragado não empurrar as cópias boas para fora. Devolve o caminho da cópia nova,
    ou None se a de hoje já existia. Para restaurar: feche o app e o Claude e copie o arquivo por
    cima do dados.db (apagando dados.db-wal e dados.db-shm)."""
    origem = caminho_dados()
    if not origem.exists():
        return None
    pasta = origem.parent / "backups"
    pasta.mkdir(exist_ok=True)
    destino = pasta / f"dados-{date.today():%Y-%m-%d}.db"
    if destino.exists():
        return None
    con = _abrir_dados()
    try:
        estado = con.execute("PRAGMA quick_check").fetchone()[0]
        if estado != "ok":
            raise sqlite3.DatabaseError(f"dados.db com problema ({estado}); backup de hoje não feito")
        temporario = destino.with_suffix(".tmp")
        try:
            copia = sqlite3.connect(temporario)
            try:
                con.backup(copia)
            finally:
                copia.close()
            temporario.replace(destino)
        except BaseException:
            temporario.unlink(missing_ok=True)  # com o disco cheio, não deixa um .tmp por dia
            raise
    finally:
        con.close()
    for velho in sorted(pasta.glob("dados-*.tmp")):  # de algum dia em que o app caiu no meio
        velho.unlink(missing_ok=True)
    for velho in sorted(pasta.glob("dados-*.db"))[:-manter]:
        velho.unlink()
    return destino


def corpus():
    """`with bancos.corpus() as con:` — conexão só leitura, fechada na saída."""
    return _sessao(_abrir_corpus)


def dados():
    """`with bancos.dados() as con:` — commit (ou rollback) e fecha na saída."""
    return _sessao(_abrir_dados)
