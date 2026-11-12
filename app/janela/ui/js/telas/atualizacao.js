// Atualizações: o aviso no topo quando há versão nova (Downloads, arquivo aberto com dois cliques ou
// GitHub), instalar (baixando do GitHub com barra de progresso), voltar de versão e o aviso de token
// vencido.
import { api, enviarArquivo } from "../lib/ponte.js";
import { $, el, esperar, trocar } from "../lib/dom.js";
import { guardar, lembrar } from "../lib/armazenamento.js";
import { emitir } from "../lib/eventos.js";
import { compararVersoes, mb } from "../lib/formato.js";
import { estado } from "../estado.js";
import { avisarErro, erroEm } from "../componentes/avisos.js";
import { mostrarProgresso } from "../componentes/progresso.js";

export const MSG_TOKEN = "Token de acesso às atualizações expirou, para um novo token, favor entrar em contato na seção \"Contato\"";

// "Agora não" vale para aquele arquivo
const chaveDispensa = (p) => `atualizacao-dispensada:${p.arquivo}|${p.modificado || ""}`;
const caixa = () => $("#aviso-atualizacao");
const ehVoltar = (p) => p.mais_novo === false && p.tipo === "app" && compararVersoes(p.numero, estado.versaoApp) < 0;

function descrever(p) {
  if (p.tipo !== "app") return `banco de frases de ${p.rotulo}`;
  return `Echo ${p.numero}${p.com_banco ? " (com banco de frases)" : ""}`;
}

function titulo(p) {
  if (p.mais_novo !== false) return `Atualização encontrada: ${descrever(p)}`;
  if (ehVoltar(p)) return `Voltar para a versão ${p.numero}? (a sua é a ${estado.versaoApp}; seus dados continuam)`;
  return `${descrever(p)}: é a mesma versão que já está instalada (dá para reinstalar).`;
}

function origem(p) {
  if (p.origem !== "github") return p.arquivo;
  return `do GitHub${p.com_banco ? ` · com o banco de frases (${Math.round(p.asset.tamanho / 1e6)} MB)` : ""}`;
}

/** Mostra o aviso no topo para o pacote `p` (com Instalar/Voltar e Agora não). */
export function mostrarAtualizacao(p) {
  const aviso = caixa();
  const novidades = (p.novidades || []).flatMap((n) => n.itens).slice(0, 6);
  trocar(aviso,
    el("div", { class: "atualizacao-titulo" }, el("b", { text: titulo(p) }), el("small", { text: origem(p) })),
    novidades.length ? el("ul", {}, novidades.map((i) => el("li", { text: i }))) : null,
    el("div", { class: "botoes" },
      el("button", { type: "button", class: "btn btn-primario", text: ehVoltar(p) ? "Voltar para esta versão" : "Instalar agora", onclick: () => instalar(p) }),
      el("button", { type: "button", class: "btn", text: "Agora não", onclick: () => { guardar(chaveDispensa(p), true); aviso.hidden = true; } })));
  aviso.hidden = false;
  window.scrollTo(0, 0);
}

// Versão do GitHub: o Python baixa numa thread e aqui só acompanha. Devolve o caminho do arquivo.
async function baixarDoGitHub(p, aviso) {
  const barra = el("progress", { max: "100", value: "0" });
  const texto = el("p", { class: "carregando", text: "Baixando…" });
  trocar(aviso, texto, barra);
  await api("baixar_atualizacao", p);
  for (;;) {
    await esperar(400);
    const d = await api("progresso_download");
    if (d.erro) throw Object.assign(new Error(d.erro), { daApi: true });
    if (d.arquivo) return d.arquivo;
    const pct = d.total ? Math.floor((d.feito / d.total) * 100) : 0;
    barra.value = pct;
    texto.textContent = `Baixando… ${pct}%${d.total ? ` (${mb(d.feito)} de ${mb(d.total)} MB)` : ""}`;
  }
}

async function instalar(p) {
  const aviso = caixa();
  aviso.hidden = false;
  window.scrollTo(0, 0);
  try {
    const arquivo = p.origem === "github" ? await baixarDoGitHub(p, aviso) : p.arquivo;
    trocar(aviso, el("p", { class: "carregando", text: "Atualizando… não feche o app." }));
    const r = await api("aplicar_atualizacao", arquivo);
    if (r.tipo === "banco") {
      trocar(aviso, el("p", { text: "Banco de frases atualizado! Recarregando…" }));
      setTimeout(() => location.reload(), 1200);
      return;
    }
    trocar(aviso, el("p", { text: `Pronto, versão ${r.numero} instalada! Reabrindo…` }));
    const re = await api("reiniciar");
    if (re.sem_janela) return;
    // a janela nova abre sozinha; esta se fecha (se o Windows não deixar, fica o aviso)
    setTimeout(() => {
      trocar(aviso, el("p", { text: "Pronto! A versão nova abriu em outra janela. Pode fechar esta." }));
      window.close();
    }, 2500);
  } catch (e) {
    erroEm(aviso, e);
    aviso.append(el("button", { type: "button", class: "btn", text: "Fechar", onclick: () => { aviso.hidden = true; } }));
  }
}

/** Procura atualização (Downloads, arquivo aberto, GitHub). `manual`: avisa também quando não há. */
// o que dizer quando não veio versão nova, pela situação da última consulta ao GitHub
const SEM_NOVIDADE = {
  offline: "Sem internet: não deu para procurar atualizações agora.",
  erro: "Não deu para procurar atualizações agora. Tento de novo mais tarde.",
  token_expirado: null, // o aviso fixo do token já explica
};

export async function verAtualizacao(manual = false) {
  const progresso = mostrarProgresso("Procurando atualizações…");
  try {
    const p = await api("procurar_atualizacao");
    if (!p) {
      const g = await api("estado_github").catch(() => ({}));
      const texto = g.situacao in SEM_NOVIDADE ? SEM_NOVIDADE[g.situacao] : `Você já está na versão mais nova (${estado.versaoApp}).`;
      progresso.terminar(texto);
      return;
    }
    if (!manual && lembrar(chaveDispensa(p), false)) {
      progresso.terminar(); // a cliente já disse "Agora não" para esta: não insiste
      return;
    }
    progresso.terminar();
    mostrarAtualizacao(p);
  } catch (e) {
    progresso.terminar();
    if (manual) avisarErro(e);
  }
}

export const A_CADA_MS = 3 * 60 * 60 * 1000;   // com o app aberto, pergunta de novo a cada 3 horas
export const VOLTOU_DEPOIS_MS = 30 * 60 * 1000; // e quando a cliente volta para a janela depois de 30 minutos fora
let ultimaVez = Date.now();

/** Com o app aberto o dia todo, a versão nova também aparece sozinha (sem a cliente precisar reabrir). Não
 * pergunta se o aviso já está na tela; o "Agora não" da cliente continua valendo para aquela versão. */
export function vigiarAtualizacoes() {
  const procurar = () => {
    if (!caixa().hidden) return;
    ultimaVez = Date.now();
    verAtualizacao();
  };
  setInterval(procurar, A_CADA_MS);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && Date.now() - ultimaVez > VOLTOU_DEPOIS_MS) procurar();
  });
}

/** "Escolher arquivo…" na aba Sobre: o arquivo vai para o Python, que diz o que ele é. */
export function escolherAtualizacao() {
  const campo = el("input", { type: "file", accept: ".sitcomatica,.zip,.db", hidden: true });
  campo.addEventListener("change", async () => {
    const arquivo = campo.files[0];
    campo.remove();
    if (!arquivo) return;
    const progresso = mostrarProgresso(`Lendo ${arquivo.name}…`);
    try {
      const p = await enviarArquivo("enviar_atualizacao", arquivo);
      progresso.terminar();
      mostrarAtualizacao(p);
    } catch (e) {
      progresso.terminar();
      avisarErro(e);
    }
  });
  document.body.append(campo);
  campo.click();
}

/** Token do GitHub vencido: aviso fixo no topo com o caminho para o Contato. */
export async function verificarToken() {
  try {
    const g = await api("estado_github");
    if (g.situacao !== "token_expirado") return;
    const aviso = $("#aviso-token");
    trocar(aviso,
      el("p", {}, el("b", { text: MSG_TOKEN })),
      el("div", { class: "botoes" },
        el("button", { type: "button", class: "btn btn-primario", text: "Ir para Contato", onclick: () => emitir("ir-para-contato") })));
    aviso.hidden = false;
  } catch { /* sem GitHub: nada a avisar */ }
}
