// Tela Buscar: formulário (estrutura do catálogo ou texto escrito, obras, personagem, temporada),
// filtro dos resultados e páginas.
import { api } from "../../lib/ponte.js";
import { $, el, trocar } from "../../lib/dom.js";
import { guardar, lembrar } from "../../lib/armazenamento.js";
import { ouvir } from "../../lib/eventos.js";
import { estado, estruturaPorId, obraPorId } from "../../estado.js";
import { alternador } from "../../componentes/alternador.js";
import { avisar, erroEm } from "../../componentes/avisos.js";
import { digitando } from "../../componentes/digitando.js";
import { esqueletoCartaoFrase, esqueletoResumo } from "../../componentes/esqueleto.js";
import { criarSeletor } from "../../componentes/seletor.js";
import { estadoVazio } from "../../componentes/vazio.js";
import { abrirAba } from "../abas.js";
import { acompanharFichas, escreverTexto, esconderFichas, iniciarLivre, mostrarFichas, paramsLivre, umaPalavra } from "./livre.js";
import { iniciarDestino } from "./destino.js";
import { guardarBusca } from "./guardar.js";
import { escolhaDeObras } from "./obras.js";
import { desenharResultado } from "./resultado.js";

const sel = {};  // seletores do formulário
let obras;       // escolha de séries, filmes e músicas (obras.js)
let modo;        // alternador "Do catálogo" | "Escrever o que procuro"

// a última busca, para andar nas páginas, filtrar e mudar "por página" sem refazer o formulário
const busca = {
  ultima: null,
  paginas: { serie: 1, filme: 1, musica: 1 },
  porPagina: lembrar("por-pagina", 10),
  pedido: 0, // número da busca mais nova: respostas atrasadas de buscas antigas são ignoradas
};

function mostrarExplicacao() {
  const e = estruturaPorId(sel.estrutura.valor);
  trocar($("#sobre-estrutura"), e?.formula ? el("span", { class: "formula", text: e.formula }) : null, e?.explicacao);
}

function preencherEstruturas() {
  const anterior = sel.estrutura.valor ?? lembrar("estrutura", null);
  sel.estrutura.definirItens(estado.estruturas.map((e) => ({
    valor: e.id, rotulo: e.nome, grupo: e.categoria || "Outras",
    secundario: [e.nivel, e.formula].filter(Boolean).join(" · "),
  })));
  sel.estrutura.valor = estruturaPorId(anterior) ? anterior : null;
  mostrarExplicacao();
}

// temporada só faz sentido com uma série só; os personagens dependem das obras
async function obrasMudaram(ids) {
  const escolhidas = ids.map(obraPorId);
  const umaSerie = escolhidas.length === 1 && escolhidas[0].tipo === "serie";
  const temporadas = [];
  if (umaSerie) {
    for (let t = escolhidas[0].primeira_temporada; t <= escolhidas[0].ultima_temporada; t++) {
      temporadas.push({ valor: t, rotulo: `Temporada ${t}` });
    }
  }
  sel.temporada.definirItens(temporadas);
  sel.temporada.desabilitar(!umaSerie);
  try {
    // valor = "obra|nome": escolher o personagem também fixa a obra dele (há nomes repetidos entre séries)
    const falantes = await api("falantes", ids);
    sel.falante.definirItens(falantes.map((f) => ({
      valor: `${f.obra_id}|${f.falante}`, rotulo: f.falante, grupo: f.obra,
      resumo: `${f.falante} · ${f.obra}`, secundario: `${f.falas} falas`,
    })));
  } catch { /* a lista de personagens é só ajuda */ }
}

function mostrarModo(valor) {
  $("#modo-catalogo").hidden = valor !== "catalogo";
  $("#modo-escrever").hidden = valor !== "escrever";
  if (valor === "catalogo") esconderFichas();
}

function paramsDoFormulario() {
  const [obraDoFalante, falante] = sel.falante.valor ? String(sel.falante.valor).split(/\|(.*)/s) : [null, ""];
  return {
    ...(modo.valor === "escrever" ? paramsLivre() : { estrutura: sel.estrutura.valor }),
    obras: obraDoFalante ? [Number(obraDoFalante)] : obras.ids(),
    falante,
    temporada: sel.temporada.valor,
  };
}

const nomeDaBusca = (p) => (p.texto ? `“${p.texto}”` : estruturaPorId(p.estrutura)?.nome || "estrutura");

/**
 * Um verbo sozinho no modo escrever: lista os phrasal verbs dele em fichas, em vez de trazer todas as
 * frases com o verbo (milhares, e lento). Devolve se mostrou as fichas.
 */
async function fichasDoVerbo(alvo, params, pedido) {
  trocar(alvo, digitando(`Procurando os phrasal verbs de ${params.texto}…`));
  alvo.setAttribute("aria-busy", "true");
  try {
    const lista = await api("phrasal_verbs", params);
    if (pedido !== busca.pedido || !lista.length) return pedido !== busca.pedido;
    mostrarFichas(params.texto, lista, (texto) => { escreverTexto(texto); buscar("nova", null, { daFicha: true }); });
    $("#filtro-resultados").hidden = true;
    busca.ultima = null;
    trocar(alvo, estadoVazio(`Escolha um phrasal verb acima para ver as frases.`, null),
      el("div", { class: "botoes centro" },
        el("button", { type: "button", class: "btn-link", text: `Ou ver todas as frases com ${params.texto}`,
          onclick: () => buscar("nova", null, { todas: true }) })));
    return true;
  } finally {
    if (pedido === busca.pedido) alvo.removeAttribute("aria-busy");
  }
}

/**
 * tipo: "nova" (botão Buscar), "filtro" (digitou no filtro), "pagina" (andou numa seção) ou
 * "por-pagina" (mudou quantas por página). Fora "pagina", tudo volta para a página 1.
 * opcoes.daFicha: veio de uma ficha de phrasal verb; opcoes.todas: o verbo sozinho, sem fichas.
 */
async function buscar(tipo = "nova", secaoAlvo = null, opcoes = {}) {
  const alvo = $("#resultado");
  if (tipo === "nova") {
    const params = paramsDoFormulario();
    if (params.texto !== undefined) {
      if (!params.texto) return avisar("Escreva o que quer procurar.");
      if (umaPalavra(params.texto) && !opcoes.daFicha && !opcoes.todas
          && await fichasDoVerbo(alvo, params, ++busca.pedido)) return;
      acompanharFichas(params.texto);
    } else {
      if (!params.estrutura) return avisar("Escolha uma estrutura primeiro.");
      guardar("estrutura", params.estrutura);
    }
    busca.ultima = params;
    $("#f-filtro").value = ""; // busca nova começa sem filtro
  } else if (!busca.ultima) return;
  if (tipo !== "pagina") busca.paginas = { serie: 1, filme: 1, musica: 1 };
  busca.ultima.filtro = $("#f-filtro").value.trim();
  const pedido = ++busca.pedido;
  if (tipo === "nova") {
    trocar(alvo,
      digitando(busca.ultima.texto !== undefined ? "Procurando nas falas…"
        : "Procurando nas falas… (na primeira busca de cada estrutura pode levar alguns segundos)"),
      esqueletoResumo(), esqueletoCartaoFrase(), esqueletoCartaoFrase(), esqueletoCartaoFrase());
  } else {
    alvo.classList.add("atualizando");
  }
  alvo.setAttribute("aria-busy", "true");
  try {
    const r = await api("buscar", { ...busca.ultima, pagina: busca.paginas, por_pagina: busca.porPagina });
    if (pedido !== busca.pedido) return;
    busca.paginas = { ...busca.paginas, ...r.pagina };
    if (tipo === "nova" && busca.ultima.tempo && r.livre && !r.livre.verbo) {
      avisar("O tempo do verbo ficou de fora: não achei verbo no que você escreveu.");
    }
    desenharResultado(alvo, r, {
      nomeEstrutura: nomeDaBusca(busca.ultima),
      estruturaId: busca.ultima.estrutura ?? null,
      significado: r.livre?.significado || null,
      acao: busca.ultima.texto !== undefined
        ? guardarBusca({ texto: busca.ultima.texto, outras_formas: busca.ultima.outras_formas, tempo: busca.ultima.tempo })
        : null,
      filtro: busca.ultima.filtro,
      comPersonagem: !!busca.ultima.falante,
      porPagina: busca.porPagina,
      aoMudarPorPagina: (n) => { busca.porPagina = n; guardar("por-pagina", n); buscar("por-pagina"); },
      aoIrPagina: (tipo, n) => { busca.paginas[tipo] = n; buscar("pagina", tipo); },
    });
    $("#filtro-resultados").hidden = !r.total_sem_filtro;
    if (secaoAlvo) $(`.secao-tipo[data-tipo="${secaoAlvo}"]`)?.scrollIntoView({ block: "start", behavior: "smooth" });
  } catch (e) {
    if (pedido === busca.pedido) erroEm(alvo, e);
  } finally {
    if (pedido === busca.pedido) {
      alvo.removeAttribute("aria-busy");
      alvo.classList.remove("atualizando");
    }
  }
}

/** "Buscar exemplos" no catálogo: escolhe a estrutura, abre a aba e busca. */
function buscarEstrutura(id) {
  modo.valor = "catalogo";
  guardar("modo-busca", "catalogo");
  mostrarModo("catalogo");
  sel.estrutura.valor = id;
  mostrarExplicacao();
  abrirAba("buscar");
  buscar();
}

export function iniciarBusca() {
  modo = alternador({
    opcoes: [{ valor: "catalogo", rotulo: "Do catálogo" }, { valor: "escrever", rotulo: "Escrever" }],
    valor: lembrar("modo-busca", "catalogo"), rotulo: "Como buscar",
    aoMudar: (v) => { guardar("modo-busca", v); mostrarModo(v); if (v === "escrever") $("#f-texto").focus(); },
  });
  trocar($("#f-modo"), modo);
  mostrarModo(modo.valor);
  iniciarLivre();
  iniciarDestino();
  sel.estrutura = criarSeletor($("#f-estrutura"), {
    placeholder: "Escolha uma estrutura", busca: "Procurar estrutura…", vazio: "Nenhuma estrutura com esse nome",
    aoMudar: (v) => { guardar("estrutura", v); mostrarExplicacao(); },
  });
  sel.falante = criarSeletor($("#f-falante"), { busca: "Procurar personagem…", vazio: "Ninguém com esse nome", todos: "Qualquer personagem" });
  sel.temporada = criarSeletor($("#f-temporada"), { busca: "Procurar…", vazio: "Nenhuma", todos: "Todas" });
  obras = escolhaDeObras($("#f-obras"), $("#salvar-grupo"), { aoMudar: obrasMudaram });

  $("#form-busca").addEventListener("submit", (ev) => { ev.preventDefault(); buscar(); });
  let espera;
  $("#f-filtro").addEventListener("input", () => {
    clearTimeout(espera);
    espera = setTimeout(() => buscar("filtro"), 300);
  });
  ouvir("estruturas-mudaram", preencherEstruturas);
  // tirou ou moveu frase na aba Aulas: ao voltar, os cartões mostram de novo se estão guardados e onde
  let frasesMudaram = false;
  ouvir("frases-mudaram", () => { frasesMudaram = true; });
  ouvir("aba-aberta", (aba) => {
    if (aba === "buscar" && frasesMudaram && busca.ultima) buscar("pagina");
    if (aba === "buscar") frasesMudaram = false;
  });
  ouvir("buscar-estrutura", buscarEstrutura);
}

/** Depois que estado.obras/grupos chegam do Python. */
export function preencherObras() {
  obras.preencher();
}
