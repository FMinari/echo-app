// Mensagem de "não tem nada aqui" (sem resultado, sem favoritos, nada escolhido): título e uma dica
// do que fazer, numa caixa tracejada.
import { el } from "../lib/dom.js";

/**
 * @param {string} titulo   o que aconteceu ("Nenhuma frase encontrada.")
 * @param {string} [dica]   o que dá para fazer ("Tente outras séries…")
 */
export function estadoVazio(titulo, dica = null) {
  return el("div", { class: "vazio" },
    el("p", { class: "vazio-titulo", text: titulo }),
    dica ? el("p", { text: dica }) : null);
}
