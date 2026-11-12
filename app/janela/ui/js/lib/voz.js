// Ouvir a frase (ou o texto dela): as vozes em inglês que o Windows já tem, pelo próprio navegador (speechSynthesis), sem
// custo. Vozes "Online (Natural)" do Edge soam melhor, mas precisam de internet; as outras funcionam sem.
// A voz e a velocidade escolhidas na aba Sobre ficam lembradas.
import { guardar, lembrar } from "./armazenamento.js";

export const VELOCIDADES = [
  { valor: "normal", rotulo: "Normal", taxa: 1 },
  { valor: "devagar", rotulo: "Devagar", taxa: 0.8 },
  { valor: "bem-devagar", rotulo: "Bem devagar", taxa: 0.6 },
];
const temVoz = () => typeof speechSynthesis !== "undefined";

export function vozesEmIngles() {
  return temVoz() ? speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith("en")) : [];
}

/** As vozes chegam depois que a página abre: espera até 2 s por elas. */
export function esperarVozes() {
  if (!temVoz() || vozesEmIngles().length) return Promise.resolve(vozesEmIngles());
  return new Promise((ok) => {
    const fim = () => ok(vozesEmIngles());
    speechSynthesis.addEventListener("voiceschanged", fim, { once: true });
    setTimeout(fim, 2000);
  });
}

export const vozEscolhida = () => lembrar("voz-nome", null);
export const velocidadeEscolhida = () => lembrar("voz-velocidade", "normal");
export function escolherVoz(nome) { guardar("voz-nome", nome); }
export function escolherVelocidade(valor) { guardar("voz-velocidade", valor); }

/** A escolhida; senão uma americana que funciona sem internet; senão qualquer uma em inglês. */
function voz() {
  const vozes = vozesEmIngles();
  return vozes.find((v) => v.name === vozEscolhida())
    || vozes.find((v) => v.localService && v.lang === "en-US")
    || vozes.find((v) => v.lang === "en-US") || vozes[0] || null;
}

/** Nome da voz que o "Ouvir" usa e a velocidade: o "Salvar áudio" grava com a mesma, se ela for do Windows. */
export function vozDoOuvir() {
  // antes das vozes do Edge carregarem, vale a escolhida no Sobre
  return { voz: voz()?.name || vozEscolhida(), velocidade: velocidadeEscolhida() };
}

/**
 * O texto como a voz deve ler: cada parágrafo (separado por linha em branco) numa linha só, com ponto no fim
 * se a cliente não pôs (um título sem ponto ganha a pausa). O mesmo do `para_ler` do nucleo/audio.py, para o
 * "Ouvir" e o áudio salvo lerem igual.
 */
export function paraLer(corpo) {
  return String(corpo || "").split(/\n\s*\n/)
    .map((p) => p.split(/\s+/).filter(Boolean).join(" "))
    .filter(Boolean)
    .map((p) => (/[.!?;:…"'”’)]$/.test(p) ? p : `${p}.`))
    .join(" ");
}

// As vozes "Online" do Edge emudecem no meio de uma fala longa (uns 15 s): texto comprido vai em pedaços.
const PEDACO_MAXIMO = 200;

function porPalavras(frase) {
  const partes = [];
  let atual = "";
  for (const palavra of frase.split(" ")) {
    const junto = atual ? `${atual} ${palavra}` : palavra;
    if (junto.length > PEDACO_MAXIMO && atual) {
      partes.push(atual);
      atual = palavra;
    } else {
      atual = junto;
    }
  }
  if (atual) partes.push(atual);
  return partes;
}

const TEM_PALAVRA = /[\p{L}\p{N}]/u;

/**
 * O texto (já de `paraLer`) em pedaços de frases inteiras, cada um de até ~200 letras. Fim de frase é a pontuação
 * seguida de espaço ou do fim do texto: "$3.50", "a.m." e "S.H.I.E.L.D." chegam inteiros à voz. Texto curto vai
 * num pedaço só, como está; sem nenhuma letra ou número, não há o que ler ([]).
 */
export function pedacos(texto) {
  texto = texto.trim();
  if (!TEM_PALAVRA.test(texto)) return [];
  if (texto.length <= PEDACO_MAXIMO) return [texto];
  const frases = (texto.match(/.+?(?:[.!?]+["'”’)]*(?=\s|$)|$)/gs) || []).map((f) => f.trim()).filter(Boolean);
  const partes = [];
  let atual = "";
  for (const frase of frases) {
    if (frase.length > PEDACO_MAXIMO) {
      if (atual) partes.push(atual);
      atual = "";
      partes.push(...porPalavras(frase));
      continue;
    }
    const junto = atual ? `${atual} ${frase}` : frase;
    if (junto.length > PEDACO_MAXIMO) {
      partes.push(atual);
      atual = frase;
    } else {
      atual = junto;
    }
  }
  if (atual) partes.push(atual);
  return partes;
}

let falando = []; // o Edge às vezes descarta a fala antes do fim (e não avisa) se ninguém guarda ela
let rodada = 0;   // cada leitura tem um número: aviso atrasado de uma leitura velha não mexe na nova

/** A taxa da velocidade escolhida na aba Sobre (1 = normal). */
export const taxaEscolhida = () => VELOCIDADES.find((v) => v.valor === velocidadeEscolhida())?.taxa || 1;

/**
 * Lê o texto em voz alta (parando o que estiver tocando), em pedaços de frases inteiras. `aoTerminar` roda
 * uma vez, quando acaba ou é parado. `ajustes` ({voz, taxa, tom, volume}, da tela Text to Audio) troca a voz e
 * a velocidade da aba Sobre só nesta leitura; tom e taxa com 1 = normal, volume de 0 a 100.
 * Devolve false se não há voz em inglês neste computador.
 */
export function falar(texto, aoTerminar = () => {}, ajustes = {}) {
  if (!temVoz() || !vozesEmIngles().length) return false;
  speechSynthesis.cancel();
  const vez = ++rodada;
  let avisou = false;
  const terminar = () => { if (!avisou) { avisou = true; aoTerminar(); } };
  const partes = pedacos(texto);
  const escolhida = ajustes.voz ? vozesEmIngles().find((v) => v.name === ajustes.voz) : null;
  falando = partes.map((parte, i) => {
    const fala = new SpeechSynthesisUtterance(parte);
    fala.lang = "en-US";
    fala.voice = escolhida || voz();
    fala.rate = ajustes.taxa ?? taxaEscolhida();
    fala.pitch = ajustes.tom ?? 1;
    fala.volume = (ajustes.volume ?? 100) / 100;
    fala.addEventListener("error", (ev) => {
      // parada (cancel) chega como "interrupted"/"canceled": só termina. Falha de verdade num pedaço (ex.: voz
      // Online sem internet) para o resto, senão o botão volta a "Ouvir" com a leitura ainda tocando; e só se
      // esta ainda for a leitura atual (o Chrome avisa atrasado, depois de a próxima começar)
      if (!["interrupted", "canceled"].includes(ev?.error) && vez === rodada) speechSynthesis.cancel();
      terminar(); // o botão volta a "Ouvir"
    });
    if (i === partes.length - 1) fala.addEventListener("end", terminar);
    speechSynthesis.speak(fala);
    return fala;
  });
  if (!partes.length) terminar();
  return true;
}

export function parar() {
  if (temVoz()) speechSynthesis.cancel();
}
