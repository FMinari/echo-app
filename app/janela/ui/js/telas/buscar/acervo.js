// Interruptor "Acervo livre": só aparece quando há um banco próprio (com frases) e o acervo público.
// Ligado, a busca vai nos dois; desligado, só no próprio. A escolha fica guardada (vale ao reabrir).
import { api } from "../../lib/ponte.js";
import { trocar } from "../../lib/dom.js";
import { avisarErro } from "../../componentes/avisos.js";
import { interruptor } from "../../componentes/interruptor.js";

/**
 * @param {HTMLElement} alvo
 * @param {{disponivel: boolean, ligado: boolean}} [acervo]  da api "inicio"
 */
export function interruptorDoAcervo(alvo, acervo) {
  alvo.hidden = !acervo?.disponivel;
  if (alvo.hidden) return;
  const chave = interruptor({
    rotulo: "Acervo livre",
    detalhe: "Buscar também nas obras de domínio público que vêm com o Echo, além dos seus textos",
    ligado: acervo.ligado,
    aoMudar: async (ligado) => {
      alvo.setAttribute("aria-busy", "true");
      chave.querySelector("input").disabled = true;
      try {
        await api("ligar_acervo", ligado);
        location.reload();  // obras, grupos e estruturas passam a vir do outro banco
      } catch (e) {
        chave.ligado = !ligado;
        chave.querySelector("input").disabled = false;
        alvo.removeAttribute("aria-busy");
        avisarErro(e);
      }
    },
  });
  trocar(alvo, chave);
}
