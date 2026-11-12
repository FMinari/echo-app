// "Guardar frases na aula" na tela Buscar: escolhe a aula (ou cria uma) onde o "Guardar" de cada
// resultado põe a frase.
import { api } from "../../lib/ponte.js";
import { $, trocar } from "../../lib/dom.js";
import { plural } from "../../lib/formato.js";
import { ouvir } from "../../lib/eventos.js";
import { estado } from "../../estado.js";
import { avisar } from "../../componentes/avisos.js";
import { campoNome } from "../../componentes/campo-nome.js";
import { criarSeletor } from "../../componentes/seletor.js";
import { definirDestino, recarregarAulas } from "../aulas/dados.js";

export function iniciarDestino() {
  const seletor = criarSeletor($("#f-aula"), {
    todos: "Sem aula", busca: "Procurar aula…", vazio: "Nenhuma aula com esse nome",
    aoMudar: (v) => definirDestino(v === null ? null : Number(v)),
  });
  const pintar = () => {
    seletor.definirItens(estado.aulas.map((a) => ({ valor: a.id, rotulo: a.nome, secundario: plural(a.frases, "frase") })));
    seletor.valor = estado.aulaDestino;
  };
  ouvir("aulas-mudaram", pintar);
  ouvir("destino-mudou", () => { seletor.valor = estado.aulaDestino; });
  trocar($("#nova-aula-busca"), campoNome({
    rotulo: "Nova aula", placeholder: "Nome da aula", salvar: "Criar",
    aoSalvar: async (nome) => {
      const aula = await api("criar_aula", nome);
      await recarregarAulas();
      definirDestino(aula.id);
      avisar(`Aula “${aula.nome}” criada. O “Guardar” dos resultados põe as frases nela.`);
    },
  }));
}
