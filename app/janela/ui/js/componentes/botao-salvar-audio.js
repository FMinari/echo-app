// "Salvar áudio": grava num arquivo em Músicas › Echo (nucleo/audio.py) e avisa onde ficou, com "Mostrar na pasta".
// No cartão da frase (.wav) e na Text to Audio (.mp3, que vira .wav quando o MP3 não sai neste computador).
import { api } from "../lib/ponte.js";
import { el, trocar } from "../lib/dom.js";
import { avisar, avisarErro } from "./avisos.js";
import { icone } from "./icones.js";

/**
 * @param {object} op
 * @param {string} op.classe                        classe do botão
 * @param {string} op.titulo                        dica do botão
 * @param {() => Promise<object>} op.gravar         chama a api e devolve a resposta dela ({arquivo, nome, voz,
 *                                                  outra_voz, sem_mp3?})
 * @param {() => boolean} [op.antes]                false = não grava (quem chamou já avisou por quê)
 */
export function botaoSalvarAudio({ classe, titulo, gravar, antes = () => true }) {
  const botao = el("button", { type: "button", class: classe, title: titulo });
  const pintar = (texto) => trocar(botao, icone("baixar"), texto);
  botao.addEventListener("click", async () => {
    if (botao.disabled || !antes()) return;
    botao.disabled = true;
    pintar("Gravando…");
    try {
      const r = await gravar();
      const wav = r.sem_mp3 ? " O MP3 não saiu neste computador, então salvei em WAV (toca do mesmo jeito)." : "";
      const outra = r.outra_voz ? ` Gravei com a voz ${r.voz}: a voz do “Ouvir” não dá para gravar (as “Online” só tocam).` : "";
      avisar(`Áudio salvo em Músicas › Echo: ${r.nome}.${wav}${outra}`,
        el("button", { type: "button", class: "btn btn-contorno", text: "Mostrar na pasta",
          onclick: () => api("mostrar_audio", r.arquivo).catch(avisarErro) }), 12000);
    } catch (e) {
      avisarErro(e);
    } finally {
      botao.disabled = false;
      pintar("Salvar áudio");
    }
  });
  pintar("Salvar áudio");
  return botao;
}
