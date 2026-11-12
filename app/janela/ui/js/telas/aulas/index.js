// Tela Aulas: as aulas da cliente (e "Sem aula") à esquerda; a aula aberta à direita, com os textos dela (que abrem
// na aba Textos), as frases, a nota de cada uma, mover para outra aula, renomear, apagar e "Fazer folha" (folha.js).
import { api } from "../../lib/ponte.js";
import { $, el, trocar } from "../../lib/dom.js";
import { plural } from "../../lib/formato.js";
import { emitir, ouvir } from "../../lib/eventos.js";
import { estado } from "../../estado.js";
import { avisar, avisarErro, erroEm } from "../../componentes/avisos.js";
import { campoNome } from "../../componentes/campo-nome.js";
import { cartaoFrase } from "../../componentes/cartao-frase.js";
import { botaoConfirmar } from "../../componentes/confirmacao.js";
import { carregando, esqueletoCartaoFrase } from "../../componentes/esqueleto.js";
import { itemLista } from "../../componentes/item-lista.js";
import { criarSeletor } from "../../componentes/seletor.js";
import { estadoVazio } from "../../componentes/vazio.js";
import { abrirTexto, novoTexto } from "../textos/index.js";
import { aulaPorId, recarregarAulas } from "./dados.js";
import { abrirFolha } from "./folha.js";

const SEM_AULA = null;
let aberta; // id da aula aberta, SEM_AULA, ou undefined (nenhuma ainda)
let naFolha = false; // a folha da aula aberta está na tela (trocar de aba e voltar não pode perdê-la)
const notasSalvando = new Set(); // a folha espera as notas que ainda estão indo para o Python

// "3 frases · 1 texto" (os textos só quando tem)
const conteudo = (frases, textos) => plural(frases, "frase") + (textos ? ` · ${plural(textos, "texto")}` : "");

function desenharLista() {
  const itens = estado.aulas.map((a) => itemLista({
    rotulo: a.nome, detalhe: conteudo(a.frases, a.textos), atual: aberta === a.id, classe: "item-aula",
    aoClicar: () => abrir(a.id),
  }));
  trocar($("#lista-aulas"),
    itens.length ? itens : el("p", { class: "ajuda lista-nada", text: "Nenhuma aula ainda: crie uma acima." }),
    itemLista({ rotulo: "Sem aula", detalhe: conteudo(estado.semAula, estado.semAulaTextos), atual: aberta === SEM_AULA,
      classe: "item-aula sem-aula", aoClicar: () => abrir(SEM_AULA) }));
}

// a nota de cada frase: salva sozinha, um instante depois que a cliente para de digitar (ou ao sair do campo)
function campoNota(f) {
  const situacao = el("span", { class: "nota-situacao" });
  const caixa = el("textarea", { class: "nota", rows: 1, maxlength: "2000", placeholder: "Nota para a aula…", "aria-label": "Nota" });
  caixa.value = f.nota || "";
  let espera = null;
  const salvar = () => {
    clearTimeout(espera);
    espera = null;
    const pedido = api("anotar_frase", f.id, caixa.value)
      .then(() => { situacao.textContent = "Salvo"; })
      .catch(avisarErro)
      .finally(() => notasSalvando.delete(pedido));
    notasSalvando.add(pedido);
  };
  caixa.addEventListener("input", () => {
    clearTimeout(espera);
    situacao.textContent = "";
    espera = setTimeout(salvar, 600);
  });
  caixa.addEventListener("blur", () => { if (espera !== null) salvar(); });
  return el("label", { class: "campo-nota" }, caixa, situacao);
}

async function fazerFolha(alvo, id, nome) {
  await Promise.allSettled([...notasSalvando]); // a nota que a cliente acabou de escrever entra na folha
  naFolha = true;
  abrirFolha(alvo, id, nome, () => abrir(id));
}

// "Mover para…": as outras aulas e "Sem aula"
function campoMover(f, cartao) {
  const alvo = el("div");
  const caixa = el("div", { class: "mover" }, el("span", { text: "Mover para" }), alvo);
  const seletor = criarSeletor(alvo, { // o alvo já tem pai (a caixa): o seletor entra no lugar dele
    placeholder: "outra aula…", busca: "Procurar aula…", vazio: "Nenhuma aula com esse nome",
    aoMudar: async (v) => {
      const destino = v === "sem" ? SEM_AULA : Number(v);
      try {
        await api("mover_frase", f.id, destino);
        cartao().remove();
        avisar(`Frase movida para ${destino === SEM_AULA ? "Sem aula" : aulaPorId(destino)?.nome}.`);
        emitir("frases-mudaram");
      } catch (e) { avisarErro(e); }
    },
  });
  seletor.definirItens([
    ...estado.aulas.filter((a) => a.id !== aberta).map((a) => ({ valor: a.id, rotulo: a.nome })),
    ...(aberta === SEM_AULA ? [] : [{ valor: "sem", rotulo: "Sem aula" }]),
  ]);
  return caixa;
}

// os textos da aula: cada um abre na aba Textos; e um atalho para escrever outro já nesta aula
function secaoTextos(id, textos) {
  return el("div", { class: "textos-da-aula" },
    textos.length ? el("h3", { text: "Textos" }) : null,
    textos.map((t) => el("button", { type: "button", class: "item-texto-aula", onclick: () => abrirTexto(t.id) },
      el("b", { text: t.titulo }), el("span", { text: t.comeco || "(ainda sem texto)" }))),
    el("button", { type: "button", class: "btn-link", text: id === SEM_AULA ? "Escrever um texto" : "Escrever um texto para esta aula",
      onclick: () => novoTexto(id) }));
}

async function abrir(id) {
  aberta = id;
  naFolha = false;
  desenharLista();
  const alvo = $("#detalhe-aula");
  trocar(alvo, carregando("Carregando a aula…", esqueletoCartaoFrase(), esqueletoCartaoFrase()));
  try {
    const [frases, textos] = await Promise.all([api("frases_da_aula", id), api("textos", id)]);
    if (aberta !== id) return;
    const aula = id === SEM_AULA ? null : aulaPorId(id);
    const nome = aula ? aula.nome : "Sem aula";
    const acoes = el("div", { class: "botoes acoes-aula" },
      frases.length ? el("button", { type: "button", class: "btn btn-primario", text: "Fazer folha para os alunos",
        onclick: () => fazerFolha(alvo, id, nome) }) : null,
      aula ? campoNome({
        rotulo: "Renomear", placeholder: "Nome da aula", valor: aula.nome, classe: "btn",
        aoSalvar: async (novo) => { await api("renomear_aula", id, novo); await recarregarAulas(); abrir(id); },
      }) : null,
      aula ? botaoConfirmar({
        texto: "Apagar aula", pergunta: "Clique de novo para apagar", class: "btn btn-perigo",
        titulo: "As frases não se perdem: vão para “Sem aula”",
        aoConfirmar: async () => {
          try {
            await api("apagar_aula", id);
            avisar(`Aula “${aula.nome}” apagada. As frases dela estão em “Sem aula”.`);
            await recarregarAulas();
            abrir(SEM_AULA);
          } catch (e) { avisarErro(e); }
        },
      }) : null);
    trocar(alvo,
      el("h2", { text: nome }),
      el("p", { class: "ajuda", text: aula
        ? `${plural(frases.length, "frase")}. Para pôr mais, escolha esta aula em “Guardar frases na aula”, na tela Buscar.`
        : "Frases guardadas sem escolher aula. Dá para mover cada uma para uma aula." }),
      acoes,
      secaoTextos(id, textos),
      frases.length
        ? el("div", { class: "cartoes" }, frases.map((f) => {
          let cartao;
          cartao = cartaoFrase(f, {
            // tirar da aula leva para "Sem aula" (com a nota); só lá dá para apagar de vez
            favorito: f.id, textoRemover: aula ? "Tirar da aula" : "Apagar frase", confirmar: !aula,
            remover: aula ? async () => {
              await api("mover_frase", f.id, SEM_AULA);
              avisar("A frase foi para “Sem aula” (com a nota).");
            } : null,
            extras: [el("div", { class: "extras-aula" }, campoNota(f), campoMover(f, () => cartao))],
          });
          return cartao;
        }))
        : estadoVazio("Nenhuma frase aqui ainda.", "Na tela Buscar, escolha a aula em “Guardar frases na aula” e clique em Guardar nos resultados."));
  } catch (e) { erroEm(alvo, e); }
}

export function iniciarAulas() {
  trocar($("#nova-aula"), campoNome({
    rotulo: "Nova aula", placeholder: "Nome da aula", salvar: "Criar", classe: "btn btn-primario btn-largo",
    aoSalvar: async (nome) => {
      const aula = await api("criar_aula", nome);
      await recarregarAulas();
      abrir(aula.id);
    },
  }));
  ouvir("aulas-mudaram", desenharLista);
  ouvir("aba-aberta", async (aba) => {
    if (aba !== "aulas") return;
    await recarregarAulas();
    if (naFolha && aberta !== undefined && (aberta === SEM_AULA || aulaPorId(aberta))) return; // a folha continua
    // abre a aula que a cliente está montando (a de "Guardar frases na aula"); sem ela, a última vista
    if (estado.aulaDestino !== null && aulaPorId(estado.aulaDestino)) return abrir(estado.aulaDestino);
    const ainda = aberta === SEM_AULA || (aberta !== undefined && aulaPorId(aberta));
    abrir(ainda ? aberta : (estado.aulas[0]?.id ?? SEM_AULA));
  });
}
