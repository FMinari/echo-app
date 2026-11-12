// Cartão de uma frase: onde (obra · episódio · título), tempo, personagem, frase com a estrutura
// destacada, cena, contexto (falas vizinhas), ouvir, salvar o áudio, guardar na aula e "Não é essa estrutura".
import { api } from "../lib/ponte.js";
import { el, trocar } from "../lib/dom.js";
import { emitir } from "../lib/eventos.js";
import { destaquesNaFrase } from "../lib/formato.js";
import { vozDoOuvir } from "../lib/voz.js";
import { estado } from "../estado.js";
import { avisar, avisarErro } from "./avisos.js";
import { botaoOuvir } from "./botao-ouvir.js";
import { botaoSalvarAudio } from "./botao-salvar-audio.js";
import { pedirConfirmacao } from "./confirmacao.js";
import { icone } from "./icones.js";
import { mostrarPalavra } from "./palavra.js";
import { recolhivel } from "./recolhivel.js";
import { SEM_FALANTE } from "../lib/tipos.js";

/** A frase com os trechos da estrutura em <mark>. `destaques` = [[início, fim], ...] em caracteres. */
export function fraseDestacada(frase, destaques) {
  const partes = [];
  let pos = 0;
  for (const [a, b] of [...destaquesNaFrase(frase, destaques)].sort((x, y) => x[0] - y[0])) {
    if (a > pos) partes.push(frase.slice(pos, a));
    partes.push(el("mark", { text: frase.slice(a, b) }));
    pos = b;
  }
  partes.push(frase.slice(pos));
  return partes;
}

const fala = (v) => el("li", {}, el("b", { text: `${v.falante || "?"}: ` }), v.texto);

/** "Salvar áudio": a frase num .wav em Músicas › Echo, com a voz e a velocidade do "Ouvir" (aba Sobre). */
const salvarAudioDaFrase = (x) => botaoSalvarAudio({
  classe: "salvar-audio", titulo: "Grava a frase num arquivo de áudio (.wav) em Músicas › Echo",
  gravar: () => {
    const { voz, velocidade } = vozDoOuvir();
    return api("salvar_audio", x, voz, velocidade);
  },
});

/**
 * @param {object} x                 um resultado de busca (ou uma frase guardada numa aula)
 * @param {object} [op]
 * @param {number} [op.estrutura]    id da estrutura buscada: liga o "Não é essa estrutura"
 * @param {number} [op.favorito]     id da frase guardada (na aba Aulas): o botão vira "Tirar da aula"
 * @param {string} [op.textoRemover] texto desse botão
 * @param {() => Promise<void>} [op.remover] o que o botão faz (padrão: apagar a frase guardada)
 * @param {boolean} [op.confirmar]   pede um segundo clique antes (apagar de vez)
 * @param {() => void} [op.aoRemover] depois de tirar
 * @param {Node[]} [op.extras]       no fim do cartão (na aba Aulas: a nota e o "mover")
 */
export function cartaoFrase(x, { estrutura = null, favorito = null, textoRemover = "Tirar da aula", remover = null,
  confirmar = false, aoRemover = () => {}, extras = [] } = {}) {
  const filme = x.tipo === "filme" || x.referencia === "filme";
  const musica = x.tipo === "musica";
  const botaoFavorito = el("button", { type: "button", class: "favoritar" });
  const falso = el("span", { class: "falso" });
  const cartao = el("article", { class: "cartao" },
    el("header", {},
      el("span", { class: "onde" }, el("b", { text: x.obra }),
        (musica ? [x.titulo] : filme ? ["filme"] : [x.referencia, x.titulo]).filter(Boolean).map((p) => ` · ${p}`).join("")),
      x.tempo ? el("span", { class: "tempo", text: x.tempo,
        title: musica ? "Momento do verso na música" : "Momento estimado pela posição da fala no roteiro (pode errar uns 2–3 minutos)" }) : null),
    el("p", { class: "fala" },
      el("span", { class: "quem", text: x.falante || (SEM_FALANTE.has(x.tipo) ? "" : "personagem não identificado") }), " ",
      el("span", { class: "frase", title: "Clique numa palavra para ver o que ela quer dizer", onclick: mostrarPalavra },
        fraseDestacada(x.frase, x.destaques))),
    x.cena ? el("p", { class: "cena", text: x.cena }) : null,
    recolhivel({ titulo: "Contexto", variante: "simples", aberto: false, classe: "contexto" },
      el("ul", {},
        (x.antes || []).map(fala),
        el("li", { class: "esta" }, el("b", { text: `${x.falante || "?"}: ` }), x.frase),
        (x.depois || []).map(fala))),
    el("footer", {}, botaoOuvir(x.frase), salvarAudioDaFrase(x), botaoFavorito, falso),
    extras);

  if (favorito !== null) {
    botaoFavorito.textContent = textoRemover;
    botaoFavorito.onclick = async () => {
      if (confirmar && !pedirConfirmacao(botaoFavorito, textoRemover, "Clique de novo para apagar")) return;
      botaoFavorito.disabled = true;
      try {
        await (remover ? remover() : api("remover_favorito", favorito));
        cartao.remove();
        emitir("frases-mudaram");
        aoRemover();
      } catch (e) {
        avisarErro(e);
        botaoFavorito.disabled = false;
      }
    };
  } else {
    const pintar = () => {
      trocar(botaoFavorito, icone("estrela", { cheio: !!x.favorito }),
        x.favorito ? `Guardada em ${x.aula || "Sem aula"}` : "Guardar");
      botaoFavorito.title = x.favorito ? "Clique para não guardar mais (sai da aula, com a nota)" : "Guarda na aula escolhida em “Guardar frases na aula”";
      botaoFavorito.classList.toggle("ativo", !!x.favorito);
    };
    pintar();
    botaoFavorito.onclick = async () => {
      if (botaoFavorito.disabled) return;
      botaoFavorito.disabled = true; // dois cliques rápidos não guardam e tiram ao mesmo tempo
      try {
        if (x.favorito) {
          await api("desfavoritar", x.arquivo, x.frase);
        } else {
          await api("favoritar", x, estado.aulaDestino);
          x.aula = estado.aulas.find((a) => a.id === estado.aulaDestino)?.nome || null;
        }
        x.favorito = !x.favorito;
        pintar();
        emitir("frases-mudaram");
      } catch (e) {
        avisarErro(e);
      } finally {
        botaoFavorito.disabled = false;
      }
    };
  }

  if (estrutura !== null) {
    const inicial = () => trocar(falso, el("button", { type: "button", text: "Não é essa estrutura", onclick: perguntar }));
    const perguntar = () => trocar(falso, "Tirar esta frase desta estrutura?",
      el("button", { type: "button", class: "confirmar", text: "Sim, não é", onclick: confirmar }),
      el("button", { type: "button", text: "Cancelar", onclick: inicial }));
    async function confirmar() {
      try {
        await api("falso_positivo", estrutura, x);
        cartao.classList.add("removido");
        trocar(falso, "Removida: não aparece mais nesta estrutura.");
      } catch (e) { avisarErro(e); }
    }
    inicial();
  }
  return cartao;
}
