import os
import shutil
import subprocess
import sys
from pathlib import Path

def patch_qwen():
    print("=== Iniciando Patch Cirurgico no Qwen Chat Desktop ===")
    
    # 1. Caminhos
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
        
    # 2. Workspace Temporario
    workspace = Path(r"C:\Users\tiago\Desktop\mcp-ultra-reborn\qwen-patch-temp")
    extracted_dir = workspace / "extracted"
    
    print(f"Limpando area temporaria...")
    if workspace.exists():
        shutil.rmtree(workspace, ignore_errors=True)
    os.makedirs(extracted_dir, exist_ok=True)
    
    # 3. Backup
    if not backup_path.exists():
        print(f"Criando backup original...")
        shutil.copy2(asar_path, backup_path)
    else:
        print(f"Restaurando do backup limpo para aplicar o patch fresco...")
        shutil.copy2(backup_path, asar_path)
        
    # 4. Extrai
    try:
        subprocess.run(
            f'npx -y asar extract "{asar_path}" "{extracted_dir}"',
            shell=True,
            check=True
        )
    except Exception as e:
        print("Erro na extracao:", e)
        sys.exit(1)
        
    # 5. Modificações cirurgicas no index.js
    main_js_path = extracted_dir / "out" / "main" / "index.js"
    content = main_js_path.read_text(encoding="utf-8")
    
    # Substitui o handler IPC original pelo nosso interceptador wrapper
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
        
    # Injeta o servidor HTTP interno no final da funcao registerIPC
    original_register_ipc_end = """    if (type === "TEST_EVENT") {
      sendEvent("TEST_EVENT", "this msg comes from main process");
    }
  });
};"""

    patched_register_ipc_end = """    if (type === "TEST_EVENT") {
      sendEvent("TEST_EVENT", "this msg comes from main process");
    }
  });

  // --- INICIO DO PATCH HTTP ---
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
      try {
        const patchFs = require('fs');
        patchFs.writeFileSync('C:\\\\Users\\\\tiago\\\\Desktop\\\\mcp-ultra-reborn\\\\patch-http-error.txt', 'Erro assincrono HTTP: ' + err.stack);
      } catch (e) {}
    });

    server.listen(http_port, '127.0.0.1', () => {
      console.log(`[PATCH] Servidor HTTP interno rodando em http://127.0.0.1:${http_port}`);
    });

    // Interceptor de rede na sessao default
    const ses = electron.session.defaultSession;
    ses.webRequest.onCompleted({ urls: ['https://chat.qwen.ai/api/chat/stream*'] }, (details) => {
      console.log('[PATCH-NET] Requisicao de stream concluida:', details.url);
    });

  } catch (err) {
    try {
      const patchFs = require('fs');
      patchFs.writeFileSync('C:\\\\Users\\\\tiago\\\\Desktop\\\\mcp-ultra-reborn\\\\patch-http-error.txt', 'Erro de inicializacao HTTP: ' + err.stack);
    } catch (e) {}
    console.error('[PATCH] Erro durante inicializacao do patch HTTP:', err);
  }
  // --- FIM DO PATCH HTTP ---
};"""

    if original_register_ipc_end in content:
        content = content.replace(original_register_ipc_end, patched_register_ipc_end)
        print("-> Servidor HTTP e interceptor de rede injetados em registerIPC.")
    else:
        original_register_ipc_end_crlf = original_register_ipc_end.replace('\n', '\r\n')
        patched_register_ipc_end_crlf = patched_register_ipc_end.replace('\n', '\r\n')
        if original_register_ipc_end_crlf in content:
            content = content.replace(original_register_ipc_end_crlf, patched_register_ipc_end_crlf)
            print("-> Servidor HTTP e interceptor de rede injetados em registerIPC (CRLF).")
        else:
            print("Erro: Nao consegui localizar o final da funcao registerIPC no arquivo.")
            sys.exit(1)
            
    # Grava o novo index.js
    main_js_path.write_text(content, encoding="utf-8")
    
    # 6. Recompacta
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
