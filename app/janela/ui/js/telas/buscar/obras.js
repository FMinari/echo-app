// Escolha das séries, filmes e músicas da busca, com atalhos (todas as séries, todos os filmes, todas
// as músicas), grupos
// prontos e os grupos da cliente (salvar e apagar).
//
// No seletor, cada item é uma obra (valor = id) ou um atalho que vale várias:
// "t:serie"/"t:filme"/"t:musica" (todas de um tipo), "g:<nome>" (grupo pronto), "m:<id>" (grupo da cliente).
import { api } from "../../lib/ponte.js";
import { trocar } from "../../lib/dom.js";
import { guardar, lembrar } from "../../lib/armazenamento.js";
import { plural } from "../../lib/formato.js";
import { estado, obraPorId } from "../../estado.js";
import { avisar, avisarErro } from "../../componentes/avisos.js";
import { pedirConfirmacao } from "../../componentes/confirmacao.js";
import { campoNome } from "../../componentes/campo-nome.js";
import { criarMultiSeletor } from "../../componentes/seletor.js";
import { TIPOS } from "../../lib/tipos.js";

/** "2 séries + 3 filmes + 1 artista" */
function contarObras(ids) {
  const conta = (t) => ids.filter((id) => (obraPorId(id)?.tipo || "serie") === t).length;
  return TIPOS.map((t) => [t, conta(t.chave)]).filter(([, n]) => n)
    .map(([t, n]) => plural(n, t.um, t.pluralUm)).join(" + ");
}

function idsDe(valor) {
  const v = String(valor);
  if (TIPOS.some((t) => v === `t:${t.chave}`)) return estado.obras.filter((o) => o.tipo === v.slice(2)).map((o) => o.id);
  if (v.startsWith("m:")) return estado.grupos.find((g) => g.meu && String(g.id) === v.slice(2))?.obras || [];
  if (v.startsWith("g:")) return estado.grupos.find((g) => !g.meu && g.nome === v.slice(2))?.obras || [];
  return [Number(v)];
}

/**
 * @param {HTMLElement} alvo        onde entra o seletor
 * @param {HTMLElement} caixaGrupo  onde aparece "Salvar como grupo"
 * @param {object} op
 * @param {(ids: number[]) => void} op.aoMudar  ids das obras escolhidas, com os grupos já abertos
 */
export function escolhaDeObras(alvo, caixaGrupo, { aoMudar }) {
  const seletor = criarMultiSeletor(alvo, {
    busca: "Procurar série, filme ou artista…",
    vazio: (termo) => (termo ? "Nada com esse nome" : "Todas já estão escolhidas"),
    semEscolha: "Nenhuma escolhida: a busca vale para todas.",
    aoMudar: mudou,
  });

  const ids = () => [...new Set(seletor.valores.flatMap(idsDe))];

  function itens() {
    const doTipo = (t) => estado.obras.filter((o) => o.tipo === t);
    const lista = [];
    const atalhos = TIPOS.map((t) => [t.chave, t.todos]).filter(([t]) => doTipo(t).length);
    if (atalhos.length > 1) {
      for (const [t, rotulo] of atalhos) {
        const obras = doTipo(t);
        const secundario = t === "musica"
          ? `${plural(obras.reduce((n, o) => n + o.episodios, 0), "música")} de ${plural(obras.length, "artista")}`
          : contarObras(obras.map((o) => o.id));
        lista.push({ valor: `t:${t}`, rotulo, secundario, grupo: "Atalhos" });
      }
    }
    for (const g of estado.grupos.filter((g) => g.meu && g.obras.length)) {
      lista.push({
        valor: `m:${g.id}`, rotulo: g.nome, secundario: contarObras(g.obras), grupo: "Meus grupos",
        acao: { rotulo: "Apagar", titulo: `Apagar o grupo ${g.nome}`, aoClicar: (botao) => apagarGrupo(g, botao) },
      });
    }
    for (const g of estado.grupos.filter((g) => !g.meu && g.obras.length)) {
      lista.push({ valor: `g:${g.nome}`, rotulo: g.nome, secundario: contarObras(g.obras), grupo: "Grupos" });
    }
    const secundario = {
      serie: (o) => `série · ${o.episodios} episódios`,
      filme: (o) => `filme${o.ano ? ` · ${o.ano}` : ""}`,
      musica: (o) => plural(o.episodios, "música"),
    };
    for (const t of TIPOS) {
      for (const o of doTipo(t.chave)) {
        const outro = (x) => `${t.um} · ${plural(x.episodios, t.parte)}`;
        lista.push({ valor: o.id, rotulo: o.nome, grupo: t.nome, secundario: (secundario[t.chave] || outro)(o) });
      }
    }
    return lista;
  }

  function mudou(valores) {
    guardar("obras", valores);
    pintarSalvarGrupo();
    aoMudar(ids());
  }

  function pintarSalvarGrupo() {
    trocar(caixaGrupo);
    const escolhidas = ids();
    const valores = seletor.valores;
    // um grupo (ou atalho) sozinho já é um grupo
    if (escolhidas.length < 2 || (valores.length === 1 && !/^\d+$/.test(String(valores[0])))) return;
    caixaGrupo.append(campoNome({
      rotulo: "Salvar como grupo", placeholder: "Nome do grupo",
      aoSalvar: async (nome) => {
        estado.grupos = await api("criar_grupo", nome, escolhidas);
        const chave = nome.trim().replace(/\s+/g, " ").toLowerCase();
        const novo = estado.grupos.find((g) => g.meu && g.nome.toLowerCase() === chave);
        seletor.definirItens(itens());
        if (novo) seletor.valores = [`m:${novo.id}`];
        mudou(seletor.valores);
        avisar(`Grupo “${novo ? novo.nome : nome}” salvo. Ele aparece em “Meus grupos”.`);
      },
    }));
  }

  async function apagarGrupo(g, botao) {
    if (!pedirConfirmacao(botao, "Apagar")) return;
    try {
      estado.grupos = await api("apagar_grupo", g.id);
      seletor.definirItens(itens());
      mudou(seletor.valores);
      avisar(`Grupo “${g.nome}” apagado.`);
    } catch (e) { avisarErro(e); }
  }

  return {
    ids,
    /** Monta a lista com estado.obras/estado.grupos e volta a escolha da última vez. */
    preencher() {
      seletor.definirItens(itens());
      seletor.valores = lembrar("obras", []);
      mudou(seletor.valores);
    },
  };
}
