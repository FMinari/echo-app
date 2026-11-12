// Escolha entre poucas opções lado a lado, uma ligada por vez (ex.: "Do catálogo | Escrever o que procuro").
import { el } from "../lib/dom.js";

/**
 * @param {object} op
 * @param {{valor: string, rotulo: string}[]} op.opcoes
 * @param {string} op.valor                 a opção ligada no começo
 * @param {string} op.rotulo                nome do grupo para o leitor de tela
 * @param {(valor: string) => void} op.aoMudar
 * @returns {HTMLElement & {valor: string}}  `valor` (get/set) troca sem chamar aoMudar
 */
export function alternador({ opcoes, valor, rotulo, aoMudar = () => {} }) {
  const botoes = opcoes.map((o) => el("button", {
    type: "button", role: "radio", "data-valor": o.valor, text: o.rotulo,
    onclick: () => { if (o.valor !== atual) { pintar(o.valor); aoMudar(o.valor); } },
  }));
  const raiz = el("div", { class: "alternador", role: "radiogroup", "aria-label": rotulo }, botoes);
  let atual;
  function pintar(v) {
    atual = v;
    for (const b of botoes) b.setAttribute("aria-checked", String(b.dataset.valor === v));
  }
  pintar(valor);
  Object.defineProperty(raiz, "valor", { get: () => atual, set: pintar });
  return raiz;
}
