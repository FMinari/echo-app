// Resultado da busca: resumo (total, quem mais usa, por página, barra séries × filmes × músicas) e uma
// seção recolhível por tipo (Séries, Filmes, Músicas), cada uma com seus cartões e seu paginador.
import { el, trocar } from "../../lib/dom.js";
import { guardar, lembrar } from "../../lib/armazenamento.js";
import { plural } from "../../lib/formato.js";
import { estado } from "../../estado.js";
import { cartaoFrase } from "../../componentes/cartao-frase.js";
import { paginador } from "../../componentes/paginador.js";
import { recolhivel } from "../../componentes/recolhivel.js";
import { estadoVazio } from "../../componentes/vazio.js";
import { TIPOS } from "../../lib/tipos.js";

export const POR_PAGINA = [10, 20, 40];

const tipoDaObra = (nome) => estado.obras.find((o) => o.nome === nome)?.tipo || "serie";

function secaoTipo(t, r, { estruturaId, aoIrPagina }) {
  const total = r.por_tipo[t.chave];
  const paginas = Math.max(1, Math.ceil(total / r.por_pagina));
  const atual = r.pagina?.[t.chave] || 1;
  const itens = r.resultados.filter((x) => (x.tipo || "serie") === t.chave);
  const obras = Object.entries(r.por_obra).filter(([nome]) => tipoDaObra(nome) === t.chave).sort((a, b) => b[1] - a[1]);
  const onde = obras.slice(0, 6).map(([nome, n]) => `${nome} ${n}`).join(" · ")
    + (obras.length > 6 ? ` · e mais ${obras.length - 6}` : "");
  return recolhivel({
    titulo: t.nome,
    detalhe: plural(total, "frase") + (paginas > 1 ? ` · página ${atual} de ${paginas}` : ""),
    marcador: t.cor,
    aberto: lembrar(`secao-${t.chave}`, true),
    aoAlternar: (aberto) => guardar(`secao-${t.chave}`, aberto),
    classe: "secao-tipo",
    atributos: { "data-tipo": t.chave },
  },
  el("p", { class: "secao-obras", text: onde }),
  ...itens.map((x) => cartaoFrase(x, { estrutura: estruturaId })),
  paginas > 1 ? paginador({ atual, total: paginas, aoIr: (n) => aoIrPagina(t.chave, n) }) : null);
}

/**
 * @param {HTMLElement} alvo
 * @param {object} r     resposta da api "buscar"
 * @param {object} ctx
 * @param {string} ctx.nomeEstrutura
 * @param {number} ctx.estruturaId
 * @param {string} [ctx.significado]     o que o phrasal verb da busca escrita quer dizer
 * @param {HTMLElement} [ctx.acao]       algo a mais no resumo (ex.: "Guardar como estrutura")
 * @param {string} ctx.filtro            texto do filtro dos resultados ("" sem filtro)
 * @param {boolean} ctx.comPersonagem    com personagem escolhido, "quem mais usa" seria só ele
 * @param {number} ctx.porPagina
 * @param {(n: number) => void} ctx.aoMudarPorPagina
 * @param {(tipo: string, pagina: number) => void} ctx.aoIrPagina
 */
export function desenharResultado(alvo, r, ctx) {
  const { filtro } = ctx;
  if (!r.total && r.total_sem_filtro) {
    trocar(alvo, estadoVazio(`Nenhuma das ${r.total_sem_filtro} frases bate com “${filtro}”.`,
      "O filtro procura no nome da série, do filme ou do artista e no personagem. Tente outro nome ou apague o filtro."));
    return;
  }
  if (!r.total) {
    trocar(alvo, estadoVazio("Nenhuma frase encontrada.", "Tente outras séries, tire o personagem ou a temporada."));
    return;
  }
  const tipos = TIPOS.filter((t) => r.por_tipo[t.chave]);
  const top = ctx.comPersonagem ? "" : r.top_falantes.map((t) => `${t.falante} (${t.frases})`).join(", ");
  const titulo = (filtro ? `${r.total} de ${plural(r.total_sem_filtro, "frase")}` : plural(r.total, "frase"))
    + ` de ${ctx.nomeEstrutura}` + (filtro ? ` com “${filtro}”` : "");
  const resumo = el("div", { class: "resumo" },
    el("h2", { text: titulo }),
    ctx.significado ? el("p", { class: "significado" }, el("b", { text: "O que quer dizer: " }), ctx.significado) : null,
    top ? el("p", { text: `Quem mais usa: ${top}.` }) : null,
    el("label", { class: "por-pagina" }, "Mostrar ",
      el("select", { "aria-label": "Frases por página", onchange: (ev) => ctx.aoMudarPorPagina(Number(ev.target.value)) },
        POR_PAGINA.map((n) => el("option", { value: n, text: n, selected: n === ctx.porPagina }))),
      " por página"),
    ctx.acao || null,
    tipos.length > 1
      ? el("div", { class: "barras" }, tipos.map((t) => el("span", { style: `flex:${r.por_tipo[t.chave]};background:${t.cor}` })))
      : null);
  trocar(alvo, resumo, tipos.map((t) => secaoTipo(t, r, ctx)));
}
