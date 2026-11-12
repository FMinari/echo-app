// Bloco que recolhe e expande (<details>): seta desenhada, título, um detalhe (contagem) e, se quiser,
// um marcador de cor. Variações: "destaque" (barra cinza, título grande: Séries/Filmes no resultado),
// "discreta" (rótulo pequeno em caixa alta: categorias da lista de estruturas) e "simples" (seta + texto:
// Contexto do cartão, Regra avançada).
import { el } from "../lib/dom.js";
import { icone } from "./icones.js";

/**
 * @param {object} op
 * @param {string} op.titulo
 * @param {string} [op.detalhe]       texto ao lado do título (ex.: "118 frases · página 2 de 12")
 * @param {string} [op.marcador]      cor de um quadradinho antes do título (CSS)
 * @param {"destaque"|"discreta"|"simples"} [op.variante]
 * @param {boolean} [op.aberto]
 * @param {(aberto: boolean) => void} [op.aoAlternar]  quando a cliente abre ou fecha
 * @param {string} [op.classe]        classes a mais (ex.: para achar o bloco depois)
 * @param {object} [op.atributos]     atributos a mais (ex.: { "data-tipo": "serie" })
 * @param {...Node} conteudo
 */
export function recolhivel({ titulo, detalhe = null, marcador = null, variante = "destaque", aberto = true, aoAlternar = () => {}, classe = "", atributos = {} }, ...conteudo) {
  const bloco = el("details", { ...atributos, class: `recolhivel recolhivel-${variante} ${classe}`.trim(), open: aberto },
    el("summary", {},
      el("span", { class: "recolhivel-seta" }, icone("baixo")),
      marcador ? el("i", { class: "recolhivel-marcador", style: `background:${marcador}` }) : null,
      el("span", { class: "recolhivel-titulo", text: titulo }),
      detalhe ? el("span", { class: "recolhivel-detalhe", text: detalhe }) : null),
    el("div", { class: "recolhivel-corpo" }, ...conteudo));
  bloco.addEventListener("toggle", () => aoAlternar(bloco.open));
  return bloco;
}
