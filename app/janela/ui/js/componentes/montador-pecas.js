// Montar a regra de uma estrutura com peças, na ordem em que aparecem na frase (ver nucleo/blocos.py).
// Peça = { tipo, texto?, menos?, opcional? }. O catálogo de tipos vem do Python (estado.pecas):
// { id, grupo, rotulo, exemplos, escreve (texto livre), recheio (peça do meio: sem "pode faltar") }.
import { $, el, trocar } from "../lib/dom.js";
import { icone } from "./icones.js";

const PECAS_NOVA_ESTRUTURA = [{ tipo: "pessoa" }, { tipo: "palavra", texto: "" }];

/**
 * @param {object} estrutura   a estrutura aberta ({} se nova): usa `blocos`, `padrao` e `id`
 * @param {object[]} catalogo  tipos de peça
 * @param {(temPecas: boolean) => void} aoMudar  avisado a cada mudança
 * @returns {{raiz: HTMLElement, atualizar: () => void, valor: () => string}}
 *          `valor()` = JSON com {pecas, excluir} para salvar/testar, ou "" sem peças (regra avançada)
 */
export function montadorDePecas(estrutura, catalogo, aoMudar) {
  const tipoPorId = (id) => catalogo.find((p) => p.id === id);
  const lista = el("div", { class: "pecas" });
  const resumo = el("p", { class: "resumo-regra" });
  const excluir = el("textarea", { rows: "2", placeholder: "ex.: had to", "aria-label": "Tirar frases que tenham" },
    (estrutura.blocos?.excluir || []).join("\n"));
  let pecas = estrutura.blocos
    ? estrutura.blocos.pecas.map((p) => ({ ...p }))
    : estrutura.id ? [] : PECAS_NOVA_ESTRUTURA.map((p) => ({ ...p }));

  function seletorDeTipo(atual) {
    const grupos = [...new Set(catalogo.map((p) => p.grupo))];
    return el("select", { class: "peca-tipo", "aria-label": "Tipo de peça" },
      grupos.map((g) => el("optgroup", { label: g },
        catalogo.filter((p) => p.grupo === g).map((p) => el("option", { value: p.id, text: p.rotulo, selected: p.id === atual })))));
  }

  function mover(i, passo) {
    const j = i + passo;
    if (j < 0 || j >= pecas.length) return;
    [pecas[i], pecas[j]] = [pecas[j], pecas[i]];
    desenhar();
  }

  function linha(p, i) {
    const info = tipoPorId(p.tipo) || {};
    const tipo = seletorDeTipo(p.tipo);
    tipo.addEventListener("change", () => {
      p.tipo = tipo.value;
      const novo = tipoPorId(p.tipo);
      if (!novo.escreve) delete p.texto;
      if (novo.escreve || novo.recheio) delete p.menos;
      desenhar();
    });
    const conteudo = info.escreve
      ? el("input", { class: "peca-texto", value: p.texto || "", placeholder: info.exemplos, "aria-label": "Palavra",
        oninput: (ev) => { p.texto = ev.target.value; atualizar(); } })
      : el("span", { class: "peca-classe" },
        el("span", { class: "peca-exemplos", text: info.exemplos }),
        info.recheio ? null : el("input", {
          class: "peca-menos", value: p.menos || "", placeholder: "menos… (ex.: be/have)",
          title: "Formas básicas que não valem, separadas por /", "aria-label": "Menos estas palavras",
          oninput: (ev) => { p.menos = ev.target.value; atualizar(); },
        }));
    const opcional = info.recheio ? el("span") : el("label", { class: "peca-opcional" },
      el("input", { type: "checkbox", checked: !!p.opcional, onchange: (ev) => { p.opcional = ev.target.checked; atualizar(); } }),
      " pode faltar");
    const botao = (nomeIcone, rotulo, desligado, acao) =>
      el("button", { type: "button", class: "btn-icone", title: rotulo, "aria-label": rotulo, disabled: desligado, onclick: acao }, icone(nomeIcone));
    return el("div", { class: "peca" },
      el("span", { class: "peca-n", text: String(i + 1) }), tipo, conteudo, opcional,
      el("span", { class: "peca-botoes" },
        botao("cima", "Subir", i === 0, () => mover(i, -1)),
        botao("baixo", "Descer", i === pecas.length - 1, () => mover(i, 1)),
        botao("fechar", "Tirar peça", false, () => { pecas.splice(i, 1); desenhar(); })));
  }

  // "Procura: wish (qualquer forma) + alguém ou algo + would + verbo na forma básica"
  function descrever(p) {
    const info = tipoPorId(p.tipo) || { rotulo: "?" };
    let nome = info.escreve ? p.texto || "…" : info.rotulo.toLowerCase();
    if (p.tipo === "forma") nome = `${p.texto || "…"} (qualquer forma)`;
    else if (!info.escreve && !info.recheio && p.menos) nome += ` (menos ${p.menos})`;
    return p.opcional && !info.recheio ? `${nome} (pode faltar)` : nome;
  }

  function atualizar() {
    if (pecas.length) trocar(resumo, el("b", { text: "Procura: " }), pecas.map(descrever).join(" + "));
    else if (estrutura.padrao && !estrutura.blocos) {
      trocar(resumo, "Esta estrutura usa uma regra avançada (veio pronta ou foi guardada de uma busca escrita). Se montar peças aqui, elas substituem a regra avançada.");
    } else trocar(resumo, "Nenhuma peça ainda: adicione as peças na ordem em que aparecem na frase.");
    aoMudar(pecas.length > 0);
  }

  function desenhar() {
    trocar(lista, pecas.map(linha));
    atualizar();
  }

  const adicionar = el("button", {
    type: "button", class: "btn-link",
    onclick: () => { pecas.push({ tipo: "palavra", texto: "" }); desenhar(); $("select", lista.lastElementChild).focus(); },
  }, icone("mais"), "Adicionar peça");
  const raiz = el("section", { class: "montador" },
    el("h3", { text: "Como achar essa estrutura nas falas" }),
    el("p", { class: "ajuda", text: "Monte a frase em peças, na ordem. Escolha da lista (ex.: “Verbo no passado” vale para qualquer verbo: went, ate, played…) ou escreva uma palavra. Depois clique em Testar." }),
    lista, adicionar, resumo,
    el("label", { class: "campo" }, el("span", { text: "Tirar frases que tenham (uma expressão por linha, opcional)" }), excluir));
  desenhar();

  return {
    raiz,
    atualizar,
    valor() {
      if (!pecas.length) return "";
      return JSON.stringify({ pecas, excluir: excluir.value.split("\n").map((x) => x.trim()).filter(Boolean) });
    },
  };
}
