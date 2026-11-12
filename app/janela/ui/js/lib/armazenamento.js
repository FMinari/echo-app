// Preferências da cliente no localStorage (aba, tema, última estrutura…). Pode não existir (modo privado):
// aí nada é lembrado, mas nada quebra.

export function guardar(chave, valor) {
  try {
    localStorage.setItem(chave, JSON.stringify(valor));
  } catch { /* sem armazenamento */ }
}

export function lembrar(chave, padrao) {
  try {
    const v = localStorage.getItem(chave);
    return v === null ? padrao : JSON.parse(v);
  } catch {
    return padrao;
  }
}
