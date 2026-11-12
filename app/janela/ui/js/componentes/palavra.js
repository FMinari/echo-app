// Clicar numa palavra da frase abre um balão com o que ela quer dizer em português (o dicionário do app,
// tirado do Wiktionary). Se a cliente estiver selecionando texto para copiar, não abre.
import { api } from "../lib/ponte.js";
import { el } from "../lib/dom.js";
import { abrirBalao } from "./balao.js";

const LETRA = /[A-Za-z'’-]/;
let pedido = 0;

/** A palavra embaixo do ponto (x, y), ou null. */
function palavraNoPonto(x, y) {
  const r = document.caretRangeFromPoint?.(x, y);
  if (!r || r.startContainer.nodeType !== Node.TEXT_NODE) return null;
  const texto = r.startContainer.textContent;
  let a = r.startOffset;
  let b = r.startOffset;
  while (a > 0 && LETRA.test(texto[a - 1])) a--;
  while (b < texto.length && LETRA.test(texto[b])) b++;
  const palavra = texto.slice(a, b).replace(/^['’-]+|['’-]+$/g, "");
  return /[A-Za-z]/.test(palavra) ? palavra : null;
}

const secoes = (entradas) => entradas.map((e) => el("section", { class: "dic-classe" },
  e.classe ? el("h4", { text: e.classe }) : null,
  el("ol", {}, e.sentidos.slice(0, 4).map((s) => el("li", {},
    el("span", { class: "dic-traducao", text: s.traducoes.join(", ") }),
    s.sentido ? el("small", { text: s.sentido }) : null)))));

function conteudo(r) {
  if (!r.entradas.length) return [el("p", { class: "ajuda", text: "Não achei essa palavra no dicionário." })];
  return [
    ...secoes(r.entradas),
    // a outra forma (saw: "see" primeiro, "saw" depois) ou a outra parte da contração (didn't: do + not)
    ...(r.tambem || []).flatMap((t) => [el("p", { class: "dic-tambem", text: `“${t.lema}”` }), ...secoes(t.entradas)]),
    el("p", { class: "dic-fonte", text: "Fonte: Wiktionary (CC BY-SA 4.0)" }),
  ];
}

/** Para o onclick do texto da frase. */
export async function mostrarPalavra(ev) {
  if (String(getSelection())) return;
  const palavra = palavraNoPonto(ev.clientX, ev.clientY);
  if (!palavra) return;
  const { clientX: x, clientY: y } = ev;
  const meu = ++pedido;
  abrirBalao(x, y, palavra, el("p", { class: "carregando", text: "Procurando…" }));
  try {
    const r = await api("dicionario", palavra);
    if (meu !== pedido || !document.querySelector(".balao")) return; // a cliente já fechou ou clicou em outra
    const titulo = r.lema && r.lema !== palavra.toLowerCase() ? `${palavra} (${r.lema})` : palavra;
    abrirBalao(x, y, titulo, ...conteudo(r));
  } catch (e) {
    if (meu === pedido) abrirBalao(x, y, palavra, el("p", { text: e.message }));
  }
}
