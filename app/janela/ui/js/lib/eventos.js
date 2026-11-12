// Canal de eventos entre as telas, para uma não precisar importar a outra.
//
// Eventos em uso:
//   aba-aberta          (nome)  uma aba foi mostrada
//   estruturas-mudaram  ()      o catálogo foi recarregado (estado.estruturas)
//   frases-mudaram      ()      guardou, tirou ou moveu uma frase (a lista de aulas recarrega)
//   aulas-mudaram       ()      a lista de aulas foi recarregada (estado.aulas)
//   destino-mudou       ()      mudou a aula onde o "Guardar" dos resultados põe as frases
//   buscar-estrutura    (id)    "Buscar exemplos" no catálogo: a busca escolhe e busca
//   ir-para-contato     ()      aviso de token: abrir Sobre na seção Contato

const ouvintes = new Map();

export function ouvir(nome, fn) {
  if (!ouvintes.has(nome)) ouvintes.set(nome, new Set());
  ouvintes.get(nome).add(fn);
  return () => ouvintes.get(nome).delete(fn);
}

export function emitir(nome, ...dados) {
  for (const fn of ouvintes.get(nome) || []) fn(...dados);
}
