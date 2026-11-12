// Aulas: a lista (estado.aulas, recarregada quando uma frase muda) e a aula onde o "Guardar" dos
// resultados põe as frases (lembrada entre uma abertura e outra).
import { api } from "../../lib/ponte.js";
import { $ } from "../../lib/dom.js";
import { guardar, lembrar } from "../../lib/armazenamento.js";
import { emitir, ouvir } from "../../lib/eventos.js";
import { estado } from "../../estado.js";

estado.aulaDestino = lembrar("aula-destino", null);

export const aulaPorId = (id) => estado.aulas.find((a) => a.id === id) || null;

export function definirDestino(id) {
  estado.aulaDestino = id ?? null;
  guardar("aula-destino", estado.aulaDestino);
  emitir("destino-mudou");
}

/** Busca as aulas de novo, atualiza o "(12)" da aba e avisa as telas. */
export async function recarregarAulas() {
  try {
    const r = await api("aulas");
    estado.aulas = r.aulas;
    estado.semAula = r.sem_aula;
    estado.semAulaTextos = r.sem_aula_textos;
    const total = r.sem_aula + r.aulas.reduce((n, a) => n + a.frases, 0);
    $("#n-frases").textContent = total ? `(${total})` : "";
    if (estado.aulaDestino !== null && !aulaPorId(estado.aulaDestino)) definirDestino(null);
    emitir("aulas-mudaram");
  } catch { /* a contagem é só ajuda */ }
}

ouvir("frases-mudaram", recarregarAulas);
ouvir("textos-mudaram", recarregarAulas);
