// O topo tem as três partes do app (Frases, Aulas, Text to Audio) e o botão Sobre; Frases tem duas sub-abas,
// Buscar e Estruturas, e volta para a última usada. Cada tela ouve "aba-aberta" para se atualizar.
import { $, $$ } from "../lib/dom.js";
import { emitir } from "../lib/eventos.js";

const PARTE = { buscar: "frases", catalogo: "frases", aulas: "aulas", textos: "textos", sobre: null };
let ultimaDeFrases = "buscar";

/** Abre uma tela: buscar, catalogo, aulas, textos ou sobre. */
export function abrirAba(nome) {
  const parte = PARTE[nome];
  if (parte === "frases") ultimaDeFrases = nome;
  for (const b of $$("[data-parte]")) b.setAttribute("aria-selected", String(b.dataset.parte === parte));
  for (const b of $$("#sub-frases [data-aba]")) b.setAttribute("aria-selected", String(b.dataset.aba === nome));
  $(".btn-sobre").setAttribute("aria-pressed", String(nome === "sobre"));
  $("#sub-frases").hidden = parte !== "frases";
  for (const s of $$(".aba")) s.hidden = s.id !== `aba-${nome}`;
  emitir("aba-aberta", nome);
}

export function iniciarAbas() {
  for (const b of $$("[data-parte]")) {
    b.addEventListener("click", () => abrirAba(b.dataset.parte === "frases" ? ultimaDeFrases : b.dataset.parte));
  }
  for (const b of $$("[data-aba]")) b.addEventListener("click", () => abrirAba(b.dataset.aba));
}
