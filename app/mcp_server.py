"""Servidor MCP (stdio) para o Claude Desktop: busca de estruturas gramaticais nas falas.

Rodar: uv run --directory <pasta do app> python mcp_server.py
"""
import functools
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from nucleo import bancos, busca, catalogo, favoritos, grupos, registro, sobre  # noqa: E402
from nucleo.registro import NaoEncontrado, log  # noqa: E402
from nucleo.padrao import __doc__ as LINGUAGEM_PADRAO  # noqa: E402

INSTRUCOES = """
Você é o lado Claude do Sitcomática, o app em que uma estudante brasileira de inglês procura
exemplos reais de estruturas gramaticais em falas de séries e filmes e em letras de música (Big Bang Theory, Friends,
How I Met Your Mother, The Office, Brooklyn 99…). Responda sempre em português; as frases de
exemplo ficam em inglês.

A cliente usa o plano gratuito do Claude, com poucas mensagens: resolva cada pedido com o mínimo de
chamadas (normalmente um `listar_estruturas` e um `buscar`), sem buscas repetidas à toa.

## Buscar exemplos
1. Ache a estrutura no catálogo (`listar_estruturas`). Se a cliente descrever com outras palavras
   ("aquela do if com had"), escolha a estrutura certa e diga qual usou.
2. `buscar` com a estrutura, as obras/personagem/temporada pedidos e a quantidade pedida
   (padrão 10). `obras` aceita nome de grupo ("Pixar", "Animações Disney", "High School Musical",
   ou um grupo que a cliente montou no app; veja `listar_obras`); "só filmes"/"só séries"/"só músicas" é `tipo`. Peça uns 30% a mais e descarte, em silêncio, o que claramente não for a estrutura
   (ex.: "had to" num past perfect, "if" no sentido de "whether"). Se descartar algum, pergunte
   no fim se a cliente quer marcar como falso positivo; só chame `marcar_falso_positivo` com esse ok.
3. Se a estrutura não existir no catálogo, ofereça cadastrar (roteiro abaixo).

## Formato da resposta
Uma linha com o total ("Achei 263 frases de past perfect: 148 em Big Bang, 115 em Friends. Quem
mais usa: Ross."), e então a lista numerada:

**1. Friends · S04E12 · "The One With The Embryos" · ~17:00**
> **Monica:** I mean if they **had lost**, we **would've made** them get rid of the birds.
*Por que é third conditional:* had lost = past perfect (condição que não aconteceu) ·
would've made = would have + particípio (consequência imaginada).
*Cena:* resumo curto da cena + a fala anterior que dá sentido.

- O negrito na frase é o trecho que realiza a estrutura (vem marcado com ** no resultado).
- Explique em uma linha, em português simples, como aquela frase realiza a estrutura. Aponte
  pegadinhas quando houver (ex.: 'd = had, não would).
- Tradução só se a cliente pedir.
- O tempo (~mm:ss) é estimado pela posição da fala no roteiro; avise uma vez, no fim, que pode
  errar uns 2–3 minutos.
- Alguns episódios vêm de legendas (Big Bang S11–S12, boa parte de Brooklyn 99 e de HIMYM):
  sem cena e quase sem personagem; se faltar, diga "personagem não identificado" e use as falas
  vizinhas como contexto.
- Feche oferecendo: mais exemplos (outra semente), outra obra/personagem, ou guardar algum nos
  favoritos (`favoritar`).

## Cadastrar estrutura nova
1. Pergunte o nome e, se a cliente quiser, um exemplo ou fórmula (opcional; não insista).
2. Monte a regra na linguagem de padrões (descrita em `testar_padrao`) e rode `testar_padrao`.
3. Mostre o total e 5–8 exemplos. Ajuste a regra até a amostra ficar limpa (no máximo 3 testes).
4. Só chame `cadastrar_estrutura` depois que a cliente aprovar. Preencha explicação em português,
   fórmula, nível (A1–C2), categoria, 1–2 frases-modelo e pegadinhas conhecidas.
"""

mcp = MCPServer("frases-series", instructions=INSTRUCOES)


def ferramenta(**opcoes):
    """Registra a função como ferramenta e devolve erros conhecidos como texto explicativo,
    para o Claude entender o que corrigir (senão ele só recebe "Error executing tool")."""
    def registrar(func):
        @functools.wraps(func)
        def envolvida(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except NaoEncontrado as e:
                return f"Erro: {e}. Confira o nome com listar_estruturas ou listar_obras."
            except (ValueError, re.error) as e:
                return f"Erro: {e}"
            except sqlite3.IntegrityError as e:
                if "UNIQUE" in str(e):
                    return "Erro: já existe uma estrutura com esse nome. Use editar_estrutura ou outro nome."
                log.exception("erro em %s %r", func.__name__, kwargs or args)
                return _inesperado(e)
            except Exception as e:  # noqa: BLE001 — senão o Claude só recebe "Error executing tool"
                log.exception("erro em %s %r", func.__name__, kwargs or args)
                return _inesperado(e)
        return mcp.tool(**opcoes)(envolvida)
    return registrar


def _inesperado(erro):
    return (f"Erro inesperado no app: {registro.explicar(erro)} Não tente de novo em seguida; diga à "
            f"cliente que a pasta de erros fica em {registro.pasta_erros()} e que pode mandar pro desenvolvedor.")


def _negrito(frase, destaques):
    for ini, fim in sorted(destaques, reverse=True):
        frase = f"{frase[:ini]}**{frase[ini:fim]}**{frase[fim:]}"
    return frase


def _curto(texto, n=180):
    return texto if len(texto) <= n else texto[:n].rstrip() + "…"


def _formatar(r, titulo, semente):
    obras = ", ".join(f"{o} {n}" for o, n in r["por_obra"].items()) or "nenhuma"
    top = ", ".join(f"{t['falante']} {t['frases']}" for t in r["top_falantes"]) or "—"
    linhas = [f"{titulo} · {r['total']} frases ({obras}) · quem mais usa: {top}",
              f"Mostrando {len(r['resultados'])} (semente {semente}; troque a semente para outra amostra)."]
    for i, x in enumerate(r["resultados"], 1):
        onde = (x["obra"] if x["tipo"] == "filme" else f"{x['obra']} \"{x['titulo']}\"" if x["tipo"] == "musica"
                else f"{x['obra']} {x['referencia']} \"{x['titulo']}\"")
        linhas += ["", f"[{i}] {onde} · {x['tempo']} · frase_id {x['frase_id']}",
                   f"{x['falante'] or 'personagem não identificado'}: {_negrito(x['frase'], x['destaques'])}"]
        if x["cena"]:
            linhas.append(f"cena: {_curto(x['cena'])}")
        linhas += [f"antes: {v['falante'] or '?'}: {_curto(v['texto'])}" for v in x["antes"]]
        linhas += [f"depois: {v['falante'] or '?'}: {_curto(v['texto'])}" for v in x["depois"][:1]]
        linhas.append(f"arquivo: {x['arquivo']}")
    return "\n".join(linhas)


@ferramenta()
def listar_estruturas(categoria: str | None = None) -> str:
    """Lista o catálogo de estruturas gramaticais. Sem categoria: só os nomes (com o nível), agrupados
    por categoria — o catálogo é grande. Com categoria (ex.: "Modais", "Phrasal verbs"): nome, nível e
    fórmula de cada uma."""
    estruturas = catalogo.listar()
    if categoria:
        chave = categoria.strip().lower()
        escolhidas = [e for e in estruturas if (e["categoria"] or "").lower() == chave]
        if not escolhidas:
            existentes = sorted({e["categoria"] or "sem categoria" for e in estruturas})
            return f"Categoria não encontrada: {categoria!r}. Categorias: {', '.join(existentes)}."
        return "\n".join(f"- {e['nome']} · {e['nivel'] or '?'} · {e['formula'] or ''}" for e in escolhidas)
    grupos = {}
    for e in estruturas:
        grupos.setdefault(e["categoria"] or "sem categoria", []).append(f"{e['nome']} ({e['nivel'] or '?'})")
    return "\n".join(f"{c}: {'; '.join(nomes)}" for c, nomes in grupos.items()) or "Catálogo vazio."


@ferramenta()
def ver_estrutura(nome: str) -> str:
    """Mostra tudo de uma estrutura do catálogo: explicação, fórmula, regra de busca, exemplos e pegadinhas."""
    e = catalogo.obter(nome)
    campos = ["nome", "categoria", "nivel", "explicacao", "formula", "regra_em_portugues", "padrao", "texto",
              "excluir", "exemplos", "pegadinhas", "origem", "atualizado_em"]
    return "\n".join(f"{c}: {e[c]}" for c in campos if e.get(c))


@ferramenta()
def listar_obras() -> str:
    """Lista as séries, filmes e artistas (músicas) disponíveis para busca, e os grupos (que valem em `obras`)."""
    obras = busca.listar_obras()
    nomes = {o["id"]: o["nome"] for o in obras}
    linhas = [f"Sitcomática {sobre.numero()} · banco de frases de {busca.rotulo_corpus()}.", "", "Obras:"]
    rotulo = {"serie": "série", "filme": "filme", "musica": "músicas"}
    linhas += [f"- {o['nome']} ({rotulo.get(o['tipo'], o['tipo'])}"
               + (f", temporadas {o['primeira_temporada']}–{o['ultima_temporada']}, {o['episodios']} episódios"
                  if o["tipo"] == "serie" else f": {o['episodios']}" if o["tipo"] == "musica"
                  else f", {o['ano']}" if o["ano"] else "") + ")"
               for o in obras]
    if gs := grupos.listar():
        linhas += ["", "Grupos:"]
        linhas += [f"- {g['nome']}{' (da cliente)' if g['meu'] else ''}: {', '.join(nomes[i] for i in g['obras'])}"
                   for g in gs]
    return "\n".join(linhas)


@ferramenta()
def buscar(estrutura: str, obras: list[str] | None = None, tipo: str | None = None,
           personagem: str | None = None, temporada: int | None = None,
           quantidade: int = 10, semente: int = 0) -> str:
    """Busca frases reais com uma estrutura do catálogo.

    estrutura: nome exato do catálogo (veja listar_estruturas).
    obras: nomes das obras (ex.: ["Friends"]); vazio = todas.
    tipo: "serie", "filme" ou "musica" para limitar; vazio = todos.
    personagem: ex. "Sheldon". temporada: número.
    quantidade: quantas frases mostrar (amostra aleatória). semente: troque para outra amostra.
    """
    r = busca.buscar(estrutura=estrutura, obras=obras, tipo=tipo, falante=personagem,
                     temporada=temporada, limite=max(1, min(quantidade, 40)), semente=semente)
    return _formatar(r, catalogo.obter(estrutura)["nome"], semente)


@ferramenta(description=(
    "Testa uma regra de busca ainda não cadastrada e mostra o total e uma amostra.\n\n"
    "padrao: regra na linguagem de tokens abaixo. texto: regex sobre o texto da frase. "
    "excluir: regex; frases que casarem são descartadas. Informe padrao e/ou texto.\n"
    + LINGUAGEM_PADRAO))
def testar_padrao(padrao: str | None = None, texto: str | None = None, excluir: str | None = None,
                  obras: list[str] | None = None, quantidade: int = 8, semente: int = 0) -> str:
    r = busca.buscar(padrao=padrao, texto=texto, excluir=excluir, obras=obras,
                     limite=max(1, min(quantidade, 20)), semente=semente)
    return _formatar(r, "Teste de regra", semente)


@ferramenta()
def cadastrar_estrutura(nome: str, explicacao: str, formula: str, padrao: str | None = None,
                        texto: str | None = None, excluir: str | None = None,
                        categoria: str | None = None, nivel: str | None = None,
                        exemplos: list[str] | None = None, pegadinhas: str | None = None) -> str:
    """Salva uma estrutura nova no catálogo. Só use depois de testar_padrao e do ok da estudante.

    nivel: A1, A2, B1, B2, C1 ou C2. categoria: ex. "Condicionais", "Tempos verbais", "Modais".
    """
    e = catalogo.criar(nome=nome, explicacao=explicacao, formula=formula, padrao=padrao, texto=texto,
                       excluir=excluir, categoria=categoria, nivel=nivel, exemplos=exemplos or [],
                       pegadinhas=pegadinhas, origem="claude")
    total = busca.buscar(estrutura=e["id"], limite=0)["total"]
    return f"Estrutura '{e['nome']}' cadastrada (id {e['id']}). {total} frases encontradas no corpus."


@ferramenta()
def editar_estrutura(nome: str, novo_nome: str | None = None, explicacao: str | None = None,
                     formula: str | None = None, padrao: str | None = None, texto: str | None = None,
                     excluir: str | None = None, categoria: str | None = None, nivel: str | None = None,
                     exemplos: list[str] | None = None, pegadinhas: str | None = None) -> str:
    """Altera campos de uma estrutura do catálogo (só os informados). Mudar padrao/texto/excluir
    refaz a busca dessa estrutura na próxima vez e troca a regra montada com peças (se houver) pela
    sua. Para apagar um campo opcional, mande ""."""
    mudancas = {k: v for k, v in dict(nome=novo_nome, explicacao=explicacao, formula=formula,
                                      padrao=padrao, texto=texto, excluir=excluir, categoria=categoria,
                                      nivel=nivel, exemplos=exemplos, pegadinhas=pegadinhas).items()
                if v is not None}
    mudancas = {k: (None if v == "" else v) for k, v in mudancas.items()}
    e = catalogo.editar(nome, **mudancas)
    return f"Estrutura '{e['nome']}' atualizada: {', '.join(mudancas) or 'nada mudou'}."


@ferramenta()
def marcar_falso_positivo(estrutura: str, frase_id: int) -> str:
    """Marca que uma frase do resultado NÃO é exemplo da estrutura; ela some das próximas buscas.
    Use o frase_id mostrado no resultado do buscar. Só com o ok da estudante."""
    x = busca.detalhar(frase_id)
    catalogo.marcar_falso_positivo(estrutura, x["arquivo"], x["frase"], frase_id)
    return f"Marcado: \"{_curto(x['frase'], 80)}\" não aparece mais em {catalogo.obter(estrutura)['nome']}."


@ferramenta()
def favoritar(frase_id: int, estrutura: str | None = None, nota: str | None = None) -> str:
    """Guarda uma frase (aparece na aba Aulas do app, em "Sem aula").
    Use o frase_id do resultado do buscar; informe a estrutura para guardar o destaque certo."""
    x = busca.detalhar(frase_id, estrutura)
    favoritos.guardar(x, nota)
    return f"Guardada nos favoritos: \"{_curto(x['frase'], 80)}\"."


@ferramenta()
def listar_favoritos(estrutura: str | None = None) -> str:
    """Lista as frases guardadas nos favoritos (todas ou só de uma estrutura)."""
    favs = favoritos.listar(estrutura)
    if not favs:
        return "Nenhum favorito ainda."
    return "\n".join(
        f"- [{f['estrutura'] or 'sem estrutura'}] {f['obra']} {f['referencia']} {f['tempo']} · "
        f"{f['falante'] or '?'}: {_negrito(f['frase'], f['destaques'])}" + (f" · nota: {f['nota']}" if f["nota"] else "")
        for f in favs)


if __name__ == "__main__":
    registro.configurar("mcp")  # só arquivo: o stdout aqui é o canal do protocolo
    try:
        bancos.fazer_backup()
    except Exception:  # noqa: BLE001 — backup não pode impedir o Claude de usar o app
        log.exception("backup do dados.db falhou")
    mcp.run()
