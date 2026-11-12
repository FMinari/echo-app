// Fichas clicáveis com uma contagem e, se houver, uma linha de explicação (ex.: os phrasal verbs de um
// verbo: "get over 390" e embaixo "superar, esquecer").
import { el } from "../lib/dom.js";

/** O começo da explicação (até o primeiro ";"), para caber na ficha; a inteira vai na dica do mouse. */
const curta = (texto) => texto.split(";")[0].trim();

/**
 * @param {object} op
 * @param {{texto: string, numero: number, detalhe?: string}[]} op.itens
 * @param {string} [op.ativo]                     texto da ficha escolhida agora
 * @param {string} op.rotulo                      nome da lista para o leitor de tela
 * @param {(texto: string) => void} op.aoEscolher
 */
export function fichas({ itens, ativo = null, rotulo, aoEscolher }) {
  return el("div", { class: "fichas", role: "list", "aria-label": rotulo },
    itens.map((x) => el("button", {
      type: "button", role: "listitem", class: "ficha",
      "aria-pressed": String(x.texto === ativo), title: x.detalhe || null,
      onclick: () => aoEscolher(x.texto),
    },
    el("span", { class: "ficha-topo" },
      el("span", { text: x.texto }),
      el("span", { class: "ficha-numero", text: x.numero.toLocaleString("pt-BR") })),
    x.detalhe ? el("span", { class: "ficha-detalhe", text: curta(x.detalhe) }) : null)));
}
