// Service worker: mantem a conexao WebSocket com o MCP local e roteia as acoes
// pra aba do DeepSeek.
//
// O service worker do MV3 hiberna em ~30s. Pra conexao nao cair: o servidor manda
// um ping a cada 20s e um alarme reconecta caso o worker tenha morrido.

const WS_URL = "ws://127.0.0.1:8766";
const ACTIONS = ["ask", "configurar", "consultar", "selecionar_modo", "inspecionar"];
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
  ws.onopen = () => console.log("[deepseek-bridge] WS conectado");
  ws.onerror = () => { try { ws.close(); } catch (e) {} };
  ws.onclose = () => { ws = null; setTimeout(ensureConnected, 2000); };
  ws.onmessage = async (ev) => {
    let msg;
    try { msg = JSON.parse(ev.data); } catch (e) { return; }
    if (msg.type === "ping") return;
    if (!ACTIONS.includes(msg.type)) return;
    try {
      const text = await runOnDeepseek(msg);
      send({ type: "answer", id: msg.id, text });
    } catch (e) {
      send({ type: "error", id: msg.id, message: String((e && e.message) || e) });
    }
  };
}

function send(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

async function runOnDeepseek(msg) {
  const tab = await findDeepseekTab();
  if (!tab) throw new Error("Nenhuma aba do DeepSeek aberta.");
  const payload = {
    type: msg.type,
    prompt: msg.prompt,
    tarefa: msg.tarefa,
    config: msg.config,
    modo: msg.modo,
    pensamento: msg.pensamento,
    pesquisa: msg.pesquisa,
    seletor: msg.seletor,
    max: msg.max,
  };
  try {
    return await sendToTab(tab.id, payload);
  } catch (e) {
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content.js"] });
    return await sendToTab(tab.id, payload);
  }
}

async function sendToTab(tabId, payload) {
  const res = await chrome.tabs.sendMessage(tabId, payload);
  if (res && res.ok) return res.text;
  throw new Error((res && res.error) || "Falha no content script.");
}

// Fixa a aba do DeepSeek usada na primeira acao e reusa nas seguintes.
let pinnedTabId = null;
async function findDeepseekTab() {
  if (pinnedTabId != null) {
    try {
      const t = await chrome.tabs.get(pinnedTabId);
      if (t && /chat\.deepseek\.com/.test(t.url || "")) return t;
    } catch (e) {}
    pinnedTabId = null;
  }
  const tabs = await chrome.tabs.query({ url: "https://chat.deepseek.com/*" });
  const t = tabs && tabs[0];
  if (t) pinnedTabId = t.id;
  return t;
}

chrome.alarms.create("keepalive", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener((a) => { if (a.name === "keepalive") ensureConnected(); });
chrome.runtime.onStartup.addListener(ensureConnected);
chrome.runtime.onInstalled.addListener(ensureConnected);

ensureConnected();
