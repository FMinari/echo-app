// Textos e números para a tela.

/** "2026-10-07" -> "07/10/2026". */
export function dataBr(iso) {
  const [a, m, d] = String(iso).split("-");
  return d ? `${d}/${m}/${a}` : iso;
}

/** plural(1, "frase") -> "1 frase"; plural(3, "frase") -> "3 frases"; plural(2, "série", "séries"). */
export function plural(n, singular, pluralForma = `${singular}s`) {
  return `${n} ${n === 1 ? singular : pluralForma}`;
}

/** Compara versões "1.10" e "1.9" número a número (negativo, zero ou positivo). */
export function compararVersoes(a, b) {
  const pa = String(a).split(".").map(Number);
  const pb = String(b).split(".").map(Number);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    if ((pa[i] || 0) !== (pb[i] || 0)) return (pa[i] || 0) - (pb[i] || 0);
  }
  return 0;
}

/** Megabytes com uma casa: 1234567 -> "1.2". */
export const mb = (bytes) => (bytes / 1e6).toFixed(1);

/**
 * Os destaques ([[início, fim], ...]) vêm do Python contados em letras; o JS conta um emoji (🎶) como
 * duas. Converte para cortar a frase no lugar certo.
 */
export function destaquesNaFrase(frase, destaques) {
  if (!/[\uD800-\uDFFF]/.test(frase)) return destaques;
  const posicoes = [0];
  let u = 0;
  for (const letra of frase) posicoes.push((u += letra.length));
  return destaques.map(([a, b]) => [posicoes[a] ?? u, posicoes[b] ?? u]);
}
