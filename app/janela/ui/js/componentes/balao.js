// Balão que abre ao lado de um ponto da tela (ex.: a palavra clicada) e fecha ao clicar fora, apertar
// Esc ou rolar a página (rolar dentro dele não fecha). Só um aberto por vez.
import { el } from "../lib/dom.js";
import { icone } from "./icones.js";

let aberto = null;

export function fecharBalao() {
  aberto?.remove();
  aberto = null;
}

addEventListener("mousedown", (ev) => { if (aberto && !aberto.contains(ev.target)) fecharBalao(); });
addEventListener("keydown", (ev) => { if (ev.key === "Escape") fecharBalao(); });
addEventListener("scroll", (ev) => { if (aberto && !aberto.contains(ev.target)) fecharBalao(); }, { passive: true, capture: true });

/**
 * @param {number} x        posição do clique (clientX)
 * @param {number} y        posição do clique (clientY)
 * @param {string} titulo
 * @param {...Node} conteudo
 */
export function abrirBalao(x, y, titulo, ...conteudo) {
  fecharBalao();
  aberto = el("div", { class: "balao", role: "dialog", "aria-label": titulo },
    el("header", {}, el("b", { text: titulo }),
      el("button", { type: "button", class: "btn-icone", "aria-label": "Fechar", onclick: fecharBalao }, icone("fechar"))),
    el("div", { class: "balao-corpo" }, ...conteudo));
  document.body.append(aberto);
  // abaixo do clique; se não couber, acima. Nunca para fora da janela.
  const r = aberto.getBoundingClientRect();
  const esquerda = Math.min(Math.max(8, x - 24), innerWidth - r.width - 8);
  const topo = y + 14 + r.height > innerHeight - 8 ? Math.max(8, y - r.height - 10) : y + 14;
  Object.assign(aberto.style, { left: `${esquerda}px`, top: `${topo}px` });
}
