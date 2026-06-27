// Content script: dirige o DeepSeek pelo DOM. Envio, modo (Rápido/Especialista/
// Visão, so no inicio do chat) + toggles (Pensamento Profundo / Pesquisa
// inteligente), e o fluxo "API" (config + edicao da 2a mensagem). Sem mouse/teclado.
//
// Seletores calibrados no DOM real do DeepSeek (jun/2026). O DeepSeek nao usa
// aria-label/data-test-id; botoes sao div[role=button] com classe ofuscada, entao
// alguns sao achados por TEXTO visivel e o editar pelo PATH do icone (lapis).

const SEL = {
  editor: 'textarea[placeholder="Mensagem para DeepSeek" i], textarea[placeholder]',
  responses: ".ds-markdown",
  doneSignal: null,
  stopBtn: null, // DeepSeek nao expoe um botao de parar confiavel; usa estabilizacao
  editBtn: 'div[role="button"]:has(svg path[d^="M9.94076 1.34942"])', // icone de lapis = editar
  editArea: 'textarea.ds-textarea__textarea, textarea:not([placeholder])',
  modoRadio: '[role="radio"]',                 // Rápido / Especialista / Visão (chat novo)
  toggle: ".ds-toggle-button",                 // Pensamento Profundo / Pesquisa inteligente
  newChat: "._5a8ac7a"                         // item "Nova conversa" na lateral
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const q = (sel, root) => (sel ? (root || document).querySelector(sel) : null);
const qa = (sel, root) => (sel ? Array.from((root || document).querySelectorAll(sel)) : []);
const norm = (s) => (s || "").replace(/\s+/g, " ").trim().toLowerCase();
const visivel = (el) => { if (!el) return false; const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };

function dispatchHover(el) {
  ["pointerover", "mouseover", "mouseenter", "pointermove", "mousemove"].forEach((t) =>
    el.dispatchEvent(new MouseEvent(t, { bubbles: true }))
  );
}

// Acha um clicavel pelo texto visivel (DeepSeek rotula botoes so por texto).
function acharPorTexto(texto, opts = {}) {
  const alvo = norm(texto);
  const casa = (el) => { const s = norm(el.innerText); return opts.exact ? s === alvo : s.includes(alvo); };
  const clic = qa('div[role="button"], [role="radio"], button, [role="button"], .ds-toggle-button, ' + SEL.newChat)
    .filter((el) => visivel(el) && casa(el))
    .sort((a, b) => (a.innerText || "").length - (b.innerText || "").length);
  if (clic[0]) return clic[0];
  // fallback: elemento pequeno com o texto -> sobe pro ancestral clicavel
  const any = qa("*")
    .filter((el) => visivel(el) && el.children.length < 4 && casa(el))
    .sort((a, b) => (a.innerText || "").length - (b.innerText || "").length);
  const el = any[0];
  if (!el) return null;
  return el.closest('div[role="button"], [role="radio"], button, a, ' + SEL.newChat) || el;
}

// ----------------------------------------------------------------------------
// Dispatcher (uma operacao por vez)
// ----------------------------------------------------------------------------

let cadeia = Promise.resolve();
function serial(fn) {
  const r = cadeia.then(fn, fn);
  cadeia = r.then(() => {}, () => {});
  return r;
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  const handlers = {
    ask: () => handleAsk(msg.prompt),
    selecionar_modo: () => handleSelecionarModo(msg.pensamento, msg.pesquisa),
    configurar: () => handleConfigurar(msg),
    consultar: () => handleConsultar(msg.tarefa),
    inspecionar: () => inspecionar(msg.seletor, msg.max),
  };
  const h = handlers[msg.type];
  if (!h) {
    sendResponse({ ok: false, error: "tipo desconhecido: " + msg.type });
    return true;
  }
  serial(h).then(
    (text) => sendResponse({ ok: true, text }),
    (err) => sendResponse({ ok: false, error: String((err && err.message) || err) })
  );
  return true;
});

// ----------------------------------------------------------------------------
// Escrita / envio (composer e edicao sao textarea)
// ----------------------------------------------------------------------------

function escreverTextarea(field, text) {
  field.focus();
  const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set;
  setter.call(field, "");
  setter.call(field, text);
  field.dispatchEvent(new Event("input", { bubbles: true }));
}

function enviarComposer(editor) {
  ["keydown", "keyup"].forEach((t) =>
    editor.dispatchEvent(new KeyboardEvent(t, { key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true }))
  );
}

// ----------------------------------------------------------------------------
// Leitura da resposta
// ----------------------------------------------------------------------------

function limparResposta(text) {
  return (text || "").trim();
}

async function aguardarResposta(getResp, isStart, opts = {}) {
  const idleMs = opts.idleMs || 2500;
  const timeoutMs = opts.timeoutMs || 180000;
  const start = Date.now();
  let last = null;
  let stableSince = 0;
  let started = false;

  while (Date.now() - start < timeoutMs) {
    const resp = getResp();
    const text = resp ? resp.innerText.trim() : "";
    const gerando = SEL.stopBtn ? !!q(SEL.stopBtn) : false;
    const done = SEL.doneSignal ? !!(resp && resp.querySelector(SEL.doneSignal)) : false;
    if (!started && isStart(resp, text, gerando, Date.now() - start)) started = true;

    const pronto = started && (done || !gerando);
    if (resp && text && text === last && pronto) {
      if (!stableSince) stableSince = Date.now();
      if (Date.now() - stableSince >= idleMs) return limparResposta(text);
    } else {
      stableSince = 0;
      last = text;
    }
    await sleep(200);
  }
  if (last) return limparResposta(last);
  throw new Error("Tempo esgotado esperando a resposta do DeepSeek.");
}

// Mensagem NOVA: surge uma resposta alem das `antes`.
function esperarNova(antes) {
  const getResp = () => {
    const r = qa(SEL.responses);
    return r.length > antes ? r[r.length - 1] : null;
  };
  return aguardarResposta(getResp, (resp) => !!resp);
}

// EDICAO: a resposta no indice `idxAlvo` (a da mensagem de trabalho) muda. Ancora
// por indice fixo pra nunca ler a resposta da config (indice 0).
function esperarEdicao(idxAlvo, textoAntigo) {
  const getResp = () => { const r = qa(SEL.responses); return r[idxAlvo] || null; };
  const isStart = (resp, text, gerando, elapsed) =>
    gerando || (text && text !== textoAntigo) || elapsed > 8000;
  return aguardarResposta(getResp, isStart);
}

// ----------------------------------------------------------------------------
// Envio simples (one-shot)
// ----------------------------------------------------------------------------

async function handleAsk(prompt) {
  if (!prompt) throw new Error("tarefa vazia.");
  const editor = q(SEL.editor);
  if (!editor) throw new Error("Campo de entrada do DeepSeek nao encontrado.");

  const antes = qa(SEL.responses).length;
  escreverTextarea(editor, prompt);
  await sleep(150);
  enviarComposer(editor);

  return await esperarNova(antes);
}

// ----------------------------------------------------------------------------
// Modo (radios, so no chat novo) + toggles (qualquer hora)
// ----------------------------------------------------------------------------

async function selecionarModoInicial(modoLabel) {
  if (!modoLabel) return;
  const alvo = qa(SEL.modoRadio).filter(visivel).find((r) => norm(r.innerText).startsWith(norm(modoLabel)));
  if (!alvo) throw new Error(`Modo '${modoLabel}' nao encontrado (so aparece em chat novo).`);
  alvo.click();
  await sleep(300);
}

async function ajustarToggle(label, desejado) {
  if (desejado == null) return null;
  const btn = qa(SEL.toggle).filter(visivel).find((b) => norm(b.innerText).includes(norm(label)));
  if (!btn) throw new Error(`Toggle '${label}' nao encontrado.`);
  const ativo = btn.getAttribute("aria-pressed") === "true";
  if (ativo !== desejado) { btn.click(); await sleep(300); }
  return `${label}=${desejado}`;
}

async function handleSelecionarModo(pensamento, pesquisa) {
  const out = [];
  const a = await ajustarToggle("Pensamento Profundo", pensamento);
  if (a) out.push(a);
  const b = await ajustarToggle("Pesquisa inteligente", pesquisa);
  if (b) out.push(b);
  return out.length ? out.join(", ") : "nada a selecionar";
}

// ----------------------------------------------------------------------------
// Fluxo "API": configurar + consultar (edita pelo botao de lapis)
// ----------------------------------------------------------------------------

async function novoChat() {
  const el = q(SEL.newChat) || acharPorTexto("Nova conversa", { exact: true });
  if (!el) throw new Error("Botao 'Nova conversa' nao encontrado.");
  el.click();
  for (let i = 0; i < 40; i++) {
    await sleep(150);
    if (q(SEL.editor) && qa(SEL.editBtn).length === 0) return;
  }
  throw new Error("Nao consegui iniciar um chat novo (a conversa nao limpou).");
}

async function handleConfigurar(msg) {
  if (!msg.config) throw new Error("config vazia.");
  await novoChat();
  if (msg.modo) await selecionarModoInicial(msg.modo);
  await handleSelecionarModo(msg.pensamento, msg.pesquisa);
  return await handleAsk(msg.config);
}

async function handleConsultar(tarefa) {
  if (!tarefa) throw new Error("tarefa vazia.");
  const editBtns = qa(SEL.editBtn).filter(visivel);
  if (editBtns.length === 0) throw new Error("Configure primeiro com configurar_deepseek.");

  // So a config existe: cria a mensagem de trabalho como mensagem nova.
  if (editBtns.length < 2) return await handleAsk(tarefa);

  const idxAlvo = editBtns.length - 1; // resposta da mensagem de trabalho
  const resps = qa(SEL.responses);
  const textoAntigo = resps[idxAlvo] ? resps[idxAlvo].innerText.trim() : "";

  editBtns[editBtns.length - 1].click();
  await sleep(400);
  const campo = q(SEL.editArea);
  if (!campo || campo.tagName !== "TEXTAREA") throw new Error("Campo de edicao nao encontrado.");
  escreverTextarea(campo, tarefa);
  await sleep(150);

  const enviar = acharPorTexto("Enviar", { exact: true });
  if (!enviar) throw new Error("Botao 'Enviar' da edicao nao encontrado.");
  enviar.click();

  return await esperarEdicao(idxAlvo, textoAntigo);
}

// ----------------------------------------------------------------------------
// Diagnostico (temporario)
// ----------------------------------------------------------------------------

function descreverEl(el) {
  const out = { tag: el.tagName.toLowerCase() };
  ["id", "role", "aria-label", "aria-pressed", "data-test-id", "placeholder", "type", "contenteditable", "href", "target", "title"].forEach((a) => {
    const v = el.getAttribute && el.getAttribute(a);
    if (v) out[a] = v;
  });
  if (typeof el.className === "string" && el.className.trim()) {
    out.cls = el.className.trim().split(/\s+/).slice(0, 5).join(".");
  }
  out.vis = visivel(el);
  const t = (el.innerText || "").replace(/\s+/g, " ").trim();
  if (t) out.txt = t.slice(0, 80);
  return out;
}

async function inspecionar(seletor, max) {
  max = max || 40;
  let dumpSel = seletor;
  if (seletor && seletor.includes(" >>> ")) {
    const parts = seletor.split(" >>> ").map((s) => s.trim());
    dumpSel = parts.pop();
    for (const sel of parts) {
      const el = q(sel) || qa(sel).find((e) => e.getBoundingClientRect().width > 0);
      if (el) { dispatchHover(el); el.click(); await sleep(500); }
    }
  }
  const rep = { url: location.href };
  if (seletor && seletor.startsWith("texto:")) {
    const termo = norm(seletor.slice(6));
    const all = qa("*")
      .filter((el) => visivel(el) && el.children.length < 6 && norm(el.innerText).includes(termo))
      .sort((a, b) => (a.innerText || "").length - (b.innerText || "").length);
    rep.seletor = seletor;
    rep.count = all.length;
    rep.matches = all.slice(0, max).map(descreverEl);
    return JSON.stringify(rep, null, 2);
  }
  if (dumpSel) {
    const all = qa(dumpSel);
    rep.seletor = dumpSel;
    rep.count = all.length;
    rep.matches = all.slice(0, max).map(descreverEl);
  } else {
    rep.interativos = qa('button, [role="button"], [role="radio"], .ds-toggle-button, textarea')
      .filter(visivel)
      .slice(0, max)
      .map(descreverEl);
    const counts = {};
    qa("*").forEach((el) => {
      const tag = el.tagName.toLowerCase();
      if (tag.includes("-")) counts[tag] = (counts[tag] || 0) + 1;
    });
    rep.customElements = counts;
  }
  return JSON.stringify(rep, null, 2);
}
