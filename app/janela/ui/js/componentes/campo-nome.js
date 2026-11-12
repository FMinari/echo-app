// Um link ("Nova aula", "Salvar como grupo", "Renomear") que vira um campo de nome com Salvar e Cancelar.
// Enter salva, Esc cancela. Se `aoSalvar` der erro, o campo continua aberto para a cliente corrigir.
import { el, trocar } from "../lib/dom.js";
import { avisarErro } from "./avisos.js";

/**
 * @param {object} op
 * @param {string} op.rotulo                 texto do link ("Nova aula")
 * @param {string} op.placeholder            dica dentro do campo ("Nome da aula")
 * @param {string} [op.valor]                nome que já vem escrito (para renomear)
 * @param {string} [op.salvar]               texto do botão ("Criar", "Salvar")
 * @param {string} [op.classe]               classe do link (padrão: btn-link)
 * @param {(nome: string) => Promise<void>} op.aoSalvar
 * @returns {HTMLElement & {fechar: () => void}}
 */
export function campoNome({ rotulo, placeholder, valor = "", salvar = "Salvar", classe = "btn-link", aoSalvar }) {
  const caixa = el("div", { class: "campo-nome" });

  function fechar() {
    trocar(caixa, el("button", { type: "button", class: classe, text: rotulo, onclick: abrir }));
  }

  function abrir() {
    const nome = el("input", { type: "text", placeholder, "aria-label": placeholder, maxlength: "80", value: valor });
    const botao = el("button", { type: "button", class: "btn btn-pequeno btn-primario", text: salvar });
    async function confirmar() {
      if (botao.disabled) return;
      botao.disabled = true;
      try {
        await aoSalvar(nome.value);
        fechar();
      } catch (e) {
        avisarErro(e);
        botao.disabled = false;
        nome.focus();
      }
    }
    botao.addEventListener("click", confirmar);
    nome.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") { ev.preventDefault(); confirmar(); }
      else if (ev.key === "Escape") fechar();
    });
    trocar(caixa, nome, botao, el("button", { type: "button", class: "btn btn-pequeno", text: "Cancelar", onclick: fechar }));
    nome.focus();
    nome.select();
  }

  fechar();
  caixa.fechar = fechar;
  return caixa;
}
