// Content script: dirige o Gemini pelo DOM. Envio simples, selecao de modelo +
// raciocinio, e o fluxo "API" (config + edicao da 2a mensagem), sem tocar no
// mouse/teclado fisico.
//
// Seletores calibrados no DOM real do Gemini (jun/2026). Se a UI mudar, ajuste SEL.

const SEL = {
  editor: 'div.ql-editor[contenteditable="true"]',
  sendBtn: 'button.send-button, button[aria-label="Enviar"], button[aria-label="Enviar mensagem"]',
  responses: 'model-response',
  doneSignal: 'message-actions, regenerate-button, copy-button',
  stopBtn: 'button[aria-label*="Parar" i], button[aria-label*="Stop" i]',
  newChat: 'a[aria-label*="Nova conversa" i], a[aria-label*="New chat" i]',
  modePicker: 'button[data-test-id="bard-mode-menu-button"]',
  modelItem: 'gem-menu-item[data-test-id^="bard-mode-option-"]',
  reasoningOpener: 'gem-menu-item[aria-haspopup="true"]',
  menuItem: 'gem-menu-item',
  userMsg: 'user-query',
  editBtn: 'button[aria-label="Editar" i]',
  editArea: 'textarea[aria-label="Editar pergunta" i], user-query textarea',
  // Barra lateral de conversas (calibrado jun/2026):
  // - convLink: cada conversa recente. O href e /app/<id> e o <id> e estavel,
  //   o mesmo que aparece na URL. Use o id como chave, nunca busca por texto.
  // - openSidebar: reabre a barra quando esta fechada (so existe nesse estado).
  //   Com a barra fechada os convLink somem do DOM, por isso abra antes.
  openSidebar: 'chat-app-side-nav-menu-button button, button[aria-label="Abrir barra lateral" i]',
  convLink: 'a.gem-nav-list-item[href^="/app/"]'
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const q = (sel, root) => (root || document).querySelector(sel);
const qa = (sel, root) => Array.from((root || document).querySelectorAll(sel));
const norm = (s) => (s || "").replace(/\s+/g, " ").trim().toLowerCase();
const visivel = (el) => { if (!el) return false; const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
const normStarts = (el, label) => norm(el.innerText).startsWith(norm(label));

function dispatchHover(el) {
  ["pointerover", "mouseover", "mouseenter", "pointermove", "mousemove"].forEach((t) =>
    el.dispatchEvent(new MouseEvent(t, { bubbles: true }))
  );
}

// ----------------------------------------------------------------------------
// Dispatcher (uma operacao de DOM por vez, serializada)
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
    selecionar_modelo: () => handleSelecionarModelo(msg.modelo, msg.raciocinio),
    configurar: () => handleConfigurar(msg),
    consultar: () => handleConsultar(msg.tarefa),
    listar_conversas: () => handleListarConversas(),
    abrir_conversa: () => handleAbrirConversa(msg.conversa_id),
    inspecionar: () => inspecionar(msg.seletor, msg.max),
    gerar_imagem: () => handleGerarImagem(msg.prompt, msg.imagem_precisa),
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
  return true; // resposta assincrona
});

// ----------------------------------------------------------------------------
// Escrita nos campos
// ----------------------------------------------------------------------------

// Composer: contenteditable do Quill.
function escreverComposer(editor, text) {
  editor.focus();
  const sel = window.getSelection();
  sel.selectAllChildren(editor);
  document.execCommand("insertText", false, text);
}

// Campo de edicao: textarea controlado por Material/React (setter nativo + input).
function escreverTextarea(field, text) {
  field.focus();
  const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set;
  setter.call(field, "");
  setter.call(field, text);
  field.dispatchEvent(new Event("input", { bubbles: true }));
}

function enviarComposer(editor) {
  const btn = q(SEL.sendBtn);
  if (btn && !btn.disabled && visivel(btn)) {
    btn.click();
    return;
  }
  ["keydown", "keyup"].forEach((t) =>
    editor.dispatchEvent(new KeyboardEvent(t, { key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true }))
  );
}

// ----------------------------------------------------------------------------
// Leitura da resposta
// ----------------------------------------------------------------------------

function ultimaResposta() {
  const r = qa(SEL.responses);
  return r[r.length - 1] || null;
}

// A resposta do turno editado: o primeiro model-response APOS o user-query alvo
// (em ordem de DOM). Anti-stale: durante a regeneracao a resposta some e volta,
// mas nunca olhamos pra antes do alvo, entao nao pegamos a resposta do turno anterior.
function respostaApos(userEl) {
  const todos = qa("user-query, " + SEL.responses);
  const i = todos.indexOf(userEl);
  for (let j = i + 1; j < todos.length; j++) {
    if (todos[j].matches(SEL.responses)) return todos[j];
  }
  return null;
}

// Remove o rotulo de acessibilidade "O Gemini disse" do inicio da resposta.
function limparResposta(text) {
  return (text || "").replace(/^\s*O Gemini (disse|respondeu)\s*/i, "").trim();
}

function extrairInfoResposta(resp, text) {
  const cleanText = limparResposta(text);
  if (!resp) return cleanText;
  
  // Encontra todas as imagens geradas na resposta
  const imgs = Array.from(resp.querySelectorAll('generated-image img, single-image img, img[src^="http"], img[src^="blob:"]'))
    .map((img) => img.src)
    .filter((src) => {
       if (!src) return false;
       // Filtra icones/assets estaticos da UI do Google
       if (src.includes("googleusercontent.com/assets/")) return false;
       if (src.includes("gstatic.com")) return false;
       return true;
    });
    
  const uniqueImgs = Array.from(new Set(imgs));
  
  if (uniqueImgs.length > 0) {
    const urlsText = uniqueImgs.map((url) => `- ${url}`).join("\n");
    return `${cleanText}\n\n[Imagens Geradas]:\n${urlsText}`;
  }
  return cleanText;
}

// Core: espera getResp() estabilizar. isStart() decide quando a geracao "comecou"
// (pra nao aceitar texto antigo). Pronto = texto estavel por idleMs E (acoes da
// resposta presentes OU geracao terminada).
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
    const gerando = !!q(SEL.stopBtn);
    const done = !!(resp && resp.querySelector(SEL.doneSignal));
    if (!started && isStart(resp, text, gerando, Date.now() - start)) started = true;

    const pronto = started && (done || !gerando);
    if (resp && text && text === last && pronto) {
      if (!stableSince) stableSince = Date.now();
      if (Date.now() - stableSince >= idleMs) return extrairInfoResposta(resp, text);
    } else {
      stableSince = 0;
      last = text;
    }
    await sleep(200);
  }
  if (last) return extrairInfoResposta(getResp(), last);
  throw new Error("Tempo esgotado esperando a resposta do Gemini.");
}

// Resposta de uma mensagem NOVA: surge um model-response alem dos `antes`.
function esperarNova(antes) {
  const getResp = () => {
    const r = qa(SEL.responses);
    return r.length > antes ? r[r.length - 1] : null;
  };
  return aguardarResposta(getResp, (resp) => !!resp);
}

// Resposta de uma EDICAO: a resposta do ultimo turno de usuario regenera. Re-acha
// o ultimo user-query a cada poll (robusto a re-render do no ao entrar em edicao).
function esperarEdicao(textoAntigo) {
  const getResp = () => {
    const u = qa(SEL.userMsg).filter(visivel);
    const a = u[u.length - 1];
    return a ? respostaApos(a) : null;
  };
  const isStart = (resp, text, gerando, elapsed) =>
    gerando || (text && text !== textoAntigo) || elapsed > 8000;
  return aguardarResposta(getResp, isStart);
}

// Gemini as vezes mostra "Qual resposta e mais util?" (A/B) e trava a UI. Escolhe a
// Opcao A pra colapsar e destravar, depois rele a resposta estabilizada.
async function resolveComparison(text) {
  const btns = qa("button").filter((b) => /mais [úu]til/i.test(b.innerText || ""));
  if (!btns.length) return text;
  btns[0].click();
  const novo = await aguardarResposta(
    () => ultimaResposta(),
    (r, t, g, e) => g || (t && t !== text) || e > 5000
  ).catch(() => null);
  return novo || text;
}

// ----------------------------------------------------------------------------
// Envio simples (one-shot)
// ----------------------------------------------------------------------------

async function handleAsk(prompt) {
  if (!prompt) throw new Error("tarefa vazia.");
  const editor = q(SEL.editor);
  if (!editor) throw new Error("Campo de entrada do Gemini nao encontrado.");

  const antes = qa(SEL.responses).length;
  escreverComposer(editor, prompt);
  await sleep(150);
  enviarComposer(editor);

  const text = await esperarNova(antes);
  return await resolveComparison(text);
}

// ----------------------------------------------------------------------------
// Geração de imagem
// ----------------------------------------------------------------------------

async function configurarCriarImagem(habilitar) {
  console.log("[gemini-web] configurarCriarImagem iniciada com habilitar =", habilitar);
  const menuBtn = q('button[aria-label="Envio e ferramentas"]');
  if (!menuBtn) throw new Error("Botao 'Envio e ferramentas' nao encontrado.");
  
  console.log("[gemini-web] abrindo menu Envio e ferramentas...");
  dispatchHover(menuBtn);
  await sleep(100);
  menuBtn.click();
  
  let targetBtn = null;
  for (let i = 0; i < 20; i++) {
    await sleep(150);
    const items = qa('button, [role="menuitemcheckbox"]');
    targetBtn = items.find((el) => /criar imagem/i.test(el.innerText || ""));
    if (targetBtn) break;
  }
  
  if (!targetBtn) {
    fecharMenu();
    throw new Error("Opcao 'Criar imagem' nao encontrada no menu de ferramentas.");
  }
  
  const isChecked = targetBtn.getAttribute("aria-checked") === "true";
  console.log("[gemini-web] Opcao Criar imagem encontrada. isChecked =", isChecked);
  
  if (habilitar && !isChecked) {
    console.log("[gemini-web] ativando Criar imagem...");
    dispatchHover(targetBtn);
    await sleep(100);
    targetBtn.click();
    await sleep(400);
  } else if (!habilitar && isChecked) {
    console.log("[gemini-web] desativando Criar imagem...");
    dispatchHover(targetBtn);
    await sleep(100);
    targetBtn.click();
    await sleep(400);
  } else {
    console.log("[gemini-web] ja no estado correto. Fechando menu.");
    fecharMenu();
    await sleep(200);
  }
}

async function blobUrlToBase64(blobUrl) {
  try {
    const r = await fetch(blobUrl);
    const blob = await r.blob();
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result.split(',')[1]);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  } catch (e) {
    console.error("[gemini-web] Erro ao converter blob:", e);
    return null;
  }
}

async function handleGerarImagem(prompt, imagemPrecisa) {
  console.log("[gemini-web] handleGerarImagem iniciada. prompt =", prompt, "imagemPrecisa =", imagemPrecisa);
  const habilitar = (imagemPrecisa === undefined || imagemPrecisa === null) ? true : !!imagemPrecisa;

  // 1. Configurar opcao "Criar imagem"
  await configurarCriarImagem(habilitar);
  await sleep(300);

  // 2. Configurar modo raciocinio
  const picker = q(SEL.modePicker);
  const currentText = picker ? (picker.innerText || "").toLowerCase() : "";
  const targetRac = habilitar ? "estendido" : "padrão";
  console.log("[gemini-web] Verificando modo de raciocinio. Atual =", currentText, "Desejado =", targetRac);
  
  if (!currentText.includes(targetRac)) {
    console.log("[gemini-web] Mudando raciocinio para:", habilitar ? "Estendido" : "Padrão");
    await handleSelecionarModelo(null, habilitar ? "Estendido" : "Padrão");
    await sleep(300);
  }

  console.log("[gemini-web] Enviando prompt...");
  const rawText = await handleAsk(prompt);
  
  const lastResp = ultimaResposta();
  const urls = [];
  const imgs = [];
  if (lastResp) {
    const imgEls = Array.from(lastResp.querySelectorAll('generated-image img, single-image img, img[src^="http"], img[src^="blob:"]'));
    for (const img of imgEls) {
      const src = img.src;
      if (!src || src.includes("googleusercontent.com/assets/") || src.includes("gstatic.com")) continue;
      
      if (src.startsWith("blob:")) {
        console.log("[gemini-web] Convertendo blob URL na pagina:", src);
        const base64 = await blobUrlToBase64(src);
        if (base64) {
          imgs.push({ url: src, base64: base64 });
        }
      } else {
        urls.push(src);
      }
    }
  }

  return JSON.stringify({
    text: rawText,
    urls: urls,
    images: imgs
  });
}


// ----------------------------------------------------------------------------
// Selecao de modelo + nivel de raciocinio
// ----------------------------------------------------------------------------

async function abrirMenuModelo() {
  const btn = q(SEL.modePicker);
  if (!btn) throw new Error("Botao do seletor de modelo nao encontrado.");
  btn.click();
  for (let i = 0; i < 8; i++) {
    await sleep(150);
    if (qa(SEL.menuItem).length) return true;
  }
  return false;
}

function fecharMenu() {
  const bd = q(".cdk-overlay-backdrop");
  if (bd) bd.click();
  document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
}

async function handleSelecionarModelo(modeloLabel, racLabel) {
  if (!modeloLabel && !racLabel) return "nada a selecionar";

  if (modeloLabel) {
    if (!(await abrirMenuModelo())) throw new Error("Menu de modelo nao abriu.");
    const item = qa(SEL.modelItem).find((el) => normStarts(el, modeloLabel));
    if (!item) { fecharMenu(); throw new Error(`Modelo '${modeloLabel}' nao encontrado no menu.`); }
    item.click();
    await sleep(500);
  }

  if (racLabel) {
    if (!(await abrirMenuModelo())) throw new Error("Menu nao reabriu pro raciocinio.");
    const opener = qa(SEL.reasoningOpener).find((el) => /racioc[íi]nio/i.test(el.innerText || ""));
    if (!opener) { fecharMenu(); throw new Error("Item 'Nivel de raciocinio' nao encontrado."); }
    dispatchHover(opener);
    await sleep(700); // submenu abre por hover (mat-menu)
    const opt = qa(SEL.menuItem).find(
      (el) => el !== opener && el.getAttribute("aria-haspopup") !== "true" && normStarts(el, racLabel)
    );
    if (!opt) { fecharMenu(); throw new Error(`Nivel de raciocinio '${racLabel}' nao encontrado.`); }
    opt.click();
    await sleep(300);
  }

  fecharMenu();
  await sleep(150);
  return `selecionado: modelo=${modeloLabel || "(mantido)"}, raciocinio=${racLabel || "(mantido)"}`;
}

// ----------------------------------------------------------------------------
// Fluxo "API": configurar (chat novo + 1a mensagem) e consultar (edita a 2a)
// ----------------------------------------------------------------------------

async function novoChat() {
  fecharMenu(); // fecha menu/overlay aberto que engoliria o clique no lugar de navegar
  await sleep(200);
  const el = q(SEL.newChat);
  if (!el) throw new Error("Botao 'Nova conversa' nao encontrado.");
  el.removeAttribute("target"); // evita que o link abra em uma ABA NOVA
  el.click();
  // Espera ATIVAMENTE o chat limpar (sem mensagens de usuario); falha alto se nao.
  for (let i = 0; i < 40; i++) {
    await sleep(150);
    if (q(SEL.editor) && qa(SEL.userMsg).filter(visivel).length === 0) return;
  }
  throw new Error("Nao consegui iniciar um chat novo (a conversa nao limpou).");
}

async function handleConfigurar(msg) {
  if (!msg.config) throw new Error("config vazia.");
  await novoChat();
  if (msg.modelo || msg.raciocinio) {
    await handleSelecionarModelo(msg.modelo, msg.raciocinio);
  }
  return await handleAsk(msg.config); // a config vira a 1a mensagem
}

async function handleConsultar(tarefa) {
  if (!tarefa) throw new Error("tarefa vazia.");
  const users = qa(SEL.userMsg).filter(visivel);
  if (users.length === 0) throw new Error("Configure primeiro com configurar_gemini.");

  // So a config existe: cria a mensagem de trabalho como mensagem nova.
  if (users.length < 2) {
    return await handleAsk(tarefa);
  }

  // Edita a ultima mensagem de usuario (a volatil).
  const alvo = users[users.length - 1];
  const respAntiga = respostaApos(alvo);
  const textoAntigo = respAntiga ? respAntiga.innerText.trim() : "";

  const editBtn = alvo.querySelector(SEL.editBtn);
  if (!editBtn) throw new Error("Botao 'Editar' nao encontrado na mensagem de trabalho.");
  editBtn.click();
  await sleep(400);

  const campo = alvo.querySelector(SEL.editArea) || q(SEL.editArea);
  if (!campo || campo.tagName !== "TEXTAREA") throw new Error("Campo de edicao (textarea) nao encontrado.");

  escreverTextarea(campo, tarefa);
  await sleep(150);

  // Confirma SO com "Atualizar" (texto exato, unico); nunca cai no envio do composer.
  const atualizar =
    qa("button", alvo).find((b) => visivel(b) && norm(b.innerText) === "atualizar") ||
    qa("button").find((b) => visivel(b) && norm(b.innerText) === "atualizar");
  if (!atualizar) throw new Error("Botao 'Atualizar' nao encontrado no bloco de edicao.");
  atualizar.click();

  const text = await esperarEdicao(textoAntigo);
  return await resolveComparison(text);
}

// ----------------------------------------------------------------------------
// Gestao de conversas (barra lateral)
//
// Achados dos testes (jun/2026), registrados pra nao redescobrir:
// - Cada conversa tem um id estavel que aparece na URL (/app/<id>) e no href do
//   link na barra. O id e a chave duravel; nao depende do contexto da IA.
// - Clicar no <a> da conversa navega de fato (a URL passa a /app/<id>).
// - Com a barra FECHADA os links somem do DOM: e preciso abrir a barra antes
//   (botao "Abrir barra lateral"). Aberta, os links voltam.
// - A lista e virtualizada (scroll infinito): so as conversas carregadas estao
//   no DOM. listar devolve as recentes carregadas, nao o historico inteiro.
// - Buscar a conversa por TEXTO (via inspecionar) derrubou o content script;
//   por isso aqui casamos por seletor CSS / href, nunca por texto.
// ----------------------------------------------------------------------------

async function garantirBarraAberta() {
  if (q(SEL.convLink)) return;            // ja tem conversas no DOM -> aberta
  const btn = q(SEL.openSidebar);
  if (btn) btn.click();
  for (let i = 0; i < 20; i++) {
    await sleep(150);
    if (q(SEL.convLink)) return;
  }
  throw new Error("Nao consegui abrir a barra lateral de conversas.");
}

const idDoHref = (href) => (href || "").split("/").pop();  // /app/<id> -> <id>

async function handleListarConversas() {
  await garantirBarraAberta();
  const convs = qa(SEL.convLink).map((a) => ({
    id: idDoHref(a.getAttribute("href")),
    titulo: norm(a.getAttribute("aria-label") || a.innerText).trim() || "(sem titulo)",
  }));
  return JSON.stringify(convs);
}

async function handleAbrirConversa(id) {
  if (!id) throw new Error("conversa_id vazio.");
  await garantirBarraAberta();
  const link = qa(SEL.convLink).find((a) => idDoHref(a.getAttribute("href")) === id);
  if (!link) {
    throw new Error(
      `Conversa '${id}' nao esta na lista carregada. A lista e virtualizada: ` +
      `role a barra, liste de novo, ou confira o id.`
    );
  }
  link.removeAttribute("target");         // evita abrir em aba nova
  link.click();
  for (let i = 0; i < 40; i++) {
    await sleep(150);
    if (location.href.includes("/app/" + id)) return location.href;
  }
  throw new Error("Cliquei na conversa mas a URL nao mudou pro id esperado.");
}

// ----------------------------------------------------------------------------
// Diagnostico (temporario): descreve o DOM real pra calibrar seletores
// ----------------------------------------------------------------------------

function descreverEl(el) {
  const out = { tag: el.tagName.toLowerCase() };
  ["id", "role", "aria-label", "aria-haspopup", "data-test-id", "placeholder", "type", "contenteditable", "href", "target", "title", "src"].forEach((a) => {
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

// TEMPORARIO (de-risk): gera uma imagem numerada na propria pagina e tenta "soltar"
// ela no campo do Gemini (arrastar-e-soltar sintetico), pra provar que da pra anexar
// imagem sem abrir a janela de arquivo do Windows. Acionado por inspecionar("@droptest").
function gerarImagemTeste() {
  const c = document.createElement("canvas");
  c.width = 640; c.height = 360;
  const x = c.getContext("2d");
  x.fillStyle = "#eef1f5"; x.fillRect(0, 0, c.width, c.height);
  const itens = [["1", "Salvar", 70, 70], ["2", "Cancelar", 340, 70], ["3", "Abrir", 70, 220], ["4", "Sair", 340, 220]];
  x.font = "22px sans-serif";
  itens.forEach(([n, label, bx, by]) => {
    x.fillStyle = "#fff"; x.fillRect(bx, by, 200, 64);
    x.strokeStyle = "#333"; x.lineWidth = 2; x.strokeRect(bx, by, 200, 64);
    x.fillStyle = "#cc1111"; x.fillRect(bx - 14, by - 14, 32, 28);
    x.fillStyle = "#fff"; x.fillText(n, bx - 6, by + 6);
    x.fillStyle = "#111"; x.fillText(label, bx + 24, by + 42);
  });
  return new Promise((res) => c.toBlob((b) => res(b), "image/png"));
}

async function dropTest() {
  const blob = await gerarImagemTeste();
  const file = new File([blob], "teste.png", { type: "image/png" });
  const achados = () => qa('img[src^="blob:"], img[src^="data:"], [class*="attachment" i], [class*="thumbnail" i], [class*="file-preview" i], [class*="uploaded" i], [data-test-id*="file" i], [data-test-id*="upload" i]')
    .filter(visivel).map(descreverEl);
  const base = achados().length;
  const alvos = ["rich-textarea", "input-area-v2", SEL.editor, "file-drop-indicator", "input-container", "chat-window"];
  const rep = { base, tentativas: [] };
  for (const seletorAlvo of alvos) {
    const alvo = q(seletorAlvo);
    if (!alvo) { rep.tentativas.push({ alvo: seletorAlvo, status: "ausente" }); continue; }
    const dt = new DataTransfer();
    dt.items.add(file);
    const r = alvo.getBoundingClientRect();
    const opt = { bubbles: true, cancelable: true, composed: true, dataTransfer: dt, clientX: r.left + r.width / 2, clientY: r.top + r.height / 2 };
    ["dragenter", "dragover", "drop"].forEach((t) => alvo.dispatchEvent(new DragEvent(t, opt)));
    await sleep(2200);
    const ach = achados();
    rep.tentativas.push({ alvo: seletorAlvo, anexos: ach.length, novos: ach.length - base, amostra: ach.slice(0, 6) });
    if (ach.length > base) { rep.sucesso = seletorAlvo; break; }
  }
  return JSON.stringify(rep, null, 2);
}

async function inspecionar(seletor, max) {
  if (seletor === "@droptest") return await dropTest();
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
  if (dumpSel) {
    const all = qa(dumpSel);
    rep.seletor = dumpSel;
    rep.count = all.length;
    rep.matches = all.slice(0, max).map(descreverEl);
  } else {
    rep.interativos = qa('button, [role="button"], [role="menuitem"], [role="menuitemradio"], [role="option"], a[aria-label], [contenteditable="true"]')
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
