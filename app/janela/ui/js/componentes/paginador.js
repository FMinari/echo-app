// [primeira] [‹ Anterior] Página 2 de 22 [Próxima ›] [última]
import { el } from "../lib/dom.js";
import { icone } from "./icones.js";

/**
 * @param {object} op
 * @param {number} op.atual
 * @param {number} op.total
 * @param {(pagina: number) => void} op.aoIr
 */
export function paginador({ atual, total, aoIr }) {
  const botao = (rotulo, n, ...conteudo) => el("button", {
    type: "button", class: "btn", title: rotulo, "aria-label": rotulo,
    disabled: n < 1 || n > total || n === atual, onclick: () => aoIr(n),
  }, ...conteudo);
  return el("nav", { class: "paginador", "aria-label": "Páginas" },
    botao("Primeira página", 1, icone("primeira")),
    botao("Página anterior", atual - 1, icone("esquerda"), "Anterior"),
    el("span", { text: `Página ${atual} de ${total}` }),
    botao("Próxima página", atual + 1, "Próxima", icone("direita")),
    botao("Última página", total, icone("ultima")));
}
