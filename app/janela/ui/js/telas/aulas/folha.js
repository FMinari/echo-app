// "Fazer folha para os alunos": as frases da aula como Exemplos (a estrutura destacada) ou Completar (a
// estrutura vira lacuna, com a dica do verbo e o gabarito no fim). Prévia na tela e "Imprimir ou salvar
// em PDF" pelo próprio Edge: na impressão só a folha aparece.
import { api, pausarSinal } from "../../lib/ponte.js";
import { el, trocar } from "../../lib/dom.js";
import { guardar, lembrar } from "../../lib/armazenamento.js";
import { destaquesNaFrase } from "../../lib/formato.js";
import { alternador } from "../../componentes/alternador.js";
import { erroEm } from "../../componentes/avisos.js";
import { carregando, esqueletoLinhas } from "../../componentes/esqueleto.js";
import { interruptor } from "../../componentes/interruptor.js";

const LACUNA = "__________";
const INSTRUCAO = {
  exemplos: "Read the sentences. Pay attention to the highlighted words.",
  completar: "Complete the sentences with the correct form of the verbs in brackets.",
};

/** A frase com cada trecho destacado trocado pelo que `por(i, trecho)` devolver. */
function comTrechos(frase, destaques, por) {
  const partes = [];
  let pos = 0;
  destaquesNaFrase(frase, destaques).map((d, i) => [d[0], d[1], i]).sort((a, b) => a[0] - b[0]).forEach(([a, b, i]) => {
    if (a > pos) partes.push(frase.slice(pos, a));
    partes.push(por(i, frase.slice(a, b)));
    pos = b;
  });
  partes.push(frase.slice(pos));
  return partes;
}

function fonte(x) {
  if (x.tipo === "musica") return `${x.obra} · ${x.titulo}`;
  if (x.referencia === "filme" || (x.temporada == null && x.tipo === "filme")) return `${x.obra} (filme)`;
  return [x.obra, x.referencia, x.titulo].filter(Boolean).join(" · ");
}

/** Quais trechos viram lacuna: os que têm verbo ("if" do third conditional fica à vista); se nenhum
 * tiver, todos. */
const lacunas = (x) => (x.dicas.some(Boolean) ? x.dicas.map(Boolean) : x.destaques.map(() => true));

function montarFolha(dados, op) {
  const completar = op.tipo === "completar";
  const itens = dados.itens.map((x) => {
    const vira = lacunas(x);
    const frase = completar
      ? comTrechos(x.frase, x.destaques, (i, t) => {
        if (!vira[i]) return t;
        const colada = x.destaques[i][0] > 0 && !/\s/.test(x.frase[x.destaques[i][0] - 1]); // I'd -> I ____
        return el("span", { class: "lacuna" }, colada ? " " : "", LACUNA, op.dica && x.dicas[i] ? ` (${x.dicas[i]})` : "");
      })
      : comTrechos(x.frase, x.destaques, (_, t) => el("mark", { text: t }));
    return el("li", {},
      el("p", { class: "folha-frase" }, op.quem && x.falante ? el("b", { text: `${x.falante}: ` }) : null, frase),
      op.fonte ? el("p", { class: "folha-fonte", text: fonte(x) }) : null,
      op.notas && x.nota ? el("p", { class: "folha-nota", text: x.nota }) : null);
  });
  return el("article", { class: "folha" },
    el("h1", { text: op.titulo || dados.aula.nome }),
    op.instrucao ? el("p", { class: "folha-instrucao", text: op.instrucao }) : null,
    el("ol", { class: "folha-itens" }, itens),
    completar && op.gabarito ? el("section", { class: "folha-gabarito" },
      el("h2", { text: "Gabarito" }),
      el("ol", {}, dados.itens.map((x) => el("li", {
        text: destaquesNaFrase(x.frase, x.destaques).filter((_, i) => lacunas(x)[i]).map(([a, b]) => x.frase.slice(a, b)).join(" … "),
      })))) : null);
}

// Na impressão vai só a folha que está na prévia, pelo botão ou pelo Ctrl+P. Enquanto a janela de
// impressão do Edge está aberta, a página fica parada e não avisa o Python que está viva: pede uma pausa.
let previaAberta = null;
let tituloDaJanela = null;
addEventListener("beforeprint", () => {
  const folha = previaAberta?.isConnected ? previaAberta.firstChild : null;
  if (!folha) return;
  pausarSinal(3600);
  document.querySelector("#impressao")?.remove();
  document.body.append(el("div", { id: "impressao" }, folha.cloneNode(true)));
  tituloDaJanela = document.title;
  document.title = folha.querySelector("h1")?.textContent || document.title; // o nome do PDF
});
addEventListener("afterprint", () => {
  document.querySelector("#impressao")?.remove();
  if (tituloDaJanela !== null) { document.title = tituloDaJanela; tituloDaJanela = null; }
  pausarSinal(0);
});

/**
 * Troca o conteúdo de `alvo` pela tela da folha.
 * @param {HTMLElement} alvo
 * @param {number|null} aulaId
 * @param {string} nomeAula
 * @param {() => void} aoVoltar
 */
export async function abrirFolha(alvo, aulaId, nomeAula, aoVoltar) {
  const [espera, ...silhuetas] = carregando("Preparando a folha…", esqueletoLinhas(["60%", "90%", "85%", "88%"]));
  trocar(alvo, espera, ...silhuetas); // o aviso marca este pedido (ver abaixo)
  let dados;
  try {
    dados = await api("folha", aulaId);
  } catch (e) {
    if (alvo.contains(espera)) erroEm(alvo, e);
    return;
  }
  if (!alvo.contains(espera)) return; // a cliente abriu outra aula enquanto a folha carregava

  const op = {
    tipo: lembrar("folha-tipo", "exemplos"), titulo: nomeAula,
    fonte: lembrar("folha-fonte", true), quem: lembrar("folha-quem", true), dica: lembrar("folha-dica", true),
    gabarito: lembrar("folha-gabarito", true), notas: lembrar("folha-notas", false),
  };
  op.instrucao = INSTRUCAO[op.tipo];
  const previa = el("div", { class: "previa-folha" });
  previaAberta = previa;
  const desenhar = () => trocar(previa, montarFolha(dados, op));

  const chave = (nome, rotulo, detalhe = null, so = null) => {
    const i = interruptor({ rotulo, detalhe, ligado: op[nome], aoMudar: (v) => { op[nome] = v; guardar(`folha-${nome}`, v); desenhar(); } });
    if (so) i.dataset.so = so;
    return i;
  };
  const soCompletar = [chave("dica", "Dica do verbo", "(lose), (make): a forma básica, entre parênteses", "completar"),
    chave("gabarito", "Gabarito no fim", "numa página separada", "completar")];
  const mostrarSoCompletar = () => soCompletar.forEach((i) => { i.hidden = op.tipo !== "completar"; });

  const titulo = el("input", { type: "text", value: op.titulo, "aria-label": "Título da folha", maxlength: "120" });
  titulo.addEventListener("input", () => { op.titulo = titulo.value; desenhar(); });
  const instrucao = el("textarea", { rows: 2, "aria-label": "Instrução para os alunos" });
  instrucao.value = op.instrucao;
  instrucao.addEventListener("input", () => { op.instrucao = instrucao.value; desenhar(); });

  const tipo = alternador({
    opcoes: [{ valor: "exemplos", rotulo: "Exemplos" }, { valor: "completar", rotulo: "Completar" }],
    valor: op.tipo, rotulo: "Tipo de folha",
    aoMudar: (v) => {
      op.tipo = v;
      guardar("folha-tipo", v);
      op.instrucao = instrucao.value = INSTRUCAO[v];
      mostrarSoCompletar();
      desenhar();
    },
  });

  trocar(alvo,
    el("div", { class: "folha-topo" },
      el("h2", { text: `Folha · ${nomeAula}` }),
      el("button", { type: "button", class: "btn", text: "Voltar para a aula", onclick: aoVoltar })),
    el("div", { class: "folha-tela" },
      el("div", { class: "folha-opcoes" },
        tipo,
        el("label", { class: "campo" }, el("span", { text: "Título" }), titulo),
        el("label", { class: "campo" }, el("span", { text: "Instrução" }), instrucao),
        chave("fonte", "De onde é", "série e episódio, filme ou música"),
        chave("quem", "Quem fala"),
        ...soCompletar,
        chave("notas", "Minhas notas", "aparecem para os alunos"),
        el("button", { type: "button", class: "btn btn-primario btn-largo", text: "Imprimir ou salvar em PDF",
          onclick: async () => { await pausarSinal(3600); window.print(); } }),
        el("p", { class: "ajuda", text: "Para salvar em PDF, escolha “Salvar como PDF” na janela de impressão." })),
      previa));
  mostrarSoCompletar();
  desenhar();
}
