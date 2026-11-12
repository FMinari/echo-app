// Item da lista lateral (estruturas, aulas): nome à esquerda, um detalhe à direita, e o aberto marcado.
import { el } from "../lib/dom.js";

/**
 * @param {object} op
 * @param {string} op.rotulo
 * @param {string|Node} [op.detalhe]   à direita (ex.: nível "B1", "12 frases")
 * @param {boolean} [op.atual]         é o que está aberto agora
 * @param {string} [op.classe]         classe a mais (ex.: item-estrutura, para os testes acharem)
 * @param {() => void} op.aoClicar
 */
export function itemLista({ rotulo, detalhe = null, atual = false, classe = "", aoClicar }) {
  return el("button", { type: "button", class: `item-lista ${classe}`.trim(), "aria-current": String(atual), onclick: aoClicar },
    el("span", { text: rotulo }),
    detalhe === null || detalhe === "" ? null
      : typeof detalhe === "string" ? el("span", { class: "item-lista-detalhe", text: detalhe }) : detalhe);
}
