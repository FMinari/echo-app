// Skeleton: silhuetas no formato do conteúdo que vai chegar, para a tela não pular quando ele chega.
// Um retângulo genérico no meio da tela seria só um spinner quadrado; por isso cada formato aqui imita
// um componente de verdade (cartão de frase, resumo da busca, cartão do Sobre).
import { el } from "../lib/dom.js";

/** Uma barra cinza. `largura`/`altura` em CSS ("60%", "14px"). */
export const barra = (largura = "100%", altura = "12px") =>
  el("span", { class: "esqueleto", style: `width:${largura};height:${altura}` });

/** Texto escondido para leitor de tela: a silhueta em si é aria-hidden. */
const aviso = (texto) => el("span", { class: "so-leitor", text: texto });

/** Silhueta de um cartão de frase (componentes/cartao-frase.js). */
export function esqueletoCartaoFrase() {
  return el("article", { class: "cartao cartao-esqueleto", "aria-hidden": "true" },
    el("header", {}, barra("42%"), barra("44px")),
    el("div", { class: "esqueleto-linhas esqueleto-fala" }, barra("96%", "17px"), barra("68%", "17px")),
    barra("38%", "10px"),
    el("footer", {}, barra("64px", "10px"), barra("120px", "10px")));
}

/** Silhueta do resumo da busca (título, quem mais usa, por página). */
export function esqueletoResumo() {
  return el("div", { class: "resumo esqueleto-linhas", "aria-hidden": "true" }, barra("46%", "22px"), barra("62%"), barra("150px"));
}

/** Silhueta de um cartão do Sobre com `linhas` linhas de rótulo + valor. */
export function esqueletoCartaoSobre(linhas = 3) {
  return el("section", { class: "cartao-sobre", "aria-hidden": "true" },
    el("div", { class: "esqueleto-linhas" },
      barra("28%", "18px"),
      Array.from({ length: linhas }, (_, i) => el("div", { class: "esqueleto-par" }, barra("140px"), barra(`${70 - i * 12}%`)))));
}

/** Algumas linhas de texto (ex.: a amostra do Testar). */
export function esqueletoLinhas(larguras = ["92%", "80%", "86%"], classe = "") {
  return el("div", { class: `esqueleto-linhas ${classe}`.trim(), "aria-hidden": "true" }, larguras.map((l) => barra(l, "14px")));
}

/** Monta o conteúdo de carregamento: as silhuetas + o aviso para leitor de tela. */
export function carregando(texto, ...silhuetas) {
  return [aviso(texto), ...silhuetas];
}
