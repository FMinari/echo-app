// Os tipos de obra do corpus, na ordem das seções do resultado (a mesma de busca.TIPOS).
// `um` conta obras ("2 séries"; música conta artistas), `parte` conta o que tem dentro de cada uma.
export const TIPOS = [
  { chave: "serie", nome: "Séries", todos: "Todas as séries", um: "série", parte: "episódio", cor: "var(--destaque)" },
  { chave: "filme", nome: "Filmes", todos: "Todos os filmes", um: "filme", cor: "var(--destaque-2)" },
  { chave: "musica", nome: "Músicas", todos: "Todas as músicas", um: "artista", parte: "música", cor: "var(--texto-2)" },
  { chave: "livro", nome: "Livros", todos: "Todos os livros", um: "livro", parte: "capítulo", cor: "var(--destaque)" },
  { chave: "peca", nome: "Peças", todos: "Todas as peças", um: "peça", parte: "ato", cor: "var(--destaque-2)" },
  { chave: "conversa", nome: "Conversas reais", todos: "Todas as conversas reais", um: "conversa", parte: "parte", cor: "var(--texto-2)" },
  { chave: "frases", nome: "Frases soltas", todos: "Todas as frases soltas", um: "coleção", pluralUm: "coleções", parte: "bloco", cor: "var(--ok)" },
];

/** Tipos sem personagem: o cartão não diz "personagem não identificado". */
export const SEM_FALANTE = new Set(["livro", "frases"]);
