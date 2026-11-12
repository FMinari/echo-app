// Montagem de elementos sem framework.

export const $ = (seletor, raiz = document) => raiz.querySelector(seletor);
export const $$ = (seletor, raiz = document) => [...raiz.querySelectorAll(seletor)];

/**
 * Cria um elemento. `props`: `class`, `text`, `on<evento>` (ouvinte) e atributos comuns
 * (false/null/undefined não entram; true vira atributo vazio). Filhos: elementos, textos ou listas;
 * null e undefined são ignorados.
 */
export function el(tag, props = {}, ...filhos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") e.className = v;
    else if (k === "text") e.textContent = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null && v !== false) e.setAttribute(k, v === true ? "" : v);
  }
  for (const f of filhos.flat()) if (f !== null && f !== undefined) e.append(f);
  return e;
}

/**
 * Troca o conteúdo de `alvo`. Diferente de `replaceChildren`, ignora null/undefined
 * (que o navegador escreveria na tela como "null").
 */
export function trocar(alvo, ...filhos) {
  alvo.replaceChildren(...filhos.flat().filter((f) => f !== null && f !== undefined));
  return alvo;
}

/** Espera `ms` milissegundos. */
export const esperar = (ms) => new Promise((ok) => setTimeout(ok, ms));
