// Aviso de progresso no canto ("Procurando atualizações…", com uma rodinha): fica até a tarefa terminar e
// então mostra o resultado por um instante, ou some. Separado do aviso rápido (avisos.js), para um não
// apagar o outro.
import { el, trocar } from "../lib/dom.js";

let caixa = null;
let temporizador;

function garantirCaixa() {
  if (!caixa) {
    caixa = el("div", { class: "progresso", role: "status", "aria-live": "polite", hidden: true });
    document.body.append(caixa);
  }
  return caixa;
}

/**
 * Mostra `texto` com a rodinha até `terminar` ou `fechar`.
 * @returns {{terminar: (resultado?: string, ms?: number) => void, fechar: () => void}}
 */
export function mostrarProgresso(texto) {
  const c = garantirCaixa();
  clearTimeout(temporizador);
  trocar(c, el("span", { class: "progresso-roda", "aria-hidden": "true" }), el("span", { text: texto }));
  c.hidden = false;
  const fechar = () => { clearTimeout(temporizador); c.hidden = true; };
  return {
    /** Troca a rodinha pelo resultado e some depois de `ms`; sem resultado, some na hora. */
    terminar(resultado = null, ms = 2500) {
      if (!resultado) return fechar();
      trocar(c, el("span", { text: resultado }));
      clearTimeout(temporizador);
      temporizador = setTimeout(fechar, ms);
    },
    fechar,
  };
}
