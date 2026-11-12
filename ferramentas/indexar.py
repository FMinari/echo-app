"""Gera corpus.db a partir de transcripts/.

Uso: .venv/bin/python ferramentas/indexar.py
     .venv/bin/python ferramentas/indexar.py --so-grupos [banco.db]   (só regrava os grupos)

Cada fala vira uma ou mais frases etiquetadas pelo spaCy. O campo `tagged`
guarda cada token como `palavra/lema/TAG` separados por espaço, que é onde o
buscar.py roda os padrões gramaticais.
"""
import json
import re
import sqlite3
import sys
import uuid
from pathlib import Path

import ftfy
import spacy

RAIZ = Path(__file__).resolve().parent.parent
TRANSCRIPTS = RAIZ / "transcripts"
DB = RAIZ / "corpus.db"

OBRAS = Path(__file__).resolve().parent / "obras.json"
GRUPOS = Path(__file__).resolve().parent / "grupos.json"

LRC_TAG = re.compile(r"^\[([a-z]+):(.*)\]$")
LRC_VERSO = re.compile(r"^\[(\d+):(\d+(?:\.\d+)?)\]\s*(.*)$")
NOME_ARQ = re.compile(r"^S(\d+)(?:E(\d+)(?:-E(\d+))?)?\s*(?:Extra)?\s*-\s*(.*)\.txt$")
FALA = re.compile(r"^([A-Za-z][^:]{0,45}?)\s*:\s*(.*)$")
CENA = re.compile(r"^\[?\s*(scene|cut|time lapse|flashback)\b", re.I)
RUBRICA = re.compile(r"^(\(|\[|credits sequence|commercial break|opening credits|"
                     r"closing credits|ending credits|end$|the end$)", re.I)
METADADOS = re.compile(r"^(written|transcribed|transcript|directed|teleplay|story|"
                       r"additional|with help|with minor|with minot|note|adjustments|"
                       r"originally|aired)\b", re.I)
PARENTESES = re.compile(r"\([^)]*\)|\[[^\]]*\]")


def limpar(texto):
    texto = ftfy.fix_text(texto)  # conserta mojibake e desentorta aspas
    return re.sub(r"\s+", " ", texto).strip()


def nome_falante(bruto):
    nome = PARENTESES.sub("", bruto).strip(" -")
    if nome.isupper():
        nome = nome.title()
    return nome


def parece_falante(nome):
    return 0 < len(nome.split()) <= 6 and not METADADOS.match(nome)


def ler_episodio(caminho, titulo=None):
    """Devolve lista de (tipo, falante, texto, cena) com tipo em fala/cena/rubrica."""
    linhas = [limpar(l) for l in caminho.read_text(encoding="utf-8", errors="replace").splitlines()]
    linhas = [l for l in linhas if l]
    if linhas and titulo and linhas[0].lower() == titulo.lower():
        linhas = linhas[1:]  # legendas de Brooklyn 99 e HIMYM começam pelo título
    com_falante = sum(1 for l in linhas if FALA.match(l))
    estilo_legenda = com_falante < 0.2 * len(linhas)

    itens, cena, falante, comecou = [], None, None, False
    for linha in linhas:
        if CENA.match(linha):
            cena = PARENTESES.sub(lambda m: m.group(0)[1:-1], linha).strip()
            cena = re.sub(r"^scene\s*:\s*", "", cena, flags=re.I)
            itens.append(("cena", None, cena, cena))
            falante, comecou = None, True
            continue
        apos_rubrica = False
        if RUBRICA.match(linha):
            itens.append(("rubrica", None, linha, cena))
            # "(rubrica) e o resto da fala" continua sendo fala do mesmo personagem
            linha = PARENTESES.sub(" ", linha).strip(" -")
            if not linha or not linha[0].isalnum() or re.match(r"(?i)(credits|commercial|end)", linha):
                continue
            apos_rubrica = True
        m = None if apos_rubrica else FALA.match(linha)
        if estilo_legenda:
            # legenda às vezes marca quem fala ("Amy: I know."): vale só pra essa linha, e só se o
            # prefixo parecer nome ("Officer Mark", "TED"), não frase ("Now here's the deal: ...")
            falante = None
            if m and re.fullmatch(r"[A-Z][\w.'-]*( [A-Z][\w.'-]*){0,2}", m.group(1)):
                falante, linha = nome_falante(m.group(1)), m.group(2)
            m = None
        if m and parece_falante(m.group(1)):
            falante, texto, comecou = nome_falante(m.group(1)), m.group(2), True
        elif not comecou and not estilo_legenda:
            continue  # cabeçalho (título, roteirista, transcritor)
        else:
            texto = linha  # continuação da fala anterior, ou legenda sem falante
            comecou = True
        texto = PARENTESES.sub(" ", texto).strip(" -")
        texto = re.sub(r"\s+", " ", texto)
        if texto:
            itens.append(("fala", falante, texto, cena))
    return itens


def ler_letra(caminho):
    """Letra no formato LRC (ver baixar_letra.py): devolve (cabeçalho, [(segundo ou None, verso)]).
    Linha vazia (pausa instrumental) fica de fora."""
    cabecalho, versos = {}, []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = ftfy.fix_text(linha.strip()).replace("’", "'")
        if m := LRC_VERSO.match(linha):
            if m[3].strip():
                versos.append((int(m[1]) * 60 + float(m[2]), m[3].strip()))
        elif m := LRC_TAG.match(linha):
            cabecalho[m[1]] = m[2].strip()
        elif linha:
            versos.append((None, linha))
    return cabecalho, versos


def segundos(mm_ss):
    m, _, s = (mm_ss or "").partition(":")
    return int(m) * 60 + float(s) if s else None


def limpar_titulo(titulo, caminho, codigo, correcoes):
    """Tira prefixos como "907 - " e "FRIENDS - ", desfaz caixa alta e usa o cabeçalho do arquivo
    quando o nome não traz título nenhum."""
    if codigo in correcoes:
        return correcoes[codigo]
    titulo = titulo.replace("’", "'")
    titulo = re.sub(r"(?i)^(friends\s*)?\d{3,4}\s*-?\s*", "", titulo.strip())
    titulo = re.sub(r"(?i)^friends\s*-\s*", "", titulo)
    if titulo.lower() in ("friends", "untitled document", ""):
        cabecalho = caminho.read_text(encoding="utf-8", errors="replace").splitlines()[:12]
        titulo = next((l.strip() for l in cabecalho if l.strip().lower().startswith("the one")), titulo)
    if titulo.isupper():
        titulo = titulo.title().replace("'S ", "'s ")
    return titulo


def criar_schema(con):
    con.executescript("""
        DROP TABLE IF EXISTS frases; DROP TABLE IF EXISTS linhas; DROP TABLE IF EXISTS episodios;
        DROP TABLE IF EXISTS obras; DROP TABLE IF EXISTS meta; DROP TABLE IF EXISTS grupos;
        CREATE TABLE meta (chave TEXT PRIMARY KEY, valor TEXT);
        CREATE TABLE obras (
            id INTEGER PRIMARY KEY, nome TEXT, tipo TEXT CHECK (tipo IN ('serie', 'filme', 'musica')),
            ano INTEGER, pasta TEXT);
        CREATE TABLE episodios (
            id INTEGER PRIMARY KEY, obra_id INTEGER REFERENCES obras, temporada INTEGER, episodio INTEGER,
            episodio_fim INTEGER, titulo TEXT, arquivo TEXT, duracao_min REAL, palavras INTEGER);
        CREATE TABLE linhas (
            id INTEGER PRIMARY KEY, episodio_id INTEGER REFERENCES episodios, n INTEGER,
            tipo TEXT, falante TEXT, texto TEXT, cena TEXT, segundo REAL);
        CREATE TABLE frases (
            id INTEGER PRIMARY KEY, linha_id INTEGER REFERENCES linhas,
            texto TEXT, tagged TEXT, offsets TEXT);
        CREATE INDEX linhas_ep ON linhas(episodio_id, n);
        CREATE INDEX frases_linha ON frases(linha_id);
        CREATE INDEX episodios_obra ON episodios(obra_id);
    """)


def gravar_grupos(con):
    """Regrava a tabela `grupos` (nome, ordem, obra_id) a partir de grupos.json, casando pela pasta."""
    con.executescript("""DROP TABLE IF EXISTS grupos;
        CREATE TABLE grupos (nome TEXT, ordem INTEGER, obra_id INTEGER REFERENCES obras);""")
    por_pasta = dict(con.execute("SELECT pasta, id FROM obras"))
    nomes_obras = {n.lower() for (n,) in con.execute("SELECT nome FROM obras")}
    grupos = json.loads(GRUPOS.read_text(encoding="utf-8"))["grupos"]
    for ordem, g in enumerate(grupos):
        if g["nome"].lower() in nomes_obras:
            print(f"grupo {g['nome']}: mesmo nome de uma obra, o Claude não vai conseguir usá-lo", file=sys.stderr)
        ids = []
        for pasta in g["obras"]:
            if pasta in por_pasta:
                ids.append(por_pasta[pasta])
            else:
                print(f"grupo {g['nome']}: {pasta} não está no corpus", file=sys.stderr)
        if not ids:
            print(f"grupo {g['nome']} ficou vazio, pulado", file=sys.stderr)
        con.executemany("INSERT INTO grupos VALUES (?,?,?)", [(g["nome"], ordem, i) for i in ids])
    con.commit()
    return con.execute("SELECT count(DISTINCT nome) FROM grupos").fetchone()[0]


def gravar_frases(con, nlp, linhas):
    """Etiqueta cada (linha_id, texto) com o spaCy e grava as frases."""
    for (linha_id, _), doc in zip(linhas, nlp.pipe((t for _, t in linhas), batch_size=256)):
        for sent in doc.sents:
            tokens = [t for t in sent if not t.is_space]
            if not tokens:
                continue
            tagged = " ".join(
                f"{t.lower_.replace('/', '')}/{t.lemma_.lower().replace('/', '')}/{t.tag_}"
                for t in tokens)
            # início de cada token dentro do texto da frase, alinhado com `tagged`
            inicio = tokens[0].idx
            offsets = " ".join(str(t.idx - inicio) for t in tokens)
            texto = doc.text[inicio:tokens[-1].idx + len(tokens[-1].text)]
            con.execute("INSERT INTO frases (linha_id, texto, tagged, offsets) VALUES (?,?,?,?)",
                        (linha_id, texto, tagged, offsets))


def gravar_musica(con, nlp, obra_id, obra, pasta, caminho):
    """Uma música = um "episódio" sem temporada, com o tempo real de cada verso (do LRC) e o artista como
    falante. O refrão repetido fica todo em `linhas` (é o contexto), mas só a primeira vez de cada verso vira
    frase: senão o mesmo verso apareceria várias vezes no resultado."""
    cabecalho, versos = ler_letra(caminho)
    titulo = cabecalho.get("ti") or caminho.stem
    total_s = segundos(cabecalho.get("length"))
    total = sum(len(v.split()) for _, v in versos) or 1
    ep_id = con.execute(
        "INSERT INTO episodios (obra_id, temporada, episodio, episodio_fim, titulo, arquivo, duracao_min, palavras)"
        " VALUES (?,NULL,NULL,NULL,?,?,?,?)",
        (obra_id, titulo, f"{pasta}/{caminho.name}", total_s / 60 if total_s else None, total)).lastrowid
    acumulado, vistos, linhas = 0, set(), []
    for n, (segundo, verso) in enumerate(versos):
        if segundo is None and total_s:  # letra sem tempo: estima pelas palavras, como nas séries
            segundo = acumulado / total * total_s
        linha_id = con.execute(
            "INSERT INTO linhas (episodio_id, n, tipo, falante, texto, cena, segundo) VALUES (?,?,'fala',?,?,NULL,?)",
            (ep_id, n, obra["nome"], verso, segundo)).lastrowid
        acumulado += len(verso.split())
        chave = re.sub(r"\W+", " ", verso.lower()).strip()
        if chave not in vistos:
            vistos.add(chave)
            linhas.append((linha_id, verso))
    gravar_frases(con, nlp, linhas)
    con.commit()
    print(f"{obra['nome']} - {titulo}: {len(versos)} versos, {len(linhas)} sem repetir", flush=True)


def main():
    nlp = spacy.load("en_core_web_sm", disable=["ner"])
    # monta num arquivo à parte e só troca no fim, pra quem estiver lendo o banco não ver ele pela metade
    novo = DB.with_suffix(".db.novo")
    novo.unlink(missing_ok=True)
    con = sqlite3.connect(novo)
    criar_schema(con)

    obras = {k: v for k, v in json.loads(OBRAS.read_text(encoding="utf-8")).items()
             if not k.startswith("_")}
    for pasta in sorted(p.name for p in TRANSCRIPTS.iterdir() if p.is_dir()):
        if pasta not in obras:
            print(f"pasta sem entrada em obras.json, ignorada: {pasta}", file=sys.stderr)
    for pasta, obra in obras.items():
        if not (TRANSCRIPTS / pasta).is_dir():
            print(f"pasta não encontrada, ignorada: {pasta}", file=sys.stderr)
            continue
        obra_id = con.execute(
            "INSERT INTO obras (nome, tipo, ano, pasta) VALUES (?,?,?,?)",
            (obra["nome"], obra["tipo"], obra.get("ano"), pasta)).lastrowid
        serie, duracao = obra["nome"], obra.get("duracao_min")
        arquivos = sorted((TRANSCRIPTS / pasta).glob("*.txt"))
        nomes = {c.name for c in arquivos}
        for caminho in arquivos:
            if caminho.name.replace(".txt", " (Uncut).txt") in nomes:
                continue  # existe a versão sem cortes do mesmo episódio
            if obra["tipo"] == "musica":
                gravar_musica(con, nlp, obra_id, obra, pasta, caminho)
                continue
            if obra["tipo"] == "filme":
                temporada, ep, ep_fim, titulo = None, None, None, obra["nome"]
            else:
                m = NOME_ARQ.match(caminho.name)
                if not m:
                    print(f"ignorado: {caminho.name}", file=sys.stderr)
                    continue
                temporada, ep, ep_fim, titulo = m.groups()
                temporada = int(temporada)
                ep = int(ep) if ep else None
                ep_fim = int(ep_fim) if ep_fim else ep
                codigo = f"S{temporada:02d}E{ep:02d}" if ep else f"S{temporada:02d}"
                titulo = limpar_titulo(titulo, caminho, codigo, obra.get("titulos", {}))
            n_eps = (ep_fim - ep + 1) if ep else 1
            itens = ler_episodio(caminho, titulo)
            falas = [i for i in itens if i[0] == "fala"]
            total = sum(len(i[2].split()) for i in falas) or 1
            minutos = duracao * n_eps
            cur = con.execute(
                "INSERT INTO episodios (obra_id, temporada, episodio, episodio_fim, titulo, arquivo,"
                " duracao_min, palavras) VALUES (?,?,?,?,?,?,?,?)",
                (obra_id, temporada, ep, ep_fim, titulo, f"{pasta}/{caminho.name}", minutos, total))
            ep_id = cur.lastrowid

            # tempo estimado = fração das palavras já faladas × duração nominal
            acumulado, linhas = 0, []
            for n, (tipo, falante, texto, cena) in enumerate(itens):
                segundo = acumulado / total * minutos * 60
                cur = con.execute(
                    "INSERT INTO linhas (episodio_id, n, tipo, falante, texto, cena, segundo)"
                    " VALUES (?,?,?,?,?,?,?)", (ep_id, n, tipo, falante, texto, cena, segundo))
                if tipo == "fala":
                    linhas.append((cur.lastrowid, texto))
                    acumulado += len(texto.split())

            gravar_frases(con, nlp, linhas)
            con.commit()
            print(f"{serie} {caminho.name[:6]}: {len(falas)} falas", flush=True)

    n = con.execute("SELECT count(*) FROM frases").fetchone()[0]
    gravar_grupos(con)
    # muda a cada indexação: invalida o cache de buscas (ocorrencias) guardado no dados.db
    con.execute("INSERT INTO meta VALUES ('versao', ?), ('gerado_em', datetime('now', 'localtime'))",
                (uuid.uuid4().hex,))
    con.commit()
    n_obras = con.execute("SELECT count(*) FROM obras").fetchone()[0]
    con.close()
    novo.replace(DB)
    print(f"pronto: {n} frases de {n_obras} obras em {DB}")
    # o banco foi recriado do zero: refaz o cache das estruturas de fábrica (ver cache_fabrica.py)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import cache_fabrica
    cache_fabrica.main(DB)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--so-grupos"]:
        banco = Path(sys.argv[2]) if len(sys.argv) > 2 else DB
        with sqlite3.connect(banco) as c:
            print(f"{gravar_grupos(c)} grupos gravados em {banco}")
    else:
        main()
