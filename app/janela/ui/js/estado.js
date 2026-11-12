// Dados que várias telas leem, carregados no início (api "inicio") e atualizados por elas.

export const estado = {
  estruturas: [],
  obras: [],
  grupos: [],
  pecas: [],      // catálogo de peças para montar regras (nucleo/blocos.py)
  aulas: [],      // [{id, nome, frases, textos}] (api "aulas"; telas/aulas/dados.js)
  semAula: 0,     // frases guardadas fora de aula
  semAulaTextos: 0, // textos fora de aula
  aulaDestino: null, // aula onde o "Guardar" dos resultados põe as frases (null = Sem aula)
  versaoApp: "",
};

export const estruturaPorId = (id) => estado.estruturas.find((e) => String(e.id) === String(id));
export const obraPorId = (id) => estado.obras.find((o) => o.id === id);
