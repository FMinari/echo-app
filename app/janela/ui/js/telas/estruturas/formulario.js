// Formulário de uma estrutura (nova ou existente): nome, categoria, nível, regra montada com peças
// (+ Testar), fórmula, explicação, frases-modelo, pegadinhas e a regra avançada.
import { api } from "../../lib/ponte.js";
import { $, el, trocar } from "../../lib/dom.js";
import { plural } from "../../lib/formato.js";
import { estado } from "../../estado.js";
import { avisar, avisarErro, erroEm } from "../../componentes/avisos.js";
import { botaoConfirmar } from "../../componentes/confirmacao.js";
import { carregando, esqueletoLinhas } from "../../componentes/esqueleto.js";
import { recolhivel } from "../../componentes/recolhivel.js";
import { fraseDestacada } from "../../componentes/cartao-frase.js";
import { montadorDePecas } from "../../componentes/montador-pecas.js";

const NIVEIS = ["A1", "A2", "B1", "B2", "C1", "C2"];
const NOVA_CATEGORIA = "__nova__";
const ORIGEM = {
  semente: "veio pronta com o app",
  semente_editada: "veio pronta com o app (você editou)",
  usuario: "criada por você",
  busca: "guardada de uma busca escrita",
  claude: "criada com o Claude",
};

function campo(e, rotulo, nome, tipo = "input", extra = {}) {
  return el("label", { class: "campo" },
    el("span", { text: rotulo }),
    tipo === "textarea" ? el("textarea", { name: nome, ...extra }, e[nome] || "") : el("input", { name: nome, value: e[nome] || "", ...extra }));
}

// escolhe uma categoria que já existe ou cria outra (o Python ainda junta "Tempos Verbais" com "Tempos verbais")
function campoCategoria(e) {
  const categorias = [...new Set(estado.estruturas.map((x) => x.categoria).filter(Boolean))].sort((a, b) => a.localeCompare(b, "pt"));
  const lista = el("select", { name: "categoria" },
    el("option", { value: "", text: "Sem categoria" }),
    categorias.map((c) => el("option", { value: c, text: c, selected: e.categoria === c })),
    el("option", { value: NOVA_CATEGORIA, text: "Nova categoria…" }));
  const nova = el("input", { name: "categoria_nova", placeholder: "Nome da categoria nova", hidden: true });
  lista.addEventListener("change", () => {
    nova.hidden = lista.value !== NOVA_CATEGORIA;
    if (!nova.hidden) nova.focus();
  });
  return el("label", { class: "campo" }, el("span", { text: "Categoria" }), lista, nova);
}

function campoNivel(e) {
  return el("label", { class: "campo" }, el("span", { text: "Nível" }),
    el("select", { name: "nivel" }, el("option", { value: "", text: "Sem nível" }),
      NIVEIS.map((n) => el("option", { value: n, text: n, selected: e.nivel === n }))));
}

/**
 * Desenha o formulário em `alvo`.
 * @param {HTMLElement} alvo
 * @param {object} e  a estrutura ({} para nova)
 * @param {object} op
 * @param {(id: number) => Promise<void>} op.aoSalvar   depois de salvar (recarrega e reabre)
 * @param {() => Promise<void>} op.aoApagar             depois de apagar
 * @param {(id: number) => void} op.aoBuscar            "Buscar exemplos"
 */
export function formularioDeEstrutura(alvo, e, { aoSalvar, aoApagar, aoBuscar }) {
  const novo = !e.id;
  const amostra = el("div", { class: "amostra" });
  const textoSalvar = novo ? "Criar estrutura" : "Salvar";
  const botaoSalvar = el("button", { type: "submit", class: "btn btn-primario", text: textoSalvar });

  // regra avançada: desligada enquanto houver peças (aí ela é gerada a partir delas)
  const avancados = [
    campo(e, "Padrão", "padrao", "input", { class: "mono" }),
    campo(e, "Texto (regex)", "texto", "input", { class: "mono" }),
    campo(e, "Excluir (regex)", "excluir", "input", { class: "mono" }),
  ];
  const avisoAvancado = el("p", { class: "ajuda", text: "Com peças montadas, a regra avançada é gerada a partir delas." });
  const montador = montadorDePecas(e, estado.pecas, (temPecas) => {
    for (const c of avancados) $("input", c).disabled = temPecas;
    avisoAvancado.hidden = !temPecas;
  });

  const form = el("form", { class: "detalhe-form", onsubmit: (ev) => { ev.preventDefault(); salvar(); } },
    el("div", { class: "grade" }, campo(e, "Nome", "nome", "input", { required: true }), campoCategoria(e), campoNivel(e)),
    montador.raiz,
    el("div", { class: "botoes" }, el("button", { type: "button", class: "btn", text: "Testar", onclick: testar })),
    amostra,
    campo(e, "Fórmula", "formula", "input", { placeholder: "ex.: If + past perfect, would have + particípio" }),
    campo(e, "Explicação", "explicacao", "textarea"),
    el("label", { class: "campo" }, el("span", { text: "Frases-modelo (uma por linha)" }),
      el("textarea", { name: "exemplos" }, (e.exemplos || []).join("\n"))),
    campo(e, "Pegadinhas", "pegadinhas", "textarea"),
    recolhivel({ titulo: "Regra avançada", variante: "simples", aberto: false, classe: "avancado" },
      avisoAvancado,
      el("p", { class: "ajuda" },
        "Cada [ ] é uma palavra: ", el("code", { text: "[l=have t=VBD] [t=RB]* [t=VBN]" }),
        " = had + advérbio opcional + particípio. ", el("code", { text: "..." }), " pula palavras."),
      avancados[0],
      el("div", { class: "grade" }, avancados[1], avancados[2], el("span"))),
    // presa no rodapé: o formulário é comprido e o Salvar não pode ficar escondido lá no fim
    el("div", { class: "botoes barra-acoes" },
      botaoSalvar,
      novo ? null : el("button", { type: "button", class: "btn", text: "Buscar exemplos", onclick: () => aoBuscar(e.id) }),
      novo ? null : botaoConfirmar({ texto: "Apagar", pergunta: "Apagar de vez?", class: "btn btn-perigo", aoConfirmar: apagar })));
  montador.atualizar();

  function dados() {
    const d = Object.fromEntries(new FormData(form));
    d.blocos = montador.valor();
    if (d.categoria === NOVA_CATEGORIA) d.categoria = d.categoria_nova;
    delete d.categoria_nova;
    return d;
  }
  async function salvar() {
    botaoSalvar.disabled = true;
    botaoSalvar.textContent = "Salvando…";
    try {
      const salvo = await api("salvar_estrutura", { ...dados(), id: e.id || null });
      avisar(novo ? "Estrutura criada." : "Alterações salvas.");
      await aoSalvar(salvo.id);
    } catch (err) {
      avisarErro(err);
      botaoSalvar.disabled = false;
      botaoSalvar.textContent = textoSalvar;
    }
  }
  async function testar() {
    trocar(amostra, carregando("Testando a regra…", esqueletoLinhas(["40%", "96%", "88%", "92%"], "amostra-esqueleto")));
    try {
      const r = await api("testar_regra", dados());
      trocar(amostra, el("b", { text: `${plural(r.total, "frase encontrada", "frases encontradas")}. Exemplos:` }),
        r.resultados.map((x) => el("p", {}, el("b", { text: `${x.falante || "?"}: ` }), fraseDestacada(x.frase, x.destaques))));
    } catch (err) { erroEm(amostra, err); }
  }
  async function apagar() {
    try {
      await api("apagar_estrutura", e.id);
      avisar("Estrutura apagada.");
      await aoApagar();
    } catch (err) { avisarErro(err); }
  }

  trocar(alvo,
    el("h2", { text: novo ? "Nova estrutura" : e.nome }),
    novo ? null : el("p", { class: "ajuda", text: ORIGEM[e.origem] || "" }),
    form);
}
