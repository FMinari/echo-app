// Ponto de entrada da tela: liga as telas, avisa o Python que a janela está aberta e carrega os dados do início.
import { api, manterAberto } from "./lib/ponte.js";
import { $ } from "./lib/dom.js";
import { dataBr } from "./lib/formato.js";
import { emitir } from "./lib/eventos.js";
import { vigiarErros } from "./lib/erros.js";
import { estado } from "./estado.js";
import { erroEm } from "./componentes/avisos.js";
import { abrirAba, iniciarAbas } from "./telas/abas.js";
import { iniciarTema } from "./telas/tema.js";
import { iniciarBusca, preencherObras } from "./telas/buscar/index.js";
import { interruptorDoAcervo } from "./telas/buscar/acervo.js";
import { iniciarEstruturas } from "./telas/estruturas/index.js";
import { iniciarAulas } from "./telas/aulas/index.js";
import { recarregarAulas } from "./telas/aulas/dados.js";
import { iniciarTextos } from "./telas/textos/index.js";
import { iniciarSobre } from "./telas/sobre.js";
import { verAtualizacao, verificarToken, vigiarAtualizacoes } from "./telas/atualizacao.js";

async function iniciar() {
  vigiarErros();
  iniciarTema();
  iniciarAbas();
  iniciarBusca();
  iniciarEstruturas();
  iniciarAulas();
  iniciarTextos();
  iniciarSobre();

  manterAberto();
  try {
    const d = await api("inicio");
    Object.assign(estado, { estruturas: d.estruturas, obras: d.obras, grupos: d.grupos || [], pecas: d.pecas || [], versaoApp: d.versao });
    const versao = $("#versao-app");
    versao.textContent = d.data ? `v${d.versao} · atualizado em ${dataBr(d.data)}` : `v${d.versao}`;
    versao.addEventListener("click", () => abrirAba("sobre"));
    emitir("estruturas-mudaram");
    preencherObras();
    interruptorDoAcervo($("#f-acervo"), d.acervo);
    recarregarAulas();
  } catch (e) {
    erroEm($("#resultado"), e);
  }
  // mesmo se o início falhou (banco ou dados com problema), procura a versão que pode consertar
  await verAtualizacao();
  vigiarAtualizacoes();
  verificarToken();
}

iniciar();
