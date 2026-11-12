// Tela Sobre: estado do app, contato, atualizar, versões do GitHub, novidades e desinstalar.
import { api } from "../lib/ponte.js";
import { $, el, esperar, trocar } from "../lib/dom.js";
import { dataBr, plural } from "../lib/formato.js";
import { TIPOS } from "../lib/tipos.js";
import { ouvir } from "../lib/eventos.js";
import { avisarErro, botaoPastaErros, erroEm } from "../componentes/avisos.js";
import { botaoConfirmar } from "../componentes/confirmacao.js";
import { interruptor } from "../componentes/interruptor.js";
import { alternador } from "../componentes/alternador.js";
import { criarSeletor } from "../componentes/seletor.js";
import { escolherVelocidade, escolherVoz, esperarVozes, falar, VELOCIDADES, velocidadeEscolhida, vozEscolhida } from "../lib/voz.js";
import { recolhivel } from "../componentes/recolhivel.js";
import { carregando as silhueta, esqueletoCartaoSobre, esqueletoLinhas } from "../componentes/esqueleto.js";
import { abrirAba } from "./abas.js";
import { escolherAtualizacao, mostrarAtualizacao, MSG_TOKEN, verAtualizacao } from "./atualizacao.js";

let carregando = Promise.resolve();

const cartao = (id, titulo, ...conteudo) => el("section", { class: "cartao-sobre", id }, el("h2", { text: titulo }), ...conteudo);
const linha = (rotulo, ...valor) => el("div", { class: "linha-sobre" }, el("dt", { text: rotulo }), el("dd", {}, ...valor));
const ajuda = (texto) => el("p", { class: "ajuda-sobre", text: texto });

function cartaoEstado(s) {
  const b = s.banco;
  return cartao(null, "Estado do app",
    el("dl", {},
      linha("Versão do app", el("b", { text: s.app.numero }), el("small", { text: s.app.versao })),
      linha("Banco de frases", el("b", { text: b.rotulo }),
        el("small", { text: `${b.series} séries · ${b.filmes} filmes${b.musicas ? ` · ${plural(b.musicas, "música")}` : ""}`
          + TIPOS.slice(3).filter((x) => b.tipos?.[x.chave]).map((x) => ` · ${plural(b.tipos[x.chave], x.um, x.pluralUm)}`).join("")
          + ` · ${b.frases.toLocaleString("pt-BR")} frases` })),
      linha("Seus dados", el("span", { text: s.dados })),
      linha("Última cópia de segurança", el("span", { text: s.ultimo_backup ? dataBr(s.ultimo_backup) : "ainda nenhuma (é feita ao abrir o app)" })),
      s.dicionario ? link("Dicionário", s.dicionario.url, `${s.dicionario.nome} (${s.dicionario.licenca})`) : null),
    botaoPastaErros());
}

// e-mail e páginas abrem no programa padrão do sistema, fora da janela do app
function link(rotulo, url, texto) {
  return linha(rotulo, el("a", { href: url, text: texto, onclick: (ev) => { ev.preventDefault(); api("abrir_link", url).catch(avisarErro); } }));
}

function cartaoContato(c) {
  if (!c || !Object.keys(c).length) return null;
  return cartao("contato", "Contato",
    c.mensagem ? ajuda(c.mensagem) : null,
    el("dl", {},
      c.nome ? linha("Nome", c.nome) : null,
      c.email ? link("E-mail", `mailto:${c.email}?subject=${encodeURIComponent("Echo")}`, c.email) : null,
      c.whatsapp ? link("WhatsApp", `https://wa.me/${String(c.whatsapp).replace(/\D/g, "")}`, c.whatsapp) : null,
      c.github ? link("GitHub", c.github, c.github.replace("https://", "")) : null));
}

function cartaoAtualizar() {
  return cartao(null, "Atualizar",
    ajuda("O app procura versões novas sozinho quando abre (pela internet e nos seus Downloads) e avisa lá em cima. Se recebeu um arquivo de atualização que está em outro lugar, escolha aqui."),
    ajuda("Um banco de frases feito com os seus próprios textos (corpus.db) também entra por aqui. Importe só textos de sua autoria ou que você tenha direito de usar. O Echo não fornece conteúdo protegido e não se responsabiliza pelo que for importado nem pelo uso dos trechos fora de fins didáticos."),
    el("div", { class: "botoes" },
      el("button", { type: "button", class: "btn", text: "Procurar atualização", onclick: () => verAtualizacao(true) }),
      el("button", { type: "button", class: "btn", text: "Escolher arquivo…", onclick: escolherAtualizacao })));
}

/**
 * O que mudou numa versão. A instalada fica aberta e fixa ("a sua"); as outras, recolhidas.
 * @param {object} op
 * @param {boolean} [op.atual]   é a versão instalada
 * @param {Node} [op.acoes]      botões no fim (ex.: "Usar esta versão")
 */
function novidade(versao, data, itens, { atual = false, acoes = null } = {}) {
  const lista = itens.length ? el("ul", {}, itens.map((i) => el("li", { text: i }))) : null;
  if (atual) {
    return el("article", { class: "novidade novidade-atual" },
      el("h3", {}, `Versão ${versao}`, el("small", { text: data ? dataBr(data) : "" }),
        el("span", { class: "versao-atual", text: "a sua" })),
      lista, acoes);
  }
  return recolhivel({ titulo: `Versão ${versao}`, detalhe: data ? dataBr(data) : null, variante: "simples",
    aberto: false, classe: "novidade" }, lista, acoes);
}

// as 5 versões mais novas do GitHub + a mais nova da linha anterior, para voltar se precisar
async function preencherVersoes(caixaVersoes) {
  const titulo = el("h2", { text: "Versões" });
  const so = (texto) => trocar(caixaVersoes, titulo, ajuda(texto));
  try {
    const r = await api("versoes");
    if (!r.ligado) return so("Este app não está ligado ao GitHub: as atualizações chegam por arquivo.");
    if (r.situacao === "token_expirado") return so(MSG_TOKEN);
    if (!r.versoes.length) return so("Não consegui ver as versões agora (sem internet?). Tente de novo mais tarde.");
    trocar(caixaVersoes, titulo,
      ajuda("Se uma versão nova não ficou boa, dá para voltar para outra. Seus dados (estruturas, aulas, grupos) continuam."),
      r.versoes.map((p) => novidade(p.numero, p.data, p.novidades[0].itens.slice(0, 4), {
        atual: p.atual,
        acoes: p.atual ? null : el("div", { class: "botoes" },
          el("button", { type: "button", class: "btn", text: "Usar esta versão", onclick: () => mostrarAtualizacao(p) })),
      })));
  } catch {
    so("Não consegui ver as versões agora.");
  }
}

// a voz do "Ouvir" dos cartões e a velocidade (devagar serve para ditado)
async function preencherVoz(caixa) {
  const titulo = el("h2", { text: "Voz das frases" });
  const vozes = await esperarVozes();
  if (!vozes.length) {
    return trocar(caixa, titulo, ajuda("Este computador não tem voz em inglês. No Windows: Configurações › Hora e idioma › Fala › Adicionar vozes, e escolha uma em inglês. Depois, feche e abra o app."));
  }
  const alvo = el("div");
  trocar(caixa, titulo,
    ajuda("A voz que lê as frases quando você clica em “Ouvir”. As que dizem “Online” soam mais naturais, mas só funcionam com internet."),
    ajuda("“Salvar áudio” grava a frase num arquivo em Músicas › Echo, com esta voz e esta velocidade. As vozes “Online” não dão para gravar: aí vai uma voz em inglês do Windows."),
    el("div", { class: "campo" }, el("span", { text: "Voz" }), alvo),
    el("div", { class: "campo" }, el("span", { text: "Velocidade" }), alternador({
      opcoes: VELOCIDADES.map(({ valor, rotulo }) => ({ valor, rotulo })), valor: velocidadeEscolhida(),
      rotulo: "Velocidade da voz", aoMudar: escolherVelocidade,
    })),
    el("div", { class: "botoes" }, el("button", { type: "button", class: "btn", text: "Testar a voz",
      onclick: () => falar("If I had known you were coming, I would have baked a cake.") })));
  const seletor = criarSeletor(alvo, { placeholder: "A voz padrão", busca: "Procurar voz…", vazio: "Nenhuma voz com esse nome", aoMudar: escolherVoz });
  seletor.definirItens(vozes.map((v) => ({ valor: v.name, rotulo: v.name, secundario: `${v.lang} · ${v.localService ? "sem internet" : "precisa de internet"}` })));
  seletor.valor = vozEscolhida();
}

// o que sai, a escolha de apagar os dados e a confirmação em dois cliques; depois o app fecha
async function preencherDesinstalar(caixa) {
  const titulo = el("h2", { text: "Desinstalar" });
  try {
    const p = await api("plano_desinstalar");
    if (!p.pode) return trocar(caixa, titulo, ajuda(p.motivo));
    const apagarDados = interruptor({
      rotulo: "Apagar também minhas estruturas, aulas e grupos",
      detalhe: `Ficam em ${p.dados}. Deixando desligado, eles continuam lá para quando instalar de novo.`,
      ligado: false,
    });
    trocar(caixa, titulo,
      ajuda(`Tira o Echo deste computador: os atalhos, o tipo de arquivo .sitcomatica e a pasta do app (${p.raiz}).`),
      apagarDados,
      el("div", { class: "botoes" }, botaoConfirmar({
        texto: "Desinstalar o Echo", pergunta: "Clique de novo para desinstalar", class: "btn btn-perigo",
        aoConfirmar: async () => {
          try {
            await api("desinstalar", apagarDados.ligado);
            trocar(caixa, titulo, el("p", { text: "Echo desinstalado. Esta janela vai fechar; se não fechar, pode fechar você." }));
            setTimeout(() => window.close(), 1500);
          } catch (e) { avisarErro(e); }
        },
      })));
  } catch (e) { erroEm(caixa, e); }
}

async function carregar() {
  const alvo = $("#conteudo-sobre");
  if (!alvo.children.length) trocar(alvo, silhueta("Carregando…", esqueletoCartaoSobre(4), esqueletoCartaoSobre(3), esqueletoCartaoSobre(2)));
  try {
    const s = await api("sobre");
    const versoes = cartao("versoes", "Versões", silhueta("Procurando as versões no GitHub…", esqueletoLinhas(["55%", "80%", "70%"])));
    const desinstalarCartao = cartao("desinstalar", "Desinstalar", esqueletoLinhas(["70%", "50%"]));
    const vozCartao = cartao("voz", "Voz das frases", esqueletoLinhas(["70%", "50%"]));
    trocar(alvo,
      cartaoEstado(s),
      cartaoContato(s.contato),
      cartaoAtualizar(),
      cartao(null, "Uso dos trechos",
        ajuda("Os trechos são para uso didático: cite a obra de onde vieram e não revenda o material.")),
      vozCartao,
      versoes,
      cartao(null, "Novidades", s.novidades.length
        ? s.novidades.map((n) => novidade(n.versao, n.data, n.itens, { atual: n.versao === s.app.numero }))
        : el("p", { text: "Sem notas de versão." })),
      desinstalarCartao);
    preencherVersoes(versoes);
    preencherDesinstalar(desinstalarCartao);
    preencherVoz(vozCartao);
  } catch (e) { erroEm(alvo, e); }
}

async function irParaContato() {
  abrirAba("sobre");
  await carregando;
  for (let i = 0; i < 20 && !$("#contato"); i++) await esperar(100);
  $("#contato")?.scrollIntoView({ block: "start", behavior: "smooth" });
}

export function iniciarSobre() {
  ouvir("aba-aberta", (aba) => { if (aba === "sobre") carregando = carregar(); });
  ouvir("ir-para-contato", irParaContato);
}
