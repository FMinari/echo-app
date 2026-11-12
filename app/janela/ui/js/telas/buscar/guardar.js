// "Guardar como estrutura" no resultado da busca escrita: nome e categoria, e a busca vira uma estrutura
// do catálogo (aba Estruturas), que depois se busca do jeito normal.
import { api } from "../../lib/ponte.js";
import { el, trocar } from "../../lib/dom.js";
import { estado } from "../../estado.js";
import { avisarErro } from "../../componentes/avisos.js";
import { criarSeletor } from "../../componentes/seletor.js";
import { recarregar } from "../estruturas/index.js";

const CATEGORIA_PADRAO = "Minhas buscas";

/**
 * @param {{texto: string, outras_formas: boolean, tempo: string|null}} params  a busca escrita mostrada
 * @returns {HTMLElement}
 */
export function guardarBusca(params) {
  const caixa = el("div", { class: "guardar-busca" });

  const fechar = () => trocar(caixa,
    el("button", { type: "button", class: "btn-link", text: "Guardar como estrutura", onclick: abrir }));

  function abrir() {
    const nome = el("input", { type: "text", value: params.texto, "aria-label": "Nome da estrutura", maxlength: 80 });
    const campoCategoria = el("div");
    let categoria; // o seletor troca o campoCategoria no lugar: só dá para criar com o formulário na tela

    const salvar = el("button", { type: "button", class: "btn btn-primario btn-pequeno", text: "Guardar" });
    salvar.addEventListener("click", async () => {
      salvar.disabled = true;
      salvar.textContent = "Guardando…";
      try {
        const e = await api("guardar_busca", { ...params, nome: nome.value, categoria: categoria.valor });
        await recarregar();
        trocar(caixa, el("p", { class: "ajuda", text: `Guardada em Estruturas, na categoria “${e.categoria}”, com o nome “${e.nome}”.` }));
      } catch (erro) {
        avisarErro(erro);
        salvar.disabled = false;
        salvar.textContent = "Guardar";
      }
    });

    trocar(caixa, el("div", { class: "guardar-form" },
      el("label", { class: "campo" }, el("span", { text: "Nome da estrutura" }), nome),
      el("div", { class: "campo" }, el("span", { text: "Categoria" }), campoCategoria),
      el("div", { class: "botoes" }, salvar,
        el("button", { type: "button", class: "btn btn-pequeno", text: "Cancelar", onclick: fechar }))));
    categoria = criarSeletor(campoCategoria, { busca: "Procurar categoria…", vazio: "Nenhuma com esse nome" });
    const categorias = new Set([CATEGORIA_PADRAO, ...estado.estruturas.map((e) => e.categoria).filter(Boolean)]);
    categoria.definirItens([...categorias].map((c) => ({ valor: c, rotulo: c })));
    categoria.valor = CATEGORIA_PADRAO;
    nome.focus();
    nome.select();
  }

  fechar();
  return caixa;
}
