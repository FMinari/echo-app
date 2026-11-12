// Liga/desliga com nome e uma linha explicando o que muda (ex.: "Aceitar outras formas").
import { el } from "../lib/dom.js";

/**
 * @param {object} op
 * @param {string} op.rotulo
 * @param {string} [op.detalhe]
 * @param {boolean} op.ligado
 * @param {(ligado: boolean) => void} op.aoMudar
 * @returns {HTMLElement & {ligado: boolean}}  `ligado` (get/set) troca sem chamar aoMudar
 */
export function interruptor({ rotulo, detalhe = null, ligado, aoMudar = () => {} }) {
  const caixa = el("input", {
    type: "checkbox", role: "switch", checked: ligado,
    onchange: () => aoMudar(caixa.checked),
  });
  const raiz = el("label", { class: "interruptor" },
    caixa,
    el("span", { class: "interruptor-trilho", "aria-hidden": "true" }),
    el("span", { class: "interruptor-texto" },
      el("span", { class: "interruptor-rotulo", text: rotulo }),
      detalhe ? el("span", { class: "interruptor-detalhe", text: detalhe }) : null));
  Object.defineProperty(raiz, "ligado", { get: () => caixa.checked, set: (v) => { caixa.checked = !!v; } });
  return raiz;
}
