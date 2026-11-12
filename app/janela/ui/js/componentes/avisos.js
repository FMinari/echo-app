// Avisos: o rápido no rodapé (toast) e o erro dentro de uma área da tela.
import { $, el, trocar } from "../lib/dom.js";
import { api } from "../lib/ponte.js";

let temporizador;

/** Aviso rápido no rodapé; `extra` é um elemento ao lado do texto (ex.: um botão). */
export function avisar(texto, extra = null, ms = 3200) {
  const toast = $("#toast");
  trocar(toast, texto, extra);
  toast.hidden = false;
  clearTimeout(temporizador);
  temporizador = setTimeout(() => { toast.hidden = true; }, ms);
}

export function botaoPastaErros() {
  return el("button", {
    type: "button", class: "btn btn-contorno", text: "Abrir pasta de erros",
    onclick: async () => {
      try {
        await api("abrir_pasta_erros");
      } catch {
        avisar("Não consegui abrir. A pasta é %APPDATA%\\FrasesSeries\\erros");
      }
    },
  });
}

const textoDoErro = (e) => (e.daApi ? e.message : `Algo deu errado: ${e.message}`);

/** Erro num aviso rápido; o inesperado fica mais tempo e com o botão da pasta de erros. */
export function avisarErro(e) {
  if (e.inesperado) avisar(e.message, botaoPastaErros(), 10000);
  else avisar(textoDoErro(e));
}

/** Erro no lugar de um conteúdo (resultado, amostra…). */
export function erroEm(alvo, e) {
  trocar(alvo, el("div", { class: "erro" },
    el("p", { text: textoDoErro(e) }),
    e.inesperado ? botaoPastaErros() : null));
}
