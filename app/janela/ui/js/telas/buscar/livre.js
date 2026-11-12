// Modo "Escrever o que procuro" da tela Buscar: o texto, "Aceitar outras formas", o tempo do verbo e
// as fichas com os phrasal verbs quando a cliente escreve só um verbo. A busca não fica salva no banco; só
// as preferências (texto, formas, tempo) ficam lembradas no navegador da janela.
import { $, el, trocar } from "../../lib/dom.js";
import { guardar, lembrar } from "../../lib/armazenamento.js";
import { fichas } from "../../componentes/fichas.js";
import { interruptor } from "../../componentes/interruptor.js";
import { criarSeletor } from "../../componentes/seletor.js";

const TEMPOS = [
  { valor: "presente", rotulo: "Presente", secundario: "go, goes" },
  { valor: "passado", rotulo: "Passado", secundario: "went" },
  { valor: "participio", rotulo: "Particípio", secundario: "gone (have gone, was gone)" },
  { valor: "ing", rotulo: "Com -ing", secundario: "going" },
  { valor: "basica", rotulo: "Forma básica", secundario: "go (to go, will go, can go)" },
];
const PRIMEIRAS = 24; // fichas mostradas antes de "Mostrar todos"

const campos = {};
const atuais = { verbo: null, itens: [], todas: false, aoEscolher: null };

export function iniciarLivre() {
  campos.texto = $("#f-texto");
  campos.texto.value = lembrar("texto-livre", "");
  campos.tempo = criarSeletor($("#f-tempo"), {
    busca: "Procurar…", vazio: "Nenhum", todos: "Qualquer tempo",
    aoMudar: (v) => guardar("tempo-verbo", v),
  });
  campos.tempo.definirItens(TEMPOS);
  campos.tempo.valor = lembrar("tempo-verbo", null);
  campos.formas = interruptor({
    rotulo: "Aceitar outras formas",
    detalhe: "take também acha took, taking e take it off",
    ligado: lembrar("outras-formas", true),
    aoMudar: (ligado) => { guardar("outras-formas", ligado); campos.tempo.desabilitar(!ligado); },
  });
  trocar($("#f-outras-formas"), campos.formas);
  campos.tempo.desabilitar(!campos.formas.ligado);
}

/** {texto, outras_formas, tempo} para a api "buscar" e "phrasal_verbs". */
export function paramsLivre() {
  const texto = campos.texto.value.trim();
  guardar("texto-livre", texto);
  return { texto, outras_formas: campos.formas.ligado, tempo: campos.formas.ligado ? campos.tempo.valor : null };
}

/** Uma palavra só: pode ser um verbo para listar os phrasal verbs (o Python confirma). */
export const umaPalavra = (texto) => /^[^\s]+$/.test(texto);

export function escreverTexto(texto) {
  campos.texto.value = texto;
  guardar("texto-livre", texto);
}

function desenharFichas() {
  const area = $("#fichas-livre");
  const ativo = campos.texto.value.trim().toLowerCase();
  const visiveis = atuais.todas ? atuais.itens : atuais.itens.slice(0, PRIMEIRAS);
  const resto = atuais.itens.length - visiveis.length;
  trocar(area,
    el("h3", { text: `Phrasal verbs com ${atuais.verbo}` }),
    el("p", { class: "ajuda", text: "Os que aparecem nas falas, com quantas frases cada um e o que querem dizer. Clique num para ver os exemplos." }),
    fichas({
      itens: visiveis.map((x) => ({ texto: x.texto, numero: x.frases, detalhe: x.significado })),
      ativo, rotulo: `Phrasal verbs com ${atuais.verbo}`, aoEscolher: atuais.aoEscolher,
    }),
    resto > 0
      ? el("button", { type: "button", class: "btn-link", text: `Mostrar todos os ${atuais.itens.length}`,
          onclick: () => { atuais.todas = true; desenharFichas(); } })
      : null);
  area.hidden = false;
}

/**
 * Mostra as fichas dos phrasal verbs de `verbo` acima do resultado.
 * @param {string} verbo
 * @param {{texto: string, frases: number}[]} itens
 * @param {(texto: string) => void} aoEscolher
 */
export function mostrarFichas(verbo, itens, aoEscolher) {
  Object.assign(atuais, { verbo, itens, todas: false, aoEscolher });
  desenharFichas();
}

/** Depois de uma busca escrita: as fichas ficam se o texto é uma delas (marcada); senão, somem. */
export function acompanharFichas(texto) {
  const area = $("#fichas-livre");
  if (atuais.itens.some((x) => x.texto === texto.toLowerCase())) {
    if (!atuais.todas && atuais.itens.findIndex((x) => x.texto === texto.toLowerCase()) >= PRIMEIRAS) atuais.todas = true;
    desenharFichas();
  } else {
    area.hidden = true;
  }
}

export function esconderFichas() {
  $("#fichas-livre").hidden = true;
}
