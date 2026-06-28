// Service worker: mantem a conexao WebSocket com o MCP local e roteia as tarefas
// pra aba do Gemini.
//
// O service worker do MV3 hiberna em ~30s. Pra conexao nao cair: o servidor manda
// um ping a cada 20s (atividade no socket reseta o timer de ocio) e um alarme
// reconecta caso o worker tenha morrido mesmo assim.

const WS_URL = "ws://127.0.0.1:8765";
let ws = null;

function ensureConnected() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  connect();
}

function connect() {
  try {
    ws = new WebSocket(WS_URL);
  } catch (e) {
    ws = null;
    return;
  }
  ws.onopen = () => console.log("[gemini-bridge] WS conectado");
  ws.onerror = () => { try { ws.close(); } catch (e) {} };
  ws.onclose = () => { ws = null; setTimeout(ensureConnected, 2000); };
  ws.onmessage = async (ev) => {
    let msg;
    try { msg = JSON.parse(ev.data); } catch (e) { return; }
    if (msg.type === "ping") return;        // so pra manter o worker acordado
    if (!ACTIONS.includes(msg.type)) return;
    try {
      let text = await runOnGemini(msg);
      if (msg.type === "gerar_imagem") {
        try {
          const data = JSON.parse(text);
          const imgs = [];
          for (const url of (data.urls || [])) {
            console.log("[gemini-web] Baixando no background:", url);
            const base64 = await baixarImagemBase64(url);
            if (base64) {
              imgs.push({ url, base64 });
            }
          }
          text = JSON.stringify({
            text: data.text,
            images: imgs
          });
        } catch (e) {
          console.error("[gemini-web] Falha ao processar imagens no background:", e);
        }
      }
      send({ type: "answer", id: msg.id, text });
    } catch (e) {
      send({ type: "error", id: msg.id, message: String((e && e.message) || e) });
    }
  };
}

const ACTIONS = ["ask", "configurar", "consultar", "selecionar_modelo", "listar_conversas", "abrir_conversa", "inspecionar", "gerar_imagem"];

function send(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

async function runOnGemini(msg) {
  const tab = await findGeminiTab();
  if (!tab) throw new Error("Nenhuma aba do Gemini aberta.");
  // Repassa so os campos da acao pro content script (sem o id de controle).
  const payload = {
    type: msg.type,
    prompt: msg.prompt,
    tarefa: msg.tarefa,
    config: msg.config,
    modelo: msg.modelo,
    raciocinio: msg.raciocinio,
    seletor: msg.seletor,
    max: msg.max,
    conversa_id: msg.conversa_id,
    imagem_precisa: msg.imagem_precisa,
  };
  try {
    return await sendToTab(tab.id, payload);
  } catch (e) {
    // content script ausente (aba aberta antes do reload da extensao): injeta e tenta de novo
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content.js"] });
    return await sendToTab(tab.id, payload);
  }
}

async function sendToTab(tabId, payload) {
  const res = await chrome.tabs.sendMessage(tabId, payload);
  if (res && res.ok) return res.text;
  throw new Error((res && res.error) || "Falha no content script.");
}

// Fixa a aba do Gemini usada na primeira acao e reusa nas seguintes, pra config e
// consulta nao cairem em abas diferentes. Revalida se a aba sumiu.
let pinnedTabId = null;
async function findGeminiTab() {
  if (pinnedTabId != null) {
    try {
      const t = await chrome.tabs.get(pinnedTabId);
      if (t && /gemini\.google\.com/.test(t.url || "")) return t;
    } catch (e) {}
    pinnedTabId = null;
  }
  const tabs = await chrome.tabs.query({ url: "https://gemini.google.com/*" });
  const t = tabs && tabs[0];
  if (t) pinnedTabId = t.id;
  return t;
}

// Rede de seguranca: acorda o worker e reconecta se a conexao caiu.
chrome.alarms.create("keepalive", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener((a) => { if (a.name === "keepalive") ensureConnected(); });
chrome.runtime.onStartup.addListener(ensureConnected);
chrome.runtime.onInstalled.addListener(ensureConnected);

ensureConnected();

function arrayBufferToBase64(buffer) {
  let binary = '';
  const bytes = new Uint8Array(buffer);
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

async function baixarImagemBase64(url) {
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const buffer = await r.arrayBuffer();
    return arrayBufferToBase64(buffer);
  } catch (e) {
    console.error("[gemini-web] Erro ao baixar imagem no background:", e);
    return null;
  }
}
