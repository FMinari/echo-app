// Controle deslizante com o nome em cima e o valor escrito ao lado ("0,75×", "+20%"). A tela Text to Audio usa
// para a velocidade, o tom e o volume da leitura.
import { el } from "../lib/dom.js";

/**
 * @param {object} op
 * @param {string} op.rotulo                  "Velocidade"
 * @param {string} op.nome                    name do campo
 * @param {number} op.min
 * @param {number} op.max
 * @param {number} op.passo
 * @param {number} op.valor
 * @param {(valor: number) => string} op.formatar   o texto ao lado do nome
 * @param {(valor: number) => void} op.aoMudar
 */
export function deslizante({ rotulo, nome, min, max, passo, valor, formatar, aoMudar }) {
  const saida = el("output", { class: "deslizante-valor" });
  const campo = el("input", { type: "range", name: nome, min, max, step: passo, "aria-label": rotulo });
  campo.value = String(valor);
  const pintar = () => { saida.textContent = formatar(Number(campo.value)); };
  campo.addEventListener("input", () => {
    pintar();
    aoMudar(Number(campo.value));
  });
  pintar();
  return el("label", { class: "campo deslizante" }, el("span", {}, rotulo, saida), campo);
}
