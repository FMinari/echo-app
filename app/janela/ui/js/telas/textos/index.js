// Tela Text to Audio: os textos da cliente à esquerda (com filtro por aula); o texto aberto à direita, com título,
// aula, o texto em inglês, a voz da leitura (voz, velocidade, tom e volume), Ouvir e "Salvar áudio" (um .mp3 em
// Músicas › Echo, nucleo/audio.py). A voz da leitura vale só enquanto o app está aberto (não vai para o
// banco) e começa pela da aba Sobre. Mudança sem salvar no texto não se perde: trocar de texto ou de aba salva sozinho.
import { api } from "../../lib/ponte.js";
import { $, el, trocar } from "../../lib/dom.js";
import { plural } from "../../lib/formato.js";
import { emitir, ouvir } from "../../lib/eventos.js";
import { esperarVozes, paraLer, taxaEscolhida, vozDoOuvir } from "../../lib/voz.js";
import { estado } from "../../estado.js";
import { avisar, avisarErro, erroEm } from "../../componentes/avisos.js";
import { botaoOuvir } from "../../componentes/botao-ouvir.js";
import { botaoSalvarAudio } from "../../componentes/botao-salvar-audio.js";
import { botaoConfirmar } from "../../componentes/confirmacao.js";
import { deslizante } from "../../componentes/deslizante.js";
import { carregando, esqueletoLinhas } from "../../componentes/esqueleto.js";
import { itemLista } from "../../componentes/item-lista.js";
import { criarSeletor } from "../../componentes/seletor.js";
import { estadoVazio } from "../../componentes/vazio.js";
import { abrirAba } from "../abas.js";
import { recarregarAulas } from "../aulas/dados.js";

const SEM_AULA = "sem";
let lista = [];      // os textos, sem o corpo (api "textos")
let filtro = null;   // null = todas as aulas; SEM_AULA; ou o id da aula
let form = null;     // o texto aberto: { id (null = novo), titulo, corpo, aula (seletor), original }
let pedido = null;   // o que abrir quando a aba abrir: { id } ou { novo: aulaId } (vem da tela da aula)
let seletorFiltro;
let ajustes = null;  // a voz da leitura: { voz, taxa, tom, volume }; null = ainda não montada (vem da aba Sobre)

const itensDeAula = () => [
  ...estado.aulas.map((a) => ({ valor: a.id, rotulo: a.nome })),
  { valor: SEM_AULA, rotulo: "Sem aula" },
];
const aulaDoValor = (v) => (v === null || v === SEM_AULA ? null : Number(v));

function valores(f = form) {
  return { titulo: f.titulo.value, corpo: f.corpo.value, aula_id: aulaDoValor(f.aula.valor) };
}
const retrato = () => JSON.stringify(valores());
const mudou = () => form !== null && retrato() !== form.original;

function desenharLista() {
  const visiveis = lista.filter((t) => filtro === null
    || (filtro === SEM_AULA ? t.aula_id === null : t.aula_id === filtro));
  trocar($("#lista-textos"), visiveis.length
    ? visiveis.map((t) => itemLista({
      rotulo: t.titulo, detalhe: filtro === null ? t.aula || "Sem aula" : "", atual: form?.id === t.id,
      classe: "item-texto", aoClicar: () => abrir({ id: t.id }),
    }))
    : el("p", { class: "ajuda lista-nada", text: lista.length ? "Nenhum texto nesta aula." : "Nenhum texto ainda." }));
}

async function recarregarLista() {
  lista = await api("textos");
  desenharLista();
}

// Um salvamento por vez: o que sai ao trocar de tela não é esperado por ninguém, e um segundo (Salvar, Salvar
// áudio, trocar de texto) que começasse antes de ele voltar ainda veria o texto novo sem id e o criaria de novo.
let fila = Promise.resolve();

function salvar(op) {
  const alvo = form; // o texto aberto quando a cliente pediu
  const vez = fila.then(() => salvarAgora(alvo, op));
  fila = vez.catch(() => {});
  return vez;
}

async function salvarAgora(alvo, { calado = false } = {}) {
  const dados = { id: alvo.id, ...valores(alvo) };
  const t = await api("salvar_texto", dados);
  if (alvo.id === null) alvo.barra.append(botaoApagar()); // texto novo: agora existe e dá para apagar
  alvo.id = t.id;
  alvo.original = JSON.stringify({ titulo: dados.titulo, corpo: dados.corpo, aula_id: dados.aula_id });
  if (form === alvo) $("#detalhe-texto h2").textContent = t.titulo;
  if (!calado) avisar("Texto salvo.");
  await recarregarLista();
  emitir("textos-mudaram");
  return t;
}

/** Antes de sair do texto aberto: salva o que mudou. Devolve false se não deu (ex.: sem título). */
async function sairDoTexto() {
  if (!mudou()) return true;
  if (form.id === null && !form.titulo.value.trim() && !form.corpo.value.trim()) return true;
  try {
    const t = await salvar({ calado: true });
    avisar(`Salvei as mudanças de “${t.titulo}”.`);
    return true;
  } catch (e) {
    avisarErro(e);
    return false;
  }
}

// o texto como está agora (salva antes, se mudou) num .mp3, com a voz da leitura escolhida aqui
const salvarAudioDoTexto = () => botaoSalvarAudio({
  classe: "btn", titulo: "Grava o texto num arquivo de áudio (.mp3) em Músicas › Echo",
  antes: () => {
    if (form.corpo.value.trim()) return true;
    avisar("Escreva o texto antes de salvar o áudio.");
    return false;
  },
  gravar: async () => {
    if (form.id === null || mudou()) await salvar({ calado: true });
    return api("salvar_audio_texto", form.id, { ...ajustes, voz: ajustes.voz || vozDoOuvir().voz });
  },
});

function botaoApagar() {
  return botaoConfirmar({
    texto: "Apagar texto", pergunta: "Clique de novo para apagar", class: "btn btn-perigo",
    aoConfirmar: async () => {
      try {
        await api("apagar_texto", form.id);
        avisar(`Texto “${form.titulo.value.trim()}” apagado.`);
        form = null;
        await recarregarLista();
        emitir("textos-mudaram");
        mostrarPrimeiro();
      } catch (e) { avisarErro(e); }
    },
  });
}

// o que o Ouvir lê: o trecho selecionado no texto, se houver; senão, o texto todo
function trechoSelecionado(corpo) {
  const { selectionStart: inicio, selectionEnd: fim, value } = corpo;
  return inicio !== fim ? value.slice(inicio, fim) : "";
}

function contagem(corpo) {
  const palavras = corpo.trim() ? corpo.trim().split(/\s+/).length : 0;
  if (!palavras) return "";
  const minutos = Math.round(palavras / 150); // a voz do Windows lê umas 150 palavras por minuto
  return `${plural(palavras, "palavra")} · ${minutos < 1 ? "menos de 1 minuto" : `uns ${plural(minutos, "minuto")}`} de leitura`;
}

const padrao = () => ({ voz: vozDoOuvir().voz, taxa: taxaEscolhida(), tom: 1, volume: 100 });
const virgula = (n) => String(Number(n.toFixed(2))).replace(".", ",");
const REGIOES = { "en-us": "Estados Unidos", "en-gb": "Reino Unido", "en-au": "Austrália", "en-ca": "Canadá",
  "en-in": "Índia", "en-ie": "Irlanda", "en-nz": "Nova Zelândia", "en-za": "África do Sul" };

function itemDeVoz(v) {
  const regiao = REGIOES[v.lang.toLowerCase().replace("_", "-")] || v.lang;
  return { valor: v.name, rotulo: v.name.replace(/^Microsoft /, "").replace(/ - English.*$/, "").replace(/ Online \(Natural\)$/, ""),
    secundario: v.localService ? regiao : `${regiao} · online, só para ouvir (o áudio sai com uma voz do Windows)` };
}

// voz, velocidade, tom e volume do Ouvir e do Salvar áudio, escolhidos na hora (ficam enquanto o app está aberto)
function painelVoz() {
  ajustes ??= padrao();
  const alvoVoz = el("div", { id: "f-texto-voz" });
  const campoVoz = el("div", { class: "campo" }, el("span", { text: "Voz" }), alvoVoz);
  const voz = criarSeletor(alvoVoz, { placeholder: "Voz padrão", busca: "Procurar voz…",
    vazio: "Nenhuma voz em inglês com esse nome", aoMudar: (v) => { ajustes.voz = v; } });
  esperarVozes().then((vozes) => {
    voz.definirItens(vozes.map(itemDeVoz));
    voz.valor = ajustes.voz;
  });
  const painel = el("fieldset", { class: "voz-leitura" },
    el("legend", { text: "Voz da leitura" }),
    el("div", { class: "grade-voz" },
      campoVoz,
      deslizante({ rotulo: "Velocidade", nome: "taxa", min: 0.5, max: 2, passo: 0.05, valor: ajustes.taxa,
        formatar: (v) => `${virgula(v)}×`, aoMudar: (v) => { ajustes.taxa = v; } }),
      deslizante({ rotulo: "Tom", nome: "tom", min: 0.5, max: 1.5, passo: 0.05, valor: ajustes.tom,
        formatar: (v) => { const p = Math.round((v - 1) * 100); return p ? `${p > 0 ? "+" : ""}${p}%` : "normal"; },
        aoMudar: (v) => { ajustes.tom = v; } }),
      deslizante({ rotulo: "Volume", nome: "volume", min: 0, max: 100, passo: 5, valor: ajustes.volume,
        formatar: (v) => `${v}%`, aoMudar: (v) => { ajustes.volume = v; } })),
    el("p", { class: "ajuda" }, "Vale para o Ouvir e o Salvar áudio, e não fica guardada no texto. ",
      el("button", { type: "button", class: "btn-link", text: "Voltar ao padrão",
        onclick: () => { ajustes = padrao(); painel.replaceWith(painelVoz()); } })));
  return painel;
}

function desenharTexto(t) {
  const alvo = $("#detalhe-texto");
  const titulo = el("input", { name: "titulo", maxlength: "120", value: t.titulo, placeholder: "ex.: My weekend", autocomplete: "off" });
  const corpo = el("textarea", { name: "corpo", maxlength: "20000", rows: 14, lang: "en", spellcheck: "true",
    placeholder: "Escreva o texto em inglês. Uma linha em branco separa os parágrafos. Para ouvir só um pedaço, selecione o trecho e clique em Ouvir trecho." });
  corpo.value = t.corpo;
  const conta = el("p", { class: "ajuda contagem" });
  const contar = () => { conta.textContent = contagem(corpo.value); };
  corpo.addEventListener("input", contar);
  contar();
  const ouvir = botaoOuvir(() => paraLer(trechoSelecionado(corpo) || corpo.value), {
    classe: "btn", vazio: "Escreva o texto antes de ouvir.", ajustes: () => ajustes,
    rotulo: () => (trechoSelecionado(corpo).trim() ? "Ouvir trecho" : "Ouvir") });
  ouvir.title = "Lê o texto todo; com um trecho selecionado, só o trecho";
  // a seleção do textarea não tem um evento só que pegue tudo (mouse, teclado, Ctrl+A): estes cobrem os jeitos
  for (const evento of ["select", "mouseup", "keyup", "input", "blur"]) corpo.addEventListener(evento, () => ouvir.repintar());

  const alvoAula = el("div", { id: "f-texto-aula" });
  const campoAula = el("div", { class: "campo" }, el("span", { text: "Aula" }), alvoAula);
  const aula = criarSeletor(alvoAula, { placeholder: "Sem aula", busca: "Procurar aula…", vazio: "Nenhuma aula com esse nome" });
  aula.definirItens(itensDeAula());
  aula.valor = t.aula_id ?? SEM_AULA;

  form = { id: t.id, titulo, corpo, aula, original: null, barra: null };
  form.original = retrato();

  trocar(alvo,
    el("h2", { text: t.id === null ? "Novo texto" : t.titulo }),
    el("form", { class: "detalhe-form", onsubmit: (ev) => ev.preventDefault() },
      el("div", { class: "grade-texto" },
        el("label", { class: "campo" }, el("span", { text: "Título" }), titulo),
        campoAula),
      el("label", { class: "campo campo-corpo" }, el("span", { text: "Texto" }), corpo),
      conta,
      painelVoz(),
      el("div", { class: "botoes barra-acoes" },
        el("button", { type: "button", class: "btn btn-primario", text: "Salvar",
          onclick: () => salvar().catch(avisarErro) }),
        ouvir,
        salvarAudioDoTexto(),
        t.id === null ? null : botaoApagar())));
  form.barra = $(".barra-acoes", alvo);
  desenharLista();
  if (t.id === null) titulo.focus();
}

function mostrarPrimeiro() {
  if (lista.length) return abrir({ id: lista[0].id });
  form = null;
  trocar($("#detalhe-texto"), estadoVazio("Nenhum texto ainda.",
    "Clique em “Novo texto”, escreva em inglês e salve o áudio para usar na aula."));
  desenharLista();
}

async function abrir(qual) {
  if (!(await sairDoTexto())) return;
  if (qual.id !== undefined && form?.id === qual.id) return desenharLista(); // já está aberto (e salvo)
  if (qual.id === undefined) {
    // "novo" pode vir null (Sem aula, da tela da aula): só sem ele é que vale a aula do filtro
    const aula = "novo" in qual ? qual.novo : (typeof filtro === "number" ? filtro : null);
    desenharTexto({ id: null, titulo: "", corpo: "", aula_id: aula });
    return;
  }
  const alvo = $("#detalhe-texto");
  trocar(alvo, carregando("Abrindo o texto…", esqueletoLinhas()));
  try {
    desenharTexto(await api("texto", qual.id));
  } catch (e) { erroEm(alvo, e); }
}

/** Abre o texto na aba Textos (a tela da aula usa). */
export function abrirTexto(id) {
  pedido = { id };
  abrirAba("textos");
}

/** Abre um texto novo já na aula `aulaId` (null = Sem aula). */
export function novoTexto(aulaId) {
  pedido = { novo: aulaId };
  abrirAba("textos");
}

export function iniciarTextos() {
  $("#novo-texto").addEventListener("click", () => abrir({ novo: typeof filtro === "number" ? filtro : null }));
  seletorFiltro = criarSeletor($("#filtro-textos"), {
    todos: "Todas as aulas", busca: "Procurar aula…", vazio: "Nenhuma aula com esse nome",
    aoMudar: (v) => { filtro = v === null || v === SEM_AULA ? v : Number(v); desenharLista(); },
  });
  ouvir("aulas-mudaram", () => {
    seletorFiltro.definirItens(itensDeAula());
    if (filtro !== null && seletorFiltro.valor === null) { filtro = null; desenharLista(); } // a aula sumiu
    form?.aula.definirItens(itensDeAula());
  });
  ouvir("aba-aberta", async (aba) => {
    if (aba !== "textos") {
      await sairDoTexto(); // o que a cliente escreveu não se perde ao trocar de aba
      return;
    }
    try {
      await recarregarAulas();
      await recarregarLista();
    } catch (e) { return erroEm($("#detalhe-texto"), e); }
    if (pedido) {
      const qual = pedido;
      pedido = null;
      return abrir(qual);
    }
    if (form) return desenharLista(); // continua o que a cliente estava escrevendo
    mostrarPrimeiro();
  });
  // fechar a janela com mudança sem salvar: o Edge pergunta antes
  addEventListener("beforeunload", (ev) => { if (mudou()) ev.preventDefault(); });
}
