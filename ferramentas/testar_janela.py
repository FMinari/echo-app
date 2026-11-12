"""Sobe o servidor da janela (janela/app.py) e abre a tela num navegador de teste (pywebview, só no PC
do dev; no da cliente é o Edge) sem mostrar na tela, e usa a interface como a cliente usaria: escolhe a
estrutura no seletor, busca, anda nas páginas, filtra, guarda e tira um favorito, escreve o que procura
(phrasal verbs, outras formas, tempo do verbo), escreve um texto e salva o áudio dele, monta e testa uma
regra com peças e abre o Sobre. Usa um dados.db de teste (o da cliente/seu não é tocado).

Uso: QT_QPA_PLATFORM=offscreen app/.venv/bin/python -I ferramentas/testar_janela.py
Sai com erro se alguma etapa falhar.
"""
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

os.environ.setdefault("FRASES_DADOS", str(Path(tempfile.mkdtemp(prefix="sitcomatica-teste-")) / "dados.db"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app" / "janela"))
import webview  # noqa: E402

import app  # noqa: E402

# Roda dentro da página. Cada etapa devolve um texto curto (ou lança erro); o resultado vai para
# window.__teste porque o backend Qt não espera Promise no evaluate_js.
ROTEIRO = r"""
(async () => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esperar = async (cond, oQue, ms = 30000) => {
    const fim = Date.now() + ms;
    while (!cond()) { if (Date.now() > fim) throw new Error("esperando: " + oQue); await new Promise(r => setTimeout(r, 100)); }
  };
  const digitar = (campo, texto) => { campo.value = texto; campo.dispatchEvent(new Event("input", { bubbles: true })); };
  const tecla = (campo, key) => campo.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
  const clicarTexto = (texto, raiz = document) => {
    const b = $$("button", raiz).find(x => x.textContent.trim() === texto);
    if (!b) throw new Error("botão não encontrado: " + texto);
    b.click();
  };
  const resultado = [];
  const etapa = async (nome, fn) => { try { resultado.push([nome, true, await fn()]); } catch (e) { resultado.push([nome, false, e.message]); } };

  await esperar(() => /^v[\d.]+ · atualizado em \d\d\/\d\d\/\d{4}$/.test($("#versao-app").textContent), "início");

  await etapa("escolher estrutura no seletor", async () => {
    $("#f-estrutura").click();
    const busca = $(".sel-painel:not([hidden]) input");
    digitar(busca, "past perfect");
    await esperar(() => $(".sel-opcao.ativo"), "opção");
    const escolhida = $(".sel-opcao.ativo .sel-rotulo").textContent;
    tecla(busca, "Enter");
    return escolhida + " → " + $("#f-estrutura").textContent;
  });

  await etapa("buscar", async () => {
    $("#form-busca button[type=submit]").click();
    await esperar(() => $$("#resultado .cartao:not(.cartao-esqueleto)").length, "cartões");
    return `${$("#resultado h2").textContent} · ${$$("#resultado .cartao:not(.cartao-esqueleto)").length} cartões · ${$$("#resultado .cartao mark").length} destaques`;
  });

  await etapa("próxima página das séries", async () => {
    const antes = $(".secao-tipo[data-tipo=serie] .frase").textContent;
    $(".secao-tipo[data-tipo=serie] [aria-label='Próxima página']").click();
    await esperar(() => $(".secao-tipo[data-tipo=serie] .recolhivel-detalhe").textContent.includes("página 2"), "página 2");
    if ($(".secao-tipo[data-tipo=serie] .frase").textContent === antes) throw new Error("mesma frase na página 2");
    return $(".secao-tipo[data-tipo=serie] .recolhivel-detalhe").textContent;
  });

  await etapa("filtrar resultados", async () => {
    digitar($("#f-filtro"), "monica");
    await esperar(() => $("#resultado h2").textContent.includes("monica"), "filtro");
    return $("#resultado h2").textContent;
  });

  await etapa("guardar sem aula", async () => {
    $("#resultado .cartao .favoritar").click();
    await esperar(() => $("#n-frases").textContent === "(1)", "contador de frases");
    return $("#resultado .cartao .favoritar").textContent + " · contador " + $("#n-frases").textContent;
  });

  await etapa("aba Aulas: apagar a frase sem aula", async () => {
    $("[data-parte=aulas]").click();
    await esperar(() => $$("#detalhe-aula .cartao").length === 1, "frase em Sem aula");
    clicarTexto("Apagar frase", $("#detalhe-aula"));
    clicarTexto("Clique de novo para apagar", $("#detalhe-aula")); // duplo clique não apaga
    await new Promise((ok) => setTimeout(ok, 500));
    if (!$$("#detalhe-aula .cartao").length) throw new Error("apagou sem confirmar");
    clicarTexto("Clique de novo para apagar", $("#detalhe-aula"));
    await esperar(() => $("#n-frases").textContent === "", "contador zerado");
    return $("#detalhe-aula h2").textContent;
  });

  await etapa("criar aula na Buscar e guardar nela", async () => {
    $("[data-aba=buscar]").click();
    // a frase tirada na aba Aulas volta a aparecer como "Guardar"
    await esperar(() => $("#resultado .cartao .favoritar")?.textContent === "Guardar" && !$("#resultado.atualizando"), "cartões atualizados");
    clicarTexto("Nova aula", $("#nova-aula-busca"));
    $("#nova-aula-busca input").value = "Aula de teste";
    clicarTexto("Criar", $("#nova-aula-busca"));
    await esperar(() => $("#f-aula").textContent.includes("Aula de teste"), "aula escolhida");
    for (const b of $$("#resultado .cartao .favoritar").slice(0, 2)) b.click();
    await esperar(() => $("#n-frases").textContent === "(2)", "duas frases");
    return $("#resultado .cartao .favoritar").textContent;
  });

  await etapa("aula: nota, ouvir, salvar áudio e folha de completar", async () => {
    $("[data-parte=aulas]").click();
    await esperar(() => $("#detalhe-aula h2")?.textContent === "Aula de teste" && $$("#detalhe-aula .cartao").length === 2, "aula aberta");
    const nota = $("#detalhe-aula .nota");
    nota.value = "começar por esta";
    nota.dispatchEvent(new Event("input", { bubbles: true }));
    await esperar(() => $(".nota-situacao").textContent === "Salvo", "nota salva");
    if (!$("#detalhe-aula .cartao .ouvir")) throw new Error("sem o botão Ouvir");
    // fora do Windows o Python recusa: confere que o botão chega na api e o aviso aparece
    $("#detalhe-aula .cartao .salvar-audio").click();
    await esperar(() => !$("#toast").hidden && $("#toast").textContent.includes("só funciona no Windows"), "aviso do Salvar áudio");
    $$("#detalhe-aula button").find(b => b.textContent.startsWith("Fazer folha")).click();
    await esperar(() => $(".folha"), "folha");
    $(".folha-opcoes [data-valor=completar]").click();
    await esperar(() => $(".folha .lacuna"), "lacunas");
    const lacunas = $$(".folha .lacuna").length, gabarito = $$(".folha-gabarito li").length;
    if (gabarito !== 2) throw new Error("gabarito com " + gabarito);
    clicarTexto("Voltar para a aula", $("#detalhe-aula"));
    return `${lacunas} lacunas · gabarito ${gabarito} · ${$(".folha-instrucao")?.textContent || "voltou"}`;
  });

  await etapa("ler texto longo em pedaços de frases inteiras", async () => {
    const voz = await import(new URL("js/lib/voz.js", location.href));
    const lido = voz.paraLer("My weekend\n\nI went to the beach\nwith my sister. It was sunny!\n\n\n" + "Then we ate. ".repeat(40));
    if (!lido.startsWith("My weekend. I went to the beach with my sister. It was sunny! Then")) throw new Error(lido.slice(0, 80));
    const pedacos = voz.pedacos(lido);
    if (pedacos.some(p => p.length > 200) || pedacos.join(" ") !== lido) throw new Error("pedaços errados");
    if (pedacos.some(p => !/[.!?]$/.test(p))) throw new Error("pedaço cortado no meio da frase");
    const longa = voz.pedacos("word ".repeat(100).trim());
    if (longa.some(p => p.length > 200) || longa.join(" ") !== "word ".repeat(100).trim()) throw new Error("frase sem ponto");
    // ponto sem espaço depois não é fim de frase: número, sigla, abreviação chegam inteiros à voz
    const curta = "It costs $3.50 at 9 a.m. with S.H.I.E.L.D. agents.";
    if (JSON.stringify(voz.pedacos(curta)) !== JSON.stringify([curta])) throw new Error("curta: " + JSON.stringify(voz.pedacos(curta)));
    const precos = "The price is $3.50 today and S.H.I.E.L.D. pays it. ".repeat(12).trim();
    const pp = voz.pedacos(precos);
    if (pp.join(" ") !== precos || pp.some(p => /\$3\.$|S\.$|^50/.test(p))) throw new Error("cortou no meio: " + pp.find(p => /\$3\.$|S\.$|^50/.test(p)));
    if (voz.pedacos("...").length || voz.pedacos("?!").length) throw new Error("pontuação sozinha virou pedaço");
    return `${pedacos.length} pedaços · frase sem ponto em ${longa.length} · $3.50 e S.H.I.E.L.D. inteiros`;
  });

  await etapa("falha num pedaço do meio para a leitura; aviso atrasado de leitura velha não corta a nova", async () => {
    const voz = await import(new URL("js/lib/voz.js", location.href));
    const antes = { s: Object.getOwnPropertyDescriptor(window, "speechSynthesis"), u: Object.getOwnPropertyDescriptor(window, "SpeechSynthesisUtterance") };
    let cancelados = 0;
    const falas = [];
    Object.defineProperty(window, "speechSynthesis", { configurable: true, value: {
      getVoices: () => [{ name: "Teste", lang: "en-US", localService: true }], speak: (u) => falas.push(u),
      cancel: () => { cancelados++; }, addEventListener: () => {} } });
    Object.defineProperty(window, "SpeechSynthesisUtterance", { configurable: true, writable: true, value: class {
      constructor(texto) { this.texto = texto; this.ouvintes = {}; }
      addEventListener(nome, fn) { (this.ouvintes[nome] ||= []).push(fn); }
      disparar(nome, dados = {}) { for (const fn of this.ouvintes[nome] || []) fn(dados); } } });
    try {
      const texto = "This is one sentence that goes on for a while. ".repeat(12).trim();
      let fins = 0;
      voz.falar(texto, () => { fins++; });
      const primeira = [...falas];
      if (primeira.length < 3) throw new Error("só " + primeira.length + " pedaços");
      const antesDaFalha = cancelados;
      primeira[1].disparar("error", { error: "synthesis-failed" });
      if (cancelados !== antesDaFalha + 1 || fins !== 1) throw new Error(`falha no meio: cancelou ${cancelados - antesDaFalha}, fim ${fins}`);
      primeira[2].disparar("error", { error: "interrupted" });
      if (fins !== 1) throw new Error("terminou duas vezes");
      // uma leitura nova; o aviso atrasado da velha (falha de verdade) não pode cancelar a nova
      voz.falar("Second reading.", () => {});
      const antesDoAtraso = cancelados;
      primeira[0].disparar("error", { error: "synthesis-failed" });
      if (cancelados !== antesDoAtraso) throw new Error("aviso da leitura velha cancelou a nova");
      return `${primeira.length} pedaços · falha no 2º para o resto · aviso velho ignorado`;
    } finally {
      for (const [nome, d] of [["speechSynthesis", antes.s], ["SpeechSynthesisUtterance", antes.u]]) {
        if (d) Object.defineProperty(window, nome, d); else delete window[nome];
      }
    }
  });

  await etapa("aba Textos: escrever, salvar na aula e salvar áudio", async () => {
    $("[data-parte=textos]").click();
    await esperar(() => $("#detalhe-texto .vazio") || $("#detalhe-texto input"), "aba Textos");
    $("#novo-texto").click();
    await esperar(() => $("#detalhe-texto [name=titulo]"), "formulário");
    clicarTexto("Salvar", $("#detalhe-texto"));
    await esperar(() => !$("#toast").hidden && $("#toast").textContent.includes("título"), "pede o título");
    digitar($("#detalhe-texto [name=titulo]"), "My weekend");
    digitar($("#detalhe-texto [name=corpo]"), "I went to the beach.\n\nIt was sunny.");
    if (!$("#detalhe-texto .contagem").textContent.includes("8 palavras")) throw new Error("contagem: " + $("#detalhe-texto .contagem").textContent);
    $("#f-texto-aula").click();
    const painel = $("#f-texto-aula").closest(".sel").querySelector(".sel-painel");
    const busca = $("input", painel);
    digitar(busca, "aula de teste");
    await esperar(() => $(".sel-opcao.ativo", painel), "aula no seletor");
    tecla(busca, "Enter");
    if (!$("#f-texto-aula").textContent.includes("Aula de teste")) throw new Error("aula não escolhida: " + $("#f-texto-aula").textContent);
    clicarTexto("Salvar", $("#detalhe-texto"));
    await esperar(() => $$("#lista-textos .item-texto").some(b => b.textContent.includes("My weekend")), "na lista");
    // fora do Windows o Python recusa: confere que o botão chega na api e o aviso aparece
    clicarTexto("Salvar áudio", $("#detalhe-texto"));
    await esperar(() => !$("#toast").hidden && $("#toast").textContent.includes("só funciona no Windows"), "aviso do Salvar áudio");
    if (!$("#lista-textos .item-texto").textContent.includes("Aula de teste")) throw new Error("salvo fora da aula: " + $("#lista-textos .item-texto").textContent);
    return $("#lista-textos .item-texto").textContent;
  });

  await etapa("voz da leitura: velocidade, tom e volume vão para o Salvar áudio", async () => {
    const painel = $("#detalhe-texto .voz-leitura");
    if (!painel) throw new Error("sem o painel de voz");
    const ajustar = (nome, valor) => { const c = $(`[name=${nome}]`, painel); c.value = valor; c.dispatchEvent(new Event("input", { bubbles: true })); };
    ajustar("taxa", "0.75");
    ajustar("tom", "1.2");
    ajustar("volume", "80");
    const lido = $$(".deslizante-valor", painel).map(o => o.textContent).join(" · ");
    if (lido !== "0,75× · +20% · 80%") throw new Error("valores na tela: " + lido);
    // o que vai para o Python: espia o fetch do Salvar áudio
    const original = window.fetch;
    let enviado = null;
    window.fetch = (url, op) => { if (String(url).endsWith("/api/salvar_audio_texto")) enviado = JSON.parse(op.body); return original(url, op); };
    try {
      clicarTexto("Salvar áudio", $("#detalhe-texto"));
      await esperar(() => enviado, "pedido do áudio");
    } finally { window.fetch = original; }
    const a = enviado[1];
    if (a.taxa !== 0.75 || a.tom !== 1.2 || a.volume !== 80) throw new Error("ajustes enviados: " + JSON.stringify(a));
    clicarTexto("Voltar ao padrão", painel);
    const padrao = $$(".deslizante-valor", $("#detalhe-texto .voz-leitura")).map(o => o.textContent).join(" · ");
    if (!padrao.endsWith("normal · 100%")) throw new Error("padrão: " + padrao);
    return `${lido} → padrão ${padrao}`;
  });

  await etapa("seletor perto do fim da janela abre para cima", async () => {
    const botao = $("#f-texto-voz");
    const painel = botao.closest(".sel").querySelector(".sel-painel");
    const topo = $(".topo").getBoundingClientRect().bottom;
    // o seletor de voz encostado embaixo da janela: a lista não cabe embaixo, abre para cima
    scrollBy(0, botao.getBoundingClientRect().bottom - innerHeight + 6);
    await new Promise((ok) => setTimeout(ok, 100));
    botao.click();
    const caixa = painel.getBoundingClientRect(), b = botao.getBoundingClientRect();
    const paraCima = painel.classList.contains("sel-para-cima");
    tecla($("input", painel), "Escape");
    if (!paraCima || caixa.bottom > b.top || caixa.top < topo) throw new Error(`abriu em ${Math.round(caixa.top)}–${Math.round(caixa.bottom)}, botão em ${Math.round(b.top)}, topo até ${Math.round(topo)}`);
    // com espaço embaixo, continua abrindo para baixo
    scrollBy(0, botao.getBoundingClientRect().top - topo - 10);
    await new Promise((ok) => setTimeout(ok, 100));
    botao.click();
    const baixo = !painel.classList.contains("sel-para-cima") && painel.getBoundingClientRect().top >= botao.getBoundingClientRect().bottom;
    tecla($("input", painel), "Escape");
    if (!baixo) throw new Error("com espaço embaixo, não abriu para baixo");
    return "perto do fim: para cima · com espaço: para baixo";
  });

  await etapa("ouvir só o trecho selecionado", async () => {
    const corpo = $("#detalhe-texto [name=corpo]");
    const botaoCom = (texto) => $$("#detalhe-texto .barra-acoes button").find(b => b.textContent.trim() === texto);
    // aqui não tem voz: um sintetizador falso anota o que o Ouvir mandou ler
    const falados = [];
    const antes = { s: Object.getOwnPropertyDescriptor(window, "speechSynthesis"), u: Object.getOwnPropertyDescriptor(window, "SpeechSynthesisUtterance") };
    Object.defineProperty(window, "speechSynthesis", { configurable: true, value: {
      getVoices: () => [{ name: "Teste", lang: "en-US", localService: true }], speak: (u) => falados.push(u.texto),
      cancel: () => {}, addEventListener: () => {} } });
    Object.defineProperty(window, "SpeechSynthesisUtterance", { configurable: true, writable: true,
      value: class { constructor(texto) { this.texto = texto; } addEventListener() {} } });
    try {
      if (!botaoCom("Ouvir")) throw new Error("sem o Ouvir");
      const inicio = corpo.value.indexOf("It was");
      corpo.focus();
      corpo.setSelectionRange(inicio, corpo.value.length);
      corpo.dispatchEvent(new Event("select"));
      if (!botaoCom("Ouvir trecho")) throw new Error("com seleção, o botão não virou Ouvir trecho");
      botaoCom("Ouvir trecho").click();
      await esperar(() => falados.length, "leu");
      if (falados.join(" ") !== "It was sunny.") throw new Error("leu: " + falados.join(" | "));
      clicarTexto("Parar", $("#detalhe-texto"));
      // um trecho só de pontuação: avisa e o botão não fica preso em "Parar"
      corpo.setSelectionRange(corpo.value.length - 1, corpo.value.length);
      corpo.dispatchEvent(new Event("select"));
      botaoCom("Ouvir trecho").click();
      await esperar(() => !$("#toast").hidden && $("#toast").textContent.includes("não tem palavras"), "aviso de trecho sem palavras");
      if (!botaoCom("Ouvir trecho")) throw new Error("trecho só de pontuação deixou o botão preso");
      corpo.setSelectionRange(0, 0);
      corpo.dispatchEvent(new Event("select"));
      if (!botaoCom("Ouvir")) throw new Error("sem seleção, não voltou para Ouvir");
      falados.length = 0;
      botaoCom("Ouvir").click();
      await esperar(() => falados.length, "leu tudo");
      if (falados.join(" ") !== "I went to the beach. It was sunny.") throw new Error("sem seleção leu: " + falados.join(" | "));
      clicarTexto("Parar", $("#detalhe-texto"));
      return "trecho: It was sunny. · tudo: " + falados.join(" ");
    } finally {
      for (const [nome, d] of [["speechSynthesis", antes.s], ["SpeechSynthesisUtterance", antes.u]]) {
        if (d) Object.defineProperty(window, nome, d); else delete window[nome];
      }
    }
  });

  await etapa("texto: mudança sem salvar não se perde ao trocar de aba", async () => {
    digitar($("#detalhe-texto [name=corpo]"), "I went to the park.");
    $("[data-parte=aulas]").click();
    await esperar(() => $("#detalhe-aula h2")?.textContent === "Aula de teste", "aula aberta");
    await esperar(() => $$("#detalhe-aula .item-texto-aula").length === 1, "texto na aula");
    $("#detalhe-aula .item-texto-aula").click();
    await esperar(() => !$("#aba-textos").hidden && $("#detalhe-texto [name=titulo]")?.value === "My weekend", "abriu na aba Textos");
    // confere no banco (a tela ainda mostra o que a cliente digitou, salvo ou não)
    const senha = new URLSearchParams(location.search).get("t");
    const chamar = (metodo, ...args) => fetch(`/api/${metodo}`, { method: "POST", headers: { "X-Sitcomatica": senha }, body: JSON.stringify(args) }).then(r => r.json());
    const { id } = (await chamar("textos")).find(t => t.titulo === "My weekend");
    const { corpo } = await chamar("texto", id);
    if (corpo !== "I went to the park.") throw new Error("perdeu: " + corpo);
    return corpo;
  });

  await etapa("texto novo de Sem aula fica em Sem aula; Salvar duas vezes seguidas cria um texto só", async () => {
    const senha = new URLSearchParams(location.search).get("t");
    const chamar = (metodo, ...args) => fetch(`/api/${metodo}`, { method: "POST", headers: { "X-Sitcomatica": senha }, body: JSON.stringify(args) }).then(r => r.json());
    // o filtro da Text to Audio numa aula
    $("#filtro-textos").click();
    const painel = $("#filtro-textos").closest(".sel").querySelector(".sel-painel");
    digitar($("input", painel), "aula de teste");
    await esperar(() => $(".sel-opcao.ativo", painel), "aula no filtro");
    tecla($("input", painel), "Enter");
    // na tela Aulas, em "Sem aula", "Escrever um texto"
    const tituloVelho = $("#detalhe-aula h2");
    $("[data-parte=aulas]").click();
    await esperar(() => $("#detalhe-aula h2") !== tituloVelho && !$("#detalhe-aula .carregando"), "aula recarregada");
    $(".item-aula.sem-aula").click();
    await esperar(() => $("#detalhe-aula h2")?.textContent === "Sem aula" && $("#detalhe-aula .textos-da-aula"), "Sem aula");
    clicarTexto("Escrever um texto", $("#detalhe-aula"));
    await esperar(() => !$("#aba-textos").hidden && $("#detalhe-texto h2")?.textContent === "Novo texto", "texto novo");
    if ($("#f-texto-aula").textContent.trim() !== "Sem aula") throw new Error("texto novo de Sem aula foi para: " + $("#f-texto-aula").textContent);
    digitar($("#detalhe-texto [name=titulo]"), "Duplo");
    clicarTexto("Salvar", $("#detalhe-texto"));
    clicarTexto("Salvar", $("#detalhe-texto")); // o segundo sai antes do primeiro voltar
    await esperar(() => !$("#toast").hidden && $("#toast").textContent.includes("Texto salvo"), "salvo");
    await new Promise((ok) => setTimeout(ok, 800));
    const duplos = (await chamar("textos")).filter(t => t.titulo === "Duplo");
    if (duplos.length !== 1) throw new Error(`${duplos.length} textos "Duplo"`);
    if ($$("#detalhe-texto button").filter(b => b.textContent.trim() === "Apagar texto").length !== 1) throw new Error("botão Apagar repetido");
    if (duplos[0].aula_id !== null) throw new Error("salvo na aula " + duplos[0].aula);
    // limpa: apaga o "Duplo" (o app abre o próximo, o "My weekend", para a etapa seguinte)
    clicarTexto("Apagar texto", $("#detalhe-texto"));
    await new Promise((ok) => setTimeout(ok, 500));
    clicarTexto("Clique de novo para apagar", $("#detalhe-texto"));
    await esperar(() => $("#detalhe-texto [name=titulo]")?.value === "My weekend", "voltou para o My weekend");
    return "1 texto, em Sem aula, um botão Apagar";
  });

  await etapa("apagar o texto", async () => {
    clicarTexto("Apagar texto", $("#detalhe-texto"));
    clicarTexto("Clique de novo para apagar", $("#detalhe-texto")); // duplo clique não apaga
    await new Promise((ok) => setTimeout(ok, 500));
    if (!$$("#lista-textos .item-texto").length) throw new Error("apagou sem confirmar");
    clicarTexto("Clique de novo para apagar", $("#detalhe-texto"));
    await esperar(() => !$$("#lista-textos .item-texto").length, "lista vazia");
    const sobrou = $("#detalhe-texto").textContent.slice(0, 60);
    // as etapas seguintes usam a aula aberta; a da visita anterior continua na tela até a aula recarregar,
    // então espera o título ser trocado por um novo e os cartões de verdade
    const tituloVelho = $("#detalhe-aula h2");
    $("[data-parte=aulas]").click();
    await esperar(() => $("#detalhe-aula h2") !== tituloVelho && $("#detalhe-aula h2")?.textContent === "Aula de teste"
      && $$("#detalhe-aula .cartao:not(.cartao-esqueleto)").length, "de volta à aula");
    return sobrou;
  });

  await etapa("dicionário ao clicar numa palavra", async () => {
    await esperar(() => $$("#detalhe-aula .cartao .frase").length, "frases da aula");
    const frase = $("#detalhe-aula .cartao .frase");
    // o clique é por posição: a frase tem que estar à vista; e a rolagem fecha o balão, então espera ela passar
    frase.scrollIntoView({ block: "center" });
    await new Promise((ok) => setTimeout(ok, 300));
    const texto = [...frase.childNodes].find(n => n.nodeType === 3 && /[A-Za-z]{3}/.test(n.textContent));
    const r = document.createRange();
    const i = texto.textContent.search(/[A-Za-z]{3}/);
    r.setStart(texto, i + 1); r.setEnd(texto, i + 2);
    const caixa = r.getBoundingClientRect();
    frase.dispatchEvent(new MouseEvent("click", { bubbles: true, clientX: caixa.left + 1, clientY: caixa.top + caixa.height / 2 }));
    await esperar(() => $(".balao") && !$(".balao .carregando"), "balão", 20000);
    const t = $(".balao").textContent;
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    return t.slice(0, 80);
  });

  await etapa("escrever um verbo mostra os phrasal verbs", async () => {
    $("[data-aba=buscar]").click();
    $("#f-modo [data-valor=escrever]").click();
    $("#f-texto").value = "get";
    $("#form-busca button[type=submit]").click();
    await esperar(() => $$(".ficha").length, "fichas", 60000);
    return `${$("#fichas-livre h3").textContent} · ${$$(".ficha").length} fichas`;
  });

  await etapa("ficha busca as frases", async () => {
    $$(".ficha").find(b => b.querySelector(".ficha-topo span").textContent === "get over").click();
    await esperar(() => $("#resultado h2")?.textContent.includes("get over"), "frases de get over", 60000);
    if ($(".ficha[aria-pressed=true] .ficha-topo span")?.textContent !== "get over") throw new Error("ficha não marcada");
    if ($("#resultado .cartao .falso")?.textContent) throw new Error("apareceu 'Não é essa estrutura' na busca escrita");
    if (!$("#resultado .significado")?.textContent.includes("superar")) throw new Error("sem o significado de get over");
    if (!$$(".ficha-detalhe").length) throw new Error("fichas sem significado");
    return `${$("#resultado h2").textContent} · ${$("#resultado .significado").textContent}`;
  });

  await etapa("guardar a busca como estrutura", async () => {
    clicarTexto("Guardar como estrutura", $("#resultado"));
    await esperar(() => $(".guardar-form input"), "formulário de guardar");
    $(".guardar-form input").value = "Teste get over";
    clicarTexto("Guardar", $(".guardar-form"));
    await esperar(() => $(".guardar-busca .ajuda")?.textContent.includes("Guardada"), "guardada", 60000);
    $("[data-aba=catalogo]").click();
    await esperar(() => $$(".item-estrutura").some(b => b.textContent.startsWith("Teste get over")), "na lista de estruturas");
    $("[data-aba=buscar]").click();
    return $(".guardar-busca .ajuda").textContent;
  });

  await etapa("sem outras formas: só como escrito", async () => {
    $("#f-outras-formas input").click();
    if (!$("#f-tempo").disabled) throw new Error("tempo do verbo continuou ligado");
    $("#f-texto").value = "took off";
    $("#form-busca button[type=submit]").click();
    await esperar(() => $("#resultado h2")?.textContent.includes("took off"), "frases de took off", 60000);
    const outros = $$("#resultado .cartao mark").map(m => m.textContent.toLowerCase()).filter(t => t !== "took off");
    if (outros.length) throw new Error("achou " + outros.join(", "));
    if (!$("#fichas-livre").hidden) throw new Error("fichas continuaram");
    $("#f-outras-formas input").click();
    return $("#resultado h2").textContent;
  });

  await etapa("tempo do verbo: passado", async () => {
    $("#f-tempo").click();
    const busca = $(".sel-painel:not([hidden]) input");
    digitar(busca, "passado");
    await esperar(() => $(".sel-opcao.ativo"), "opção");
    tecla(busca, "Enter");
    $("#f-texto").value = "take off";
    $("#form-busca button[type=submit]").click();
    await esperar(() => $("#resultado h2")?.textContent.includes("take off"), "frases de take off", 60000);
    const marcas = $$("#resultado .cartao mark").map(m => m.textContent.toLowerCase());
    if (marcas.filter(t => t.startsWith("took")).length < marcas.length - 1) throw new Error("fora do passado: " + marcas.join(", "));
    return `${$("#f-tempo").textContent} · ${$("#resultado h2").textContent}`;
  });

  await etapa("nova estrutura com peças e Testar", async () => {
    $("[data-aba=catalogo]").click();
    await esperar(() => $$(".item-estrutura").length > 100, "lista de estruturas");
    $("#nova-estrutura").click();
    await esperar(() => $$(".peca").length === 2, "duas peças iniciais");
    const tipo = $$(".peca-tipo")[1];
    tipo.value = "verbo_passado";
    tipo.dispatchEvent(new Event("change"));
    clicarTexto("Testar", $("#detalhe-estrutura"));
    await esperar(() => /frases? encontradas?/.test($(".amostra").textContent), "amostra", 60000);
    return $(".resumo-regra").textContent + " · " + $(".amostra b").textContent;
  });

  await etapa("abrir estrutura pronta", async () => {
    $$(".item-estrutura").find(b => b.textContent.startsWith("Past simple")).click();
    await esperar(() => $("#detalhe-estrutura h2")?.textContent === "Past simple", "formulário");
    if ($("#detalhe-estrutura").textContent.includes("null")) throw new Error("apareceu 'null'");
    return $(".resumo-regra").textContent;
  });

  await etapa("Frases volta para a última sub-aba (Estruturas)", async () => {
    $("[data-parte=aulas]").click();
    if (!$("#sub-frases").hidden) throw new Error("sub-abas de Frases aparecendo em Aulas");
    $("[data-parte=frases]").click();
    if ($("#aba-catalogo").hidden || $("#sub-frases").hidden) throw new Error("não voltou para Estruturas");
    const nomes = $$("[data-parte]").map(b => b.querySelector(".parte-nome").firstChild.textContent.trim()).join(" · ");
    if (nomes !== "Frases · Aulas · Text to Audio") throw new Error("abas: " + nomes);
    return nomes;
  });

  await etapa("procura atualização sozinho ao voltar para a janela", async () => {
    const original = window.fetch, agora = Date.now;
    let perguntas = 0;
    window.fetch = (url, ...resto) => { if (String(url).includes("procurar_atualizacao")) perguntas++; return original(url, ...resto); };
    try {
      document.dispatchEvent(new Event("visibilitychange"));
      await new Promise(r => setTimeout(r, 300));
      const logo = perguntas;                         // voltou logo: não pergunta
      Date.now = () => agora() + 31 * 60 * 1000;     // 31 minutos depois
      document.dispatchEvent(new Event("visibilitychange"));
      await esperar(() => perguntas > logo, "perguntou ao voltar", 5000);
      if (logo !== 0) throw new Error("perguntou antes dos 30 minutos");
      return `antes dos 30 min: ${logo} · depois: ${perguntas}`;
    } finally { window.fetch = original; Date.now = agora; }
  });

  await etapa("arquivo que não é atualização é recusado", async () => {
    const senha = new URLSearchParams(location.search).get("t");
    const r = await fetch("/api/enviar_atualizacao", { method: "POST", body: new Blob(["oi"]),
      headers: { "X-Sitcomatica": senha, "X-Nome": encodeURIComponent("Sitcomatica teste.zip") } }).then(x => x.json());
    if (!r.erro) throw new Error("aceitou: " + JSON.stringify(r).slice(0, 100));
    const semSenha = await fetch("/api/inicio", { method: "POST", body: "[]" });
    if (semSenha.status !== 403) throw new Error("sem senha deu " + semSenha.status);
    return r.erro;
  });

  await etapa("aba Sobre com contato e versões", async () => {
    $("[data-aba=sobre]").click();
    await esperar(() => $("#contato") && $("#versoes") && !$("#versoes .carregando"), "Sobre", 20000);
    await esperar(() => $("#desinstalar .ajuda-sobre"), "cartão Desinstalar", 20000);
    // fora do app instalado (aqui) ele explica por que não dá, em vez de oferecer o botão
    if ($$("#desinstalar button").length) throw new Error("ofereceu desinstalar fora do app instalado");
    return $$(".cartao-sobre h2").map(h => h.textContent).join(" · ") + " · " + $("#desinstalar .ajuda-sobre").textContent;
  });

  await etapa("aviso de progresso ao procurar atualização", async () => {
    clicarTexto("Procurar atualização", $("#conteudo-sobre"));
    await esperar(() => $(".progresso") && !$(".progresso").hidden, "aviso aparece");
    const viu = $(".progresso").textContent;
    await esperar(() => !$(".progresso .progresso-roda"), "terminou de procurar", 20000);
    const resultado = $(".progresso").textContent;
    await esperar(() => $(".progresso").hidden, "aviso some sozinho", 6000);
    return `${viu} → ${resultado}`;
  });

  window.__teste = JSON.stringify(resultado);
})();
"""


def roteiro(janela):
    time.sleep(1)
    janela.evaluate_js(ROTEIRO)
    resultado = None
    for _ in range(1500):
        resultado = janela.evaluate_js("window.__teste || null")
        if resultado:
            break
        time.sleep(0.2)
    janela.destroy()
    etapas = json.loads(resultado) if resultado else [["roteiro", False, "não terminou"]]
    for nome, ok, detalhe in etapas:
        print(f"{'ok ' if ok else 'ERRO'} {nome}: {detalhe}")
    roteiro.falhou = not all(ok for _, ok, _ in etapas)


roteiro.falhou = True
servidor = app.Servidor(app.Api(), porta=0, desenvolvimento=True)
threading.Thread(target=servidor.rodar, daemon=True).start()
janela = webview.create_window("teste", servidor.endereco)
webview.start(roteiro, janela, gui="qt" if sys.platform.startswith("linux") else None)
sys.exit(1 if roteiro.falhou else 0)
