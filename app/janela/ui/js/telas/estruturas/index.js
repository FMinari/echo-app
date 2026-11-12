// Tela Estruturas: lista do catálogo por categoria (com busca), nova estrutura e o formulário.
import { api } from "../../lib/ponte.js";
import { $, el, trocar } from "../../lib/dom.js";
import { emitir, ouvir } from "../../lib/eventos.js";
import { estado, estruturaPorId } from "../../estado.js";
import { recolhivel } from "../../componentes/recolhivel.js";
import { icone } from "../../componentes/icones.js";
import { itemLista } from "../../componentes/item-lista.js";
import { estadoVazio } from "../../componentes/vazio.js";
import { formularioDeEstrutura } from "./formulario.js";

let aberta = null; // id da estrutura no formulário

// categorias abertas na lista: todas começam fechadas a cada vez que o app abre; as que a cliente abre
// ficam abertas enquanto o app estiver aberto (inclusive depois de salvar)
const categoriasAbertas = new Set();


function desenharLista() {
  const filtro = $("#filtro-estruturas").value.trim().toLowerCase();
  const porCategoria = new Map();
  for (const e of estado.estruturas) {
    if (filtro && !`${e.nome} ${e.formula || ""} ${e.categoria || ""}`.toLowerCase().includes(filtro)) continue;
    const c = e.categoria || "Outras";
    if (!porCategoria.has(c)) porCategoria.set(c, []);
    porCategoria.get(c).push(e);
  }
  // procurando, todas abrem (senão o que a cliente procura ficaria escondido) e o clique não conta
  const filhos = [...porCategoria].map(([categoria, itens]) => recolhivel({
    titulo: categoria,
    detalhe: String(itens.length),
    variante: "discreta",
    aberto: !!filtro || categoriasAbertas.has(categoria),
    aoAlternar: (aberto) => {
      if (filtro) return;
      if (aberto) categoriasAbertas.add(categoria);
      else categoriasAbertas.delete(categoria);
    },
  }, ...itens.map((e) => itemLista({
    rotulo: e.nome, detalhe: e.nivel ? el("span", { class: "nivel", text: e.nivel }) : null,
    atual: aberta === e.id, classe: "item-estrutura", aoClicar: () => abrir(e.id),
  }))));
  trocar($("#lista-estruturas"), filhos.length ? filhos : el("p", { class: "ajuda lista-nada", text: "Nenhuma estrutura com esse nome." }));
}

/** Busca o catálogo de novo no Python e avisa as telas (também usado ao guardar uma busca). */
export async function recarregar() {
  estado.estruturas = await api("estruturas");
  emitir("estruturas-mudaram");
}

function semNada() {
  trocar($("#detalhe-estrutura"), estadoVazio("Nenhuma estrutura aberta.", "Escolha uma estrutura à esquerda para ver ou editar."));
}

function abrir(id) {
  aberta = id;
  if (id) categoriasAbertas.add(estruturaPorId(id)?.categoria || "Outras"); // a dela fica à vista
  desenharLista();
  formularioDeEstrutura($("#detalhe-estrutura"), id ? estruturaPorId(id) : {}, {
    aoSalvar: async (salvoId) => { await recarregar(); abrir(salvoId); },
    aoApagar: async () => { aberta = null; await recarregar(); semNada(); },
    aoBuscar: (estruturaId) => emitir("buscar-estrutura", estruturaId),
  });
}

function nova() {
  abrir(null);
}

export function iniciarEstruturas() {
  $("#filtro-estruturas").addEventListener("input", desenharLista);
  $("#nova-estrutura").addEventListener("click", nova);
  $("#nova-estrutura").prepend(icone("mais"));
  semNada();
  ouvir("estruturas-mudaram", desenharLista);
  ouvir("aba-aberta", (aba) => { if (aba === "catalogo") desenharLista(); });
}
