// Erros do JavaScript também vão para o log do app (pela ponte), no máximo 20 por sessão, e a cliente vê um
// aviso na primeira vez.
import { avisarErro } from "../componentes/avisos.js";
import { api } from "./ponte.js";

const LIMITE = 20;
let quantos = 0;

function registrar(mensagem, pilha) {
  if (++quantos > LIMITE) return;
  api("registrar_erro_js", { mensagem: String(mensagem), pilha: String(pilha || "") }).catch(() => {});
  if (quantos === 1) {
    avisarErro({ message: "Algo deu errado na tela. Os detalhes foram para a pasta de erros.", inesperado: true });
  }
}

export function vigiarErros() {
  window.addEventListener("error", (ev) =>
    registrar(ev.message, ev.error?.stack || `${ev.filename}:${ev.lineno}:${ev.colno}`));
  window.addEventListener("unhandledrejection", (ev) =>
    registrar(ev.reason?.message || ev.reason, ev.reason?.stack));
}
