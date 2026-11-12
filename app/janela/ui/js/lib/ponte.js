// Ponte com o Python (janela/app.py): cada método da classe `Api` vira POST /api/<método>, com a
// senha da sessão, que chega no endereço da janela (?t=…) e vai num cabeçalho próprio.

const SENHA = new URLSearchParams(location.search).get("t") || "";
// cada janela (e cada recarregar) tem um nome: o app só fecha quando nenhuma janela dá sinal
const JANELA = Math.random().toString(36).slice(2) + Date.now().toString(36);
const CABECALHO = { "X-Sitcomatica": SENHA, "X-Janela": JANELA };

async function resposta(r) {
  if (!r.ok) {
    throw Object.assign(new Error(r.status === 403
      ? "Esta janela perdeu a ligação com o app. Feche e abra o Echo de novo."
      : "O app parou de responder. Feche e abra o Echo de novo."), { daApi: true });
  }
  const dados = await r.json();
  if (dados?.erro) throw Object.assign(new Error(dados.erro), { daApi: true, inesperado: !!dados.inesperado });
  return dados;
}

/**
 * Chama um método da classe `Api` (janela/app.py). Erro do Python vira exceção com:
 * `daApi` (a mensagem já foi escrita para a cliente) e `inesperado` (foi para o log: vale oferecer a pasta de erros).
 */
export async function api(metodo, ...args) {
  let r;
  try {
    r = await fetch(`/api/${metodo}`, { method: "POST", headers: CABECALHO, body: JSON.stringify(args) });
  } catch {
    throw Object.assign(new Error("O app fechou. Abra o Echo de novo pelo ícone."), { daApi: true });
  }
  return resposta(r);
}

/** Manda um arquivo escolhido na tela para o Python (que grava e devolve o que é). */
export async function enviarArquivo(metodo, arquivo) {
  const r = await fetch(`/api/${metodo}`, {
    method: "POST", body: arquivo,
    headers: { ...CABECALHO, "X-Nome": encodeURIComponent(arquivo.name), "Content-Type": "application/octet-stream" },
  });
  return resposta(r);
}

/**
 * Avisa o Python de tempos em tempos que a janela está aberta: sem aviso, o app fecha sozinho. Ao
 * fechar a janela, avisa na hora (se for só um recarregar, o aviso seguinte chega antes de fechar).
 */
export function manterAberto() {
  setInterval(() => fetch("/api/sinal", { method: "POST", headers: CABECALHO }).catch(() => {}), 20000);
  addEventListener("pagehide", () => navigator.sendBeacon(`/api/fechando?t=${encodeURIComponent(SENHA)}&j=${JANELA}`));
}

/**
 * Avisa que esta janela vai ficar um tempo sem dar sinal (a impressão do Edge trava a página enquanto o
 * diálogo está aberto). `segundos = 0` volta ao normal.
 */
export function pausarSinal(segundos) {
  return fetch("/api/sinal", { method: "POST", headers: CABECALHO, body: JSON.stringify([{ pausa: segundos }]) }).catch(() => {});
}
