import os
import shutil
import subprocess
import sys
from pathlib import Path

MONITOR_JS_CODE = """
(function() {
  if (window.__qwen_monitor_active) return;
  window.__qwen_monitor_active = true;
  console.log('[QWEN-MONITOR] Ativo.');

  let lastProcessedText = "";
  let lastUrl = "";

  function preencherTextarea(text) {
    const ta = document.querySelector('textarea.message-input-textarea, textarea[placeholder]');
    if (!ta) return false;
    ta.focus();
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set;
    setter.call(ta, text);
    
    ta.dispatchEvent(new Event('input', { bubbles: true }));
    ta.dispatchEvent(new Event('change', { bubbles: true }));
    
    // Forca trigger do React via digitação física simulada
    const spaceEvent = new KeyboardEvent('keydown', { key: ' ', code: 'Space', bubbles: true });
    ta.dispatchEvent(spaceEvent);
    ta.value += ' ';
    ta.dispatchEvent(new Event('input', { bubbles: true }));
    
    const backspaceEvent = new KeyboardEvent('keydown', { key: 'Backspace', code: 'Backspace', bubbles: true });
    ta.dispatchEvent(backspaceEvent);
    ta.value = ta.value.slice(0, -1);
    ta.dispatchEvent(new Event('input', { bubbles: true }));
    
    return true;
  }

  function clicarEnviar() {
    const btn = document.querySelector('button.send-button');
    if (btn && !btn.disabled && !btn.classList.contains('disabled')) {
      btn.click();
      return true;
    }
    return false;
  }

  // Ativação automática do modo MCP
  function garantirMCPAtivo() {
    if (window.__mcp_auto_activated) return;
    
    const plusBtn = document.querySelector('.mode-select-open');
    if (!plusBtn) return;
    
    const currentModeEl = document.querySelector('.mode-select-current-mode');
    const isMCP = currentModeEl && currentModeEl.innerText.includes('MCP');
    
    if (isMCP) {
      window.__mcp_auto_activated = true;
      return;
    }

    console.log('[QWEN-MONITOR] Ativando modo MCP automaticamente...');
    window.__mcp_auto_activated = true;
    
    plusBtn.click();
    
    setTimeout(() => {
      const dropdowns = document.querySelectorAll('.ant-dropdown, .ant-popover, [class*="dropdown"], [class*="popover"]');
      let mcpOption = null;
      let ferramentasSwitch = null;

      for (const dd of dropdowns) {
        const items = Array.from(dd.querySelectorAll('*'));
        for (const item of items) {
          if (item.children.length === 0 && item.innerText === 'MCP') {
            mcpOption = item.closest('li, div, [role="menuitem"], button') || item;
          }
          if (item.innerText === 'Ferramentas') {
            const parent = item.closest('div, li');
            if (parent) {
              ferramentasSwitch = parent.querySelector('button[role="switch"], .ant-switch, [role="checkbox"]');
            }
          }
        }
      }

      if (ferramentasSwitch) {
        const checked = ferramentasSwitch.getAttribute('aria-checked') === 'true' || 
                        ferramentasSwitch.classList.contains('ant-switch-checked') ||
                        ferramentasSwitch.classList.contains('checked');
        if (!checked) {
          ferramentasSwitch.click();
        }
      }

      if (mcpOption) {
        mcpOption.click();
      }

      setTimeout(() => {
        plusBtn.click(); // Fecha
      }, 100);
    }, 150);
  }

  function parseToolCall(text) {
    // Padrão 1: Formato XML do Qwen com parameter=
    const funcRegex = /<function=(\\w+)>([\\s\\S]*?)<\/function>/i;
    const funcMatch = text.match(funcRegex);
    if (funcMatch) {
      const toolName = funcMatch[1];
      const body = funcMatch[2];
      const args = {};
      const paramRegex = /<parameter(?:=|\\s+name=")([^">]+)">([\\s\\S]*?)<\/parameter>/gi;
      let pm;
      while ((pm = paramRegex.exec(body)) !== null) {
        args[pm[1]] = pm[2].trim();
      }
      if (Object.keys(args).length > 0) {
        return { toolName, args };
      }
    }

    // Padrão 2: Formato inline call:nome_ferramenta{prop: valor} ou nome_ferramenta(prop=valor)
    const inlineRegex = /(?:call:)?(\\w+)(?:\\(|\\{)([\\s\\S]*?)(?:\\)|\\})/i;
    const inlineMatch = text.match(inlineRegex);
    if (inlineMatch) {
      const toolName = inlineMatch[1];
      const body = inlineMatch[2];
      const args = {};
      const paramRegex = /(\\w+)\\s*(?:=|:)\\s*(?:"([^"]*)"|'([^']*)'|([^,\\s\\(\\)\\}]+))/g;
      let pm;
      while ((pm = paramRegex.exec(body)) !== null) {
        const key = pm[1];
        const val = pm[2] !== undefined ? pm[2] : (pm[3] !== undefined ? pm[3] : pm[4]);
        args[key] = val;
      }
      if (Object.keys(args).length > 0) {
        return { toolName, args };
      }
    }

    // Padrão 3: JSON bruto no chat
    const jsonRegex = /\\{[\\s\\S]*?\\}/g;
    let jsonMatch;
    while ((jsonMatch = jsonRegex.exec(text)) !== null) {
      try {
        const obj = JSON.parse(jsonMatch[0]);
        if (obj.tarefa && obj.subagente_port) {
          return {
            toolName: "delegar_para_subagente",
            args: { tarefa: obj.tarefa, subagente_port: parseInt(obj.subagente_port, 10) }
          };
        }
        if (obj.tool_name && obj.args) {
          return { toolName: obj.tool_name, args: obj.args };
        }
      } catch (e) {}
    }
    return null;
  }

  async function checkLastMessage() {
    const msgs = document.querySelectorAll('.qwen-chat-message-assistant, [class*="message-assistant"], .response-message-content.phase-answer');
    if (!msgs || msgs.length === 0) return;
    const lastMsg = msgs[msgs.length - 1];

    const isDone = lastMsg.querySelector('.copy-response-button, .response-message-footer, [class*="footer"], [class*="action"]');
    if (!isDone) return;

    const text = lastMsg.innerText || "";
    if (text === lastProcessedText || !text.trim()) return;

    const call = parseToolCall(text);
    if (!call) return;

    lastProcessedText = text;
    console.log('[QWEN-MONITOR] Detectada chamada de ferramenta:', call);

    const statusDiv = document.createElement('div');
    statusDiv.style.cssText = "background: #f0f7ff; border: 1px solid #1890ff; padding: 12px; margin: 12px 0; border-radius: 8px; color: #1890ff; font-weight: bold; font-family: sans-serif; font-size: 13px; box-shadow: 0 2px 8px rgba(24,144,255,0.15);";
    statusDiv.innerText = `[Orquestrador] Executando ferramenta "${call.toolName}" via MCP local...`;
    lastMsg.appendChild(statusDiv);

    try {
      const port = window.location.port || '8780';
      const response = await fetch(`http://127.0.0.1:${port}/tool-call`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: call.toolName,
          arguments: call.args
        })
      });
      
      const data = await response.json();
      console.log('[QWEN-MONITOR] Resposta recebida:', data);
      
      statusDiv.style.background = "#f6ffed";
      statusDiv.style.borderColor = "#52c41a";
      statusDiv.style.color = "#52c41a";
      statusDiv.style.boxShadow = "0 2px 8px rgba(82,196,26,0.15)";
      statusDiv.innerText = `[Orquestrador] Ferramenta "${call.toolName}" executada com sucesso! Enviando resposta...`;
      
      const resultText = data.result || data.error || JSON.stringify(data);
      const formattedResponse = `[Resultado da ferramenta ${call.toolName}]:\\n${resultText}`;
      
      setTimeout(() => {
        if (preencherTextarea(formattedResponse)) {
          setTimeout(() => {
            clicarEnviar();
            statusDiv.remove();
          }, 300);
        }
      }, 500);

    } catch (err) {
      console.error('[QWEN-MONITOR] Erro em /tool-call:', err);
      statusDiv.style.background = "#fff2f0";
      statusDiv.style.borderColor = "#ff4d4f";
      statusDiv.style.color = "#ff4d4f";
      statusDiv.style.boxShadow = "0 2px 8px rgba(255,77,79,0.15)";
      statusDiv.innerText = `[Orquestrador] Erro ao executar ${call.toolName}: ${err.message}`;
    }
  }

  function periodicChecks() {
    if (window.location.href !== lastUrl) {
      lastUrl = window.location.href;
      window.__mcp_auto_activated = false;
    }
    garantirMCPAtivo();
    checkLastMessage();
  }

  const observer = new MutationObserver(() => {
    periodicChecks();
  });
  
  observer.observe(document.body, { childList: true, subtree: true });
  setInterval(periodicChecks, 2000);
  console.log('[QWEN-MONITOR] MutationObserver e Interval registrado.');
})();
"""

def patch_qwen():
    print("=== Iniciando Patch Cirurgico no Qwen Chat Desktop ===")
    
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        print("Erro: variavel LOCALAPPDATA nao encontrada.")
        sys.exit(1)
        
    qwen_dir = Path(local_app_data) / "Programs" / "Qwen"
    resources_dir = qwen_dir / "resources"
    asar_path = resources_dir / "app.asar"
    backup_path = resources_dir / "app.asar.bak"
    
    if not asar_path.exists():
        print(f"Erro: app.asar nao encontrado em: {asar_path}")
        sys.exit(1)
        
    workspace = Path(r"C:\Users\tiago\Desktop\mcp-ultra-reborn\qwen-patch-temp")
    extracted_dir = workspace / "extracted"
    
    print(f"Limpando area temporaria...")
    if workspace.exists():
        shutil.rmtree(workspace, ignore_errors=True)
    os.makedirs(extracted_dir, exist_ok=True)
    
    if not backup_path.exists():
        print(f"Criando backup original...")
        shutil.copy2(asar_path, backup_path)
    else:
        print(f"Restaurando do backup limpo para aplicar o patch fresco...")
        shutil.copy2(backup_path, asar_path)
        
    try:
        subprocess.run(
            f'npx -y asar extract "{asar_path}" "{extracted_dir}"',
            shell=True,
            check=True
        )
    except Exception as e:
        print("Erro na extracao:", e)
        sys.exit(1)
        
    main_js_path = extracted_dir / "out" / "main" / "index.js"
    content = main_js_path.read_text(encoding="utf-8")
    
    original_ipc_line = 'electron.ipcMain.handle("mcp_client_tool_call", mcpClientToolCall);'
    patched_ipc_line = """electron.ipcMain.handle("mcp_client_tool_call", async (event, params) => {
    console.log('[PATCH-MCP] Interceptada chamada de ferramenta:', params);
    try {
      const res = await mcpClientToolCall(event, params);
      console.log('[PATCH-MCP] Retorno da ferramenta executada com sucesso.');
      return res;
    } catch (e) {
      console.error('[PATCH-MCP] Erro ao chamar ferramenta:', e);
      throw e;
    }
  });"""
  
    if original_ipc_line in content:
        content = content.replace(original_ipc_line, patched_ipc_line)
        print("-> Hook IPC de ferramentas MCP injetado com sucesso.")
    else:
        print("Aviso: Linha original do IPC mcp_client_tool_call nao encontrada.")
        
    original_register_ipc_end = """    if (type === "TEST_EVENT") {
      sendEvent("TEST_EVENT", "this msg comes from main process");
    }
  });
};"""

    # Escapa aspas e barras para injetar de forma segura no index.js do Electron
    escaped_monitor_js = MONITOR_JS_CODE.replace('\\', '\\\\').replace('`', '\\`').replace('$', '\\$')

    patched_register_ipc_end = """    if (type === "TEST_EVENT") {
      sendEvent("TEST_EVENT", "this msg comes from main process");
    }
  });

  // --- INICIO DO PATCH HTTP E AGENT LOOP ---
  try {
    const patch_http = require('http');
    const http_port = parseInt(process.env.QWEN_HTTP_PORT || '8780', 10);

    const server = patch_http.createServer(async (req, res) => {
      res.setHeader('Content-Type', 'application/json');
      res.setHeader('Access-Control-Allow-Origin', '*');
      res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
      res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

      if (req.method === 'OPTIONS') {
        res.writeHead(200);
        res.end();
        return;
      }

      try {
        const url = new URL(req.url, `http://${req.headers.host || '127.0.0.1'}`);
        
        if (url.pathname === '/status') {
          res.writeHead(200);
          res.end(JSON.stringify({
            status: 'ok',
            appVersion: electron.app.getVersion(),
            windowExists: !!exports.mainWindow && !exports.mainWindow.isDestroyed(),
            webviewReady: !!webViewContents && !webViewContents.isDestroyed(),
            webviewUrl: webViewContents && !webViewContents.isDestroyed() ? webViewContents.getURL() : null
          }));
          return;
        }

        if (url.pathname === '/tool-call' && req.method === 'POST') {
          let body = '';
          req.on('data', chunk => body += chunk);
          req.on('end', async () => {
            try {
              const params = JSON.parse(body);
              console.log('[PATCH-HTTP] Recebida chamada /tool-call:', params);
              const eventMock = { sender: webViewContents };
              const result = await mcpClientToolCall(eventMock, params);
              res.writeHead(200);
              res.end(JSON.stringify({ result }));
            } catch (err) {
              console.error('[PATCH-HTTP] Erro em /tool-call:', err);
              res.writeHead(500);
              res.end(JSON.stringify({ error: err.message }));
            }
          });
          return;
        }

        if (url.pathname === '/evaluate' && req.method === 'POST') {
          let body = '';
          req.on('data', chunk => body += chunk);
          req.on('end', async () => {
            try {
              if (!webViewContents || webViewContents.isDestroyed()) {
                res.writeHead(400);
                res.end(JSON.stringify({ error: 'Webview nao carregada ou ja destruida.' }));
                return;
              }
              const result = await webViewContents.executeJavaScript(body);
              res.writeHead(200);
              res.end(JSON.stringify({ result }));
            } catch (err) {
              res.writeHead(500);
              res.end(JSON.stringify({ error: err.message }));
            }
          });
          return;
        }

        res.writeHead(404);
        res.end(JSON.stringify({ error: 'Endpoint nao encontrado' }));
      } catch (err) {
        res.writeHead(500);
        res.end(JSON.stringify({ error: 'Internal Error: ' + err.message }));
      }
    });

    server.on('error', (err) => {
      console.error('[PATCH] Erro no servidor HTTP:', err);
    });

    server.listen(http_port, '127.0.0.1', () => {
      console.log(`[PATCH] Servidor HTTP interno rodando em http://127.0.0.1:${http_port}`);
    });

    // Loop de injeção contínua robusta do monitor de DOM
    const monitorJs = `{escaped_monitor_js}`;
    
    const tentarInjetar = async () => {
      try {
        if (!webViewContents || webViewContents.isDestroyed()) return;
        const ativo = await webViewContents.executeJavaScript("window.__qwen_monitor_active || false");
        if (!ativo) {
          console.log('[PATCH-DOM] Injetando monitor de DOM...');
          await webViewContents.executeJavaScript(monitorJs);
          console.log('[PATCH-DOM] Monitor de DOM injetado com sucesso.');
        }
      } catch (e) {
        // Ignora erros enquanto a página carrega
      }
    };

    electron.ipcMain.removeHandler("webview-loaded");
    electron.ipcMain.handle("webview-loaded", async (event, id) => {
      const res = await webviewLoaded(event, id);
      if (webViewContents && !webViewContents.isDestroyed()) {
        console.log('[PATCH-DOM] Webview carregada. Configurando escutas e timer...');
        
        // Injeta imediatamente
        tentarInjetar();

        // Injeta a cada evento de navegação ou fim de load
        webViewContents.on('dom-ready', tentarInjetar);
        webViewContents.on('did-navigate', tentarInjetar);
        webViewContents.on('did-navigate-in-page', tentarInjetar);

        // Timer de segurança de 3 segundos para re-injetar caso suma por qualquer motivo
        if (global.qwen_monitor_interval) clearInterval(global.qwen_monitor_interval);
        global.qwen_monitor_interval = setInterval(tentarInjetar, 3000);
      }
      return res;
    });

  } catch (err) {
    console.error('[PATCH] Erro durante inicializacao do patch HTTP:', err);
  }
  // --- FIM DO PATCH HTTP ---
};""".replace('{escaped_monitor_js}', escaped_monitor_js)

    if original_register_ipc_end in content:
        content = content.replace(original_register_ipc_end, patched_register_ipc_end)
        print("-> Servidor HTTP e Agent Loop injetados em registerIPC.")
    else:
        original_register_ipc_end_crlf = original_register_ipc_end.replace('\n', '\r\n')
        patched_register_ipc_end_crlf = patched_register_ipc_end.replace('\n', '\r\n')
        if original_register_ipc_end_crlf in content:
            content = content.replace(original_register_ipc_end_crlf, patched_register_ipc_end_crlf)
            print("-> Servidor HTTP e Agent Loop injetados em registerIPC (CRLF).")
        else:
            print("Erro: Nao consegui localizar o final da funcao registerIPC no arquivo.")
            sys.exit(1)
            
    main_js_path.write_text(content, encoding="utf-8")
    
    print("Recompactando app.asar...")
    try:
        subprocess.run(
            f'npx -y asar pack "{extracted_dir}" "{asar_path}"',
            shell=True,
            check=True
        )
        print("Patch aplicado com sucesso!")
    except Exception as e:
        print("Erro na recompactacao:", e)
        shutil.copy2(backup_path, asar_path)
        sys.exit(1)
        
    shutil.rmtree(workspace, ignore_errors=True)
    print("=== Concluido! ===")

if __name__ == "__main__":
    patch_qwen()
