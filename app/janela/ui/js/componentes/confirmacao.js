// Confirmação no próprio botão: o primeiro clique troca o texto ("Apagar" → "Apagar?") e o segundo,
// em até 3 s, confirma. Sem janelas de diálogo do navegador (confirm), que travam a tela.
import { el } from "../lib/dom.js";

const PRAZO_MS = 3000;
const MINIMO_MS = 400; // o segundo clique de um duplo clique não vale como confirmação

/**
 * Para usar no clique de um botão que já existe. Devolve true quando é o clique que confirma.
 * @param {HTMLButtonElement} botao
 * @param {string} texto     texto normal
 * @param {string} pergunta  texto enquanto espera a confirmação
 */
export function pedirConfirmacao(botao, texto, pergunta = `${texto}?`) {
  if (botao.dataset.confirmar === "1") {
    if (Date.now() - Number(botao.dataset.desde) < MINIMO_MS) return false;
    clearTimeout(Number(botao.dataset.temporizador));
    botao.dataset.confirmar = "";
    botao.textContent = texto;
    return true;
  }
  botao.dataset.confirmar = "1";
  botao.dataset.desde = String(Date.now());
  botao.textContent = pergunta;
  botao.dataset.temporizador = String(setTimeout(() => {
    botao.dataset.confirmar = "";
    botao.textContent = texto;
  }, PRAZO_MS));
  return false;
}

/** Botão pronto com confirmação. `aoConfirmar` roda só no segundo clique. */
export function botaoConfirmar({ texto, pergunta = `${texto}?`, class: classe = "btn", titulo, aoConfirmar }) {
  return el("button", {
    type: "button", class: classe, text: texto, title: titulo,
    onclick: (ev) => {
      ev.stopPropagation();
      if (pedirConfirmacao(ev.currentTarget, texto, pergunta)) aoConfirmar();
    },
  });
}
