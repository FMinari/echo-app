// Ícones da interface, em SVG próprio (traço da cor do texto). Emoji e símbolos de texto (☆ ↑ × «)
// mudam de cara em cada sistema, são lidos de forma estranha pelo leitor de tela e denunciam
// interface gerada às pressas; aqui fica um desenho só para cada ícone.

const CAMINHOS = {
  estrela: '<path d="M12 3.6l2.5 5.2 5.7.8-4.1 4 1 5.7L12 16.6l-5.1 2.7 1-5.7-4.1-4 5.7-.8z"/>',
  cima: '<path d="m6 15 6-6 6 6"/>',
  baixo: '<path d="m6 9 6 6 6-6"/>',
  esquerda: '<path d="m15 6-6 6 6 6"/>',
  direita: '<path d="m9 6 6 6-6 6"/>',
  primeira: '<path d="m17 6-6 6 6 6"/><path d="M7 6v12"/>',
  ultima: '<path d="m7 6 6 6-6 6"/><path d="M17 6v12"/>',
  fechar: '<path d="M6 6l12 12M18 6 6 18"/>',
  busca: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  mais: '<path d="M12 5v14M5 12h14"/>',
  som: '<path d="M11 5 6 9H3v6h3l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M18.5 5.5a9 9 0 0 1 0 13"/>',
  baixar: '<path d="M12 4v11"/><path d="m7 10 5 5 5-5"/><path d="M5 20h14"/>',
  parar: '<rect x="7" y="7" width="10" height="10" rx="1.5"/>',
};

/**
 * @param {keyof CAMINHOS} nome
 * @param {object} [op]
 * @param {boolean} [op.cheio]  preenchido com a cor do texto (ex.: estrela de "Guardada")
 */
export function icone(nome, { cheio = false } = {}) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("class", cheio ? "icone icone-cheio" : "icone");
  svg.innerHTML = CAMINHOS[nome];
  return svg;
}
