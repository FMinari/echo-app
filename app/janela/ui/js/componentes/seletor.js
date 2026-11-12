// Seletores com busca. A lista tem altura fixa (~6 itens) e rola; o campo de busca filtra sem
// distinguir acento nem maiúscula; setas e Enter funcionam.
//
// Item: { valor, rotulo, secundario?, grupo?, resumo?, acao? }
//   grupo   cabeçalho na lista (itens do mesmo grupo vêm juntos)
//   resumo  texto no botão quando escolhido (senão, o rótulo)
//   acao    { rotulo, titulo, aoClicar(botao) }: um botãozinho dentro do item (ex.: Apagar)
import { el, trocar } from "../lib/dom.js";
import { icone } from "./icones.js";

const semAcento = (t) => String(t).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

// só um seletor aberto por vez; clicar fora fecha
let aberto = null;
document.addEventListener("mousedown", (ev) => {
  if (aberto && !aberto.raiz.contains(ev.target)) aberto.fechar();
});
function abrirSo(controle) {
  if (aberto && aberto !== controle) aberto.fechar();
  aberto = controle;
}

// Painel com busca + lista navegável pelo teclado, usado pelos dois seletores.
function painelDeBusca({ placeholder, vazio, aoEscolher }) {
  const busca = el("input", { type: "search", placeholder, "aria-label": placeholder });
  const lista = el("div", { class: "sel-lista", role: "listbox" });
  const linhaBusca = el("label", { class: "sel-busca" }, icone("busca"), busca);
  const painel = el("div", { class: "sel-painel" }, linhaBusca, lista);

  let itens = [];
  let visiveis = [];
  let ativo = -1;
  let atual = null;

  function marcar(n, rolar) {
    ativo = n;
    for (const op of lista.querySelectorAll(".sel-opcao")) op.classList.toggle("ativo", Number(op.dataset.n) === n);
    if (rolar) lista.querySelector(`.sel-opcao[data-n="${n}"]`)?.scrollIntoView({ block: "nearest" });
  }

  function opcao(item, n) {
    const op = el("div", {
      class: "sel-opcao", role: "option", "data-n": n,
      "aria-selected": String(atual !== null && String(item.valor) === String(atual)),
      onmousedown: (ev) => ev.preventDefault(), // não tira o foco da busca
      onclick: () => aoEscolher(item),
      onmousemove: () => marcar(n, false),
    },
    el("span", { class: "sel-rotulo", text: item.rotulo }),
    item.secundario ? el("span", { class: "sel-secundario", text: item.secundario }) : null);
    if (item.acao) {
      op.append(el("button", {
        type: "button", class: "sel-acao", text: item.acao.rotulo, title: item.acao.titulo || item.acao.rotulo,
        onclick: (ev) => { ev.stopPropagation(); item.acao.aoClicar(ev.currentTarget); },
      }));
    }
    return op;
  }

  function desenhar() {
    const termo = semAcento(busca.value.trim());
    visiveis = itens.filter((i) => !termo || semAcento(`${i.rotulo} ${i.secundario || ""} ${i.grupo || ""}`).includes(termo));
    const filhos = [];
    let grupo;
    visiveis.forEach((item, n) => {
      if (item.grupo && item.grupo !== grupo) {
        grupo = item.grupo;
        filhos.push(el("div", { class: "sel-grupo", text: grupo }));
      }
      filhos.push(opcao(item, n));
    });
    if (!visiveis.length) {
      filhos.push(el("div", { class: "sel-vazio", text: typeof vazio === "function" ? vazio(busca.value.trim()) : vazio }));
    }
    trocar(lista, filhos);
    const escolhido = visiveis.findIndex((i) => atual !== null && String(i.valor) === String(atual));
    marcar(escolhido >= 0 ? escolhido : visiveis.length ? 0 : -1, true);
  }

  busca.addEventListener("input", desenhar);
  busca.addEventListener("keydown", (ev) => {
    if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
      ev.preventDefault();
      if (!visiveis.length) return;
      const passo = ev.key === "ArrowDown" ? 1 : -1;
      marcar((ativo + passo + visiveis.length) % visiveis.length, true);
    } else if (ev.key === "Enter") {
      ev.preventDefault();
      if (visiveis[ativo]) aoEscolher(visiveis[ativo]);
    }
  });

  return {
    painel, busca, lista,
    abrir(novosItens, valorAtual) {
      itens = novosItens;
      atual = valorAtual;
      busca.value = "";
      desenhar();
    },
    redesenhar(novosItens) {
      itens = novosItens;
      desenhar();
    },
  };
}

/**
 * Escolha de um item. Troca o `alvo` (um div vazio) pelo seletor.
 * `todos`: rótulo da opção "sem filtro", que vale null (ex.: "Qualquer personagem").
 * Devolve { valor (get/set), itens, definirItens(lista), desabilitar(sim) }.
 */
export function criarSeletor(alvo, { placeholder = "Escolha…", busca = "Procurar…", vazio = "Nada encontrado", todos = null, aoMudar = () => {} } = {}) {
  const texto = el("span", { class: "sel-texto" });
  const botao = el("button", { type: "button", class: "sel-botao", role: "combobox", "aria-haspopup": "listbox", "aria-expanded": "false" },
    texto, icone("baixo"));
  if (alvo.id) botao.id = alvo.id;
  const raiz = el("div", { class: "sel" }, botao);
  alvo.replaceWith(raiz);

  let itens = [];
  let valor = null;
  const comTodos = () => (todos ? [{ valor: null, rotulo: todos }, ...itens] : itens);
  const p = painelDeBusca({
    placeholder: busca, vazio,
    aoEscolher: (item) => { seletor.valor = item.valor; fechar(); botao.focus(); aoMudar(valor); },
  });
  p.painel.hidden = true;
  raiz.append(p.painel);

  function pintar() {
    const item = comTodos().find((i) => String(i.valor) === String(valor));
    texto.textContent = item ? item.resumo || item.rotulo : placeholder;
    texto.classList.toggle("sel-placeholder", !item);
  }
  // Abre para cima quando embaixo não cabe e em cima cabe mais (perto do fim da janela, como a voz na Text to
  // Audio). O topo fixo da janela conta como espaço ocupado.
  function posicionar() {
    p.painel.classList.remove("sel-para-cima");
    const caixa = botao.getBoundingClientRect();
    const altura = p.painel.getBoundingClientRect().height;
    const topo = document.querySelector(".topo")?.getBoundingClientRect().bottom ?? 0;
    const embaixo = innerHeight - caixa.bottom - 8;
    const emCima = caixa.top - topo - 8;
    if (altura > embaixo && emCima > embaixo) p.painel.classList.add("sel-para-cima");
  }
  function abrir() {
    if (botao.disabled) return;
    abrirSo(controle);
    p.painel.hidden = false;
    botao.setAttribute("aria-expanded", "true");
    p.abrir(comTodos(), valor);
    posicionar();
    p.busca.focus({ preventScroll: true });
  }
  function fechar() {
    p.painel.hidden = true;
    botao.setAttribute("aria-expanded", "false");
    if (aberto === controle) aberto = null;
  }
  const controle = { raiz, fechar };

  botao.addEventListener("click", () => (p.painel.hidden ? abrir() : fechar()));
  botao.addEventListener("keydown", (ev) => { if (ev.key === "ArrowDown") { ev.preventDefault(); abrir(); } });
  p.painel.addEventListener("keydown", (ev) => { if (ev.key === "Escape") { fechar(); botao.focus(); } });

  const seletor = {
    get valor() { return valor; },
    set valor(v) { valor = v === "" || v === undefined ? null : v; pintar(); },
    get itens() { return itens; },
    definirItens(novos) {
      itens = novos;
      if (valor !== null && !itens.some((i) => String(i.valor) === String(valor))) valor = null;
      pintar();
    },
    desabilitar(sim) {
      botao.disabled = sim;
      if (sim) fechar();
    },
  };
  pintar();
  return seletor;
}

/**
 * Escolha de vários itens: a busca fica sempre à mostra e lista o que ainda não foi escolhido;
 * os escolhidos aparecem embaixo, cada um com um × para tirar.
 * Devolve { valores (get/set), definirItens(lista) }.
 */
export function criarMultiSeletor(alvo, { busca = "Procurar…", vazio = "Nada encontrado", semEscolha = "", aoMudar = () => {} } = {}) {
  let itens = [];
  let escolhidos = [];
  const disponiveis = () => itens.filter((i) => !escolhidos.some((v) => String(v) === String(i.valor)));

  const p = painelDeBusca({
    placeholder: busca, vazio,
    aoEscolher: (item) => { escolhidos.push(item.valor); p.busca.value = ""; depoisDeMudar(); p.busca.focus(); },
  });
  p.painel.classList.add("sel-embutido");
  p.lista.hidden = true;
  const selecionados = el("div", { class: "sel-escolhidos" });
  const raiz = el("div", { class: "sel sel-multi" }, p.painel, selecionados);
  alvo.replaceWith(raiz);

  function abrirLista() {
    abrirSo(controle);
    p.lista.hidden = false;
    p.redesenhar(disponiveis());
  }
  function fechar() {
    p.lista.hidden = true;
    if (aberto === controle) aberto = null;
  }
  const controle = { raiz, fechar };

  p.busca.addEventListener("focus", abrirLista);
  p.busca.addEventListener("input", () => { if (p.lista.hidden) abrirLista(); });
  p.busca.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") fechar();
    else if (ev.key === "Backspace" && !p.busca.value && escolhidos.length) { escolhidos.pop(); depoisDeMudar(); }
  });

  function cartao(v) {
    const item = itens.find((i) => String(i.valor) === String(v));
    if (!item) return null;
    return el("span", { class: "sel-cartao" },
      el("span", { text: item.rotulo }),
      item.secundario ? el("small", { text: item.secundario }) : null,
      el("button", {
        type: "button", class: "sel-tirar", title: `Tirar ${item.rotulo}`, "aria-label": `Tirar ${item.rotulo}`,
        onclick: () => { escolhidos = escolhidos.filter((e) => String(e) !== String(v)); depoisDeMudar(); },
      }, icone("fechar")));
  }
  function pintarEscolhidos() {
    if (!escolhidos.length) trocar(selecionados, semEscolha ? el("p", { class: "sel-dica", text: semEscolha }) : null);
    else trocar(selecionados, escolhidos.map(cartao));
  }
  function depoisDeMudar() {
    pintarEscolhidos();
    if (!p.lista.hidden) p.redesenhar(disponiveis());
    aoMudar([...escolhidos]);
  }

  return {
    get valores() { return [...escolhidos]; },
    set valores(vs) {
      escolhidos = [...(vs || [])].filter((v) => itens.some((i) => String(i.valor) === String(v)));
      pintarEscolhidos();
    },
    definirItens(novos) {
      itens = novos;
      escolhidos = escolhidos.filter((v) => itens.some((i) => String(i.valor) === String(v)));
      pintarEscolhidos();
      if (!p.lista.hidden) p.redesenhar(disponiveis());
    },
  };
}
