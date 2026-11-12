// "Ouvir": lê o texto com a voz escolhida na aba Sobre; tocando, vira "Parar". No cartão da frase e na aba Textos.
import { el, trocar } from "../lib/dom.js";
import { esperarVozes, falar, parar, pedacos, vozesEmIngles } from "../lib/voz.js";
import { avisar } from "./avisos.js";
import { icone } from "./icones.js";

/**
 * @param {string | (() => string)} texto   o texto, ou quem o dá na hora do clique (texto que a cliente edita)
 * @param {object} [op]
 * @param {string} [op.classe]              classe do botão
 * @param {string} [op.vazio]               aviso quando não há o que ler
 * @param {() => object} [op.ajustes]       voz, velocidade, tom e volume desta leitura (ver falar, em lib/voz.js)
 * @param {() => string} [op.rotulo]        o texto do botão parado ("Ouvir", "Ouvir trecho")
 * @returns {HTMLButtonElement & {repintar: () => void}}  repintar: o rótulo mudou (ex.: a cliente selecionou um trecho)
 */
export function botaoOuvir(texto, { classe = "ouvir", vazio = "Não há o que ler.", ajustes = () => ({}), rotulo = () => "Ouvir" } = {}) {
  const ler = typeof texto === "function" ? texto : () => texto;
  const botao = el("button", { type: "button", class: classe });
  const pintar = (tocando) => {
    trocar(botao, icone(tocando ? "parar" : "som"), tocando ? "Parar" : rotulo());
    botao.dataset.tocando = tocando ? "1" : "";
  };
  botao.repintar = () => { if (!botao.dataset.tocando) pintar(false); };
  botao.addEventListener("click", async () => {
    if (botao.dataset.tocando) { parar(); pintar(false); return; }
    const agora = ler();
    if (!agora.trim()) { avisar(vazio); return; }
    if (!pedacos(agora).length) { avisar("Esse trecho não tem palavras para ler."); return; }
    if (!vozesEmIngles().length) await esperarVozes(); // logo depois de abrir, o Edge ainda não listou as vozes
    pintar(true); // antes de falar: se a leitura acabar na hora, o fim dela é que volta o botão para "Ouvir"
    if (!falar(agora, () => pintar(false), ajustes())) {
      pintar(false);
      avisar("Este computador não tem voz em inglês. Veja como pôr uma na aba Sobre, em “Voz das frases”.");
    }
  });
  pintar(false);
  return botao;
}
