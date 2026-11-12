// Tema: "auto" segue o sistema; "claro" e "escuro" ficam fixos. O <head> do index.html aplica o tema
// salvo antes de desenhar (para a janela não piscar); aqui ficam os botões.
import { $$ } from "../lib/dom.js";
import { guardar, lembrar } from "../lib/armazenamento.js";

function aplicarTema(tema) {
  if (tema === "claro" || tema === "escuro") document.documentElement.dataset.tema = tema;
  else delete document.documentElement.dataset.tema;
  for (const b of $$(".tema button")) b.setAttribute("aria-checked", String(b.dataset.tema === tema));
  guardar("tema", tema);
}

export function iniciarTema() {
  for (const b of $$(".tema button")) b.addEventListener("click", () => aplicarTema(b.dataset.tema));
  aplicarTema(lembrar("tema", "auto"));
}
