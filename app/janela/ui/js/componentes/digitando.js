// "Digitando…": um balão de fala com três pontos pulando em sequência, em loop, enquanto o app procura
// nas falas. Combina com o app (falas, balão do ícone) e diz que algo está acontecendo sem prometer
// tempo. Com "reduzir animação" no sistema, os pontos ficam parados (ver componentes/digitando.css).
import { el } from "../lib/dom.js";

/** @param {string} texto  o que está acontecendo ("Procurando nas falas…") */
export function digitando(texto) {
  return el("div", { class: "digitando", role: "status" },
    el("span", { class: "balao-digitando", "aria-hidden": "true" },
      el("span", { class: "ponto" }), el("span", { class: "ponto" }), el("span", { class: "ponto" })),
    el("span", { text: texto }));
}
