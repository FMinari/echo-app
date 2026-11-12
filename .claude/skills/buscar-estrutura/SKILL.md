---
name: buscar-estrutura
description: Busca nas transcrições de Big Bang Theory, Friends, How I Met Your Mother, The Office e Brooklyn 99 exemplos reais de uma estrutura gramatical do inglês (zero/first/second/third conditional, past perfect, present perfect continuous, used to, passive, reported speech, wish, phrasal verbs etc.) e devolve uma lista com série, temporada, episódio, a frase, o contexto da cena e o tempo estimado no episódio. Use quando o usuário pedir "exemplos de <estrutura>", "onde alguém usa <construção>", "frases com <padrão>" ou der uma frase-modelo para achar parecidas.
---

# Buscar estrutura gramatical nas séries

## Entrada

1. **Estrutura** (obrigatória): o nome da construção. Ex.: "first conditional", "past perfect", "used to".
2. **Exemplo ou fórmula** (opcional): uma fórmula ("if + present simple, will + verbo") ou uma
   frase-modelo ("if you cut that in half, you will get…"). Serve para afinar a busca.
3. Filtros (opcionais): série, temporada, personagem, quantidade (padrão: 10).

Se o usuário não disse a estrutura, pergunte só isso. **Não peça** o exemplo se ele não veio:
é opcional, siga sem ele. Mas diga numa linha, no começo da resposta, que dá pra mandar
um exemplo ou uma fórmula pra refinar.

## Como usar o exemplo

- **Fórmula** ("if + present simple") → traduza direto para o `--padrao`.
- **Frase-modelo** → descubra a estrutura dela (ex.: "if you cut… you will get" = if + present
  simple + will + verbo base = first conditional) e use isso como alvo. Na hora de filtrar os
  candidatos, prefira os que se parecem com o modelo na forma: mesma ordem das orações, mesma
  pessoa, mesmo tipo de verbo. Não exija as mesmas palavras. Se o exemplo e o nome da estrutura
  não baterem (ex.: "past perfect" com uma frase no present perfect), avise e pergunte qual vale.

## Passos

1. Se `corpus.db` não existir na raiz do projeto, rode `.venv/bin/python ferramentas/indexar.py`
   (leva alguns minutos).
2. Veja se a estrutura já está no catálogo: `.venv/bin/python -I ferramentas/buscar.py --listar`.
   Se estiver, use `--estrutura "<nome>"`: a regra já foi conferida e a busca vem do cache. Se não
   estiver, monte o `--padrao` (linguagem em `ferramentas/buscar.py --help`, receitas abaixo).
   Peça ~3× a quantidade desejada (`--limite 30` para entregar 10), porque parte será descartada.
3. Rode a busca:
   ```bash
   .venv/bin/python -I ferramentas/buscar.py (--estrutura "<nome>" | --padrao '<padrão>') \
     [--texto '<regex>'] [--obra friends --obra "big bang theory"] [--temporada N] \
     [--falante Nome] --limite 30
   ```
   Para uma amostra diferente, troque `--semente`.
4. **Confira cada candidato à mão.** O etiquetador erra e o padrão é largo. Descarte o que não for
   a estrutura de verdade (ex.: "had" de posse num falso past perfect; "if" de "whether" em
   "I don't know if he will"; frases cortadas). Se sobrar pouco, ajuste o padrão ou troque a semente
   e rode de novo. Se o padrão casar milhares de frases, aperte a busca.
5. Entregue no formato abaixo.

## Receitas de padrão

Tags úteis: VB base · VBD passado · VBN particípio · VBG gerúndio · VBP/VBZ presente · MD modal ·
RB advérbio · PRP pronome · NN substantivo. `l=` casa todas as formas do verbo (`l=have` pega
has/had/'d/'ve).

| Estrutura | Padrão |
|---|---|
| zero conditional | `[w=if|when] ... [t=VBP|VBZ] ... [t=VBP|VBZ]` + `--excluir '\b(will|would|\'ll|\'d)\b'` |
| first conditional | `if ... [t=VBP|VBZ] ... [w=will|'ll|wo] [t=RB]* [t=VB]` (ou com a oração do will primeiro: `[w=will|'ll] ... if ... [t=VBP|VBZ]`) |
| second conditional | `if ... [t=VBD] ... [w=would|'d] [t=RB]* [t=VB]` |
| third conditional | `if ... [l=have t=VBD] [t=RB]* [t=VBN] ... [w=would|'d|could|might] [t=RB]* [w=have|'ve] [t=VBN]` |
| past perfect | `[l=have t=VBD] [t=RB]* [t=VBN]` (descarte "had to") |
| past perfect continuous | `[l=have t=VBD] [t=RB]* [w=been] [t=VBG]` |
| present perfect | `[l=have t=VBP|VBZ] [t=RB]* [t=VBN]` |
| present perfect continuous | `[l=have t=VBP|VBZ] [t=RB]* [w=been] [t=VBG]` |
| future continuous | `[w=will|'ll] [t=RB]* [w=be] [t=VBG]` |
| future perfect | `[w=will|'ll] [t=RB]* [w=have] [t=VBN]` |
| used to | `[w=used] [w=to] [t=VB]` |
| be going to | `[l=be] [w=going] [w=to] [t=VB]` |
| passiva | `[l=be] [t=RB]* [t=VBN]` + `--excluir` conforme o caso |
| wish + passado | `[w=wish] [t=PRP|NN.*] [t=VBD]` |
| modal perfeito (should have done…) | `[w=should|could|would|might|must] [t=RB]* [w=have|'ve] [t=VBN]` |

Para algo lexical (um phrasal verb, uma expressão), use `--texto`, com ou sem `--padrao`:
`--texto "\bgive(s|n)? up\b|\bgave up\b"`.

## Formato da resposta

Uma linha dizendo o que foi buscado (e, se não houve exemplo, que dá pra mandar um), depois a lista:

```
1. **Friends · S03E15 · "The One Where Ross and Rachel Take A Break" · ~08:30**
   > **Ross:** If you **had told** me, I **would have understood**.
   *Cena:* Central Perk, Rachel e Ross brigando. *Antes:* Rachel: "You never asked."
```

- Coloque em negrito o trecho que realiza a estrutura.
- Contexto da cena: a linha `cena:` resumida + a fala anterior relevante, em uma linha.
  Episódios que vêm de legendas (Big Bang S11–S12, boa parte de Brooklyn 99 e de HIMYM) não têm
  cena e quase nunca falante: diga "personagem não identificado" e use as falas vizinhas como contexto.
- O tempo é **estimado** (posição da fala no texto × duração nominal de 21–22 min, arredondada
  para 30 s). Diga uma vez, no fim, que pode errar uns 2–3 minutos.
- Feche com uma linha: quantas frases casaram no total, e que dá pra pedir mais, outra série ou
  outro personagem.
