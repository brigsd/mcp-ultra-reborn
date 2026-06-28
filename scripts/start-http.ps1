# Sobe os MCPs de delegação web em modo HTTP persistente.
#
# No modo HTTP cada servidor fica de pé sozinho numa porta própria; os hosts
# (Claude Code, Codex, Antigravity) apenas se conectam pela URL, então a conexão
# sobrevive a reloads/re-syncs do host. Deixe esta janela aberta enquanto usa.
#
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\start-http.ps1
#
# Endpoints:
#   gemini-web    http://127.0.0.1:8775/mcp   (bridge WebSocket 8765)
#   deepseek-web  http://127.0.0.1:8776/mcp   (bridge WebSocket 8766)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

$env:GEMINI_TRANSPORT = "http"
$env:DEEPSEEK_TRANSPORT = "http"

Write-Host "Subindo gemini-web   em http://127.0.0.1:8775/mcp"
Start-Process -FilePath "python" -ArgumentList "`"$root\mcp-gemini-web\gemini_mcp.py`""

Write-Host "Subindo deepseek-web em http://127.0.0.1:8776/mcp"
Start-Process -FilePath "python" -ArgumentList "`"$root\mcp-deepseek-web\deepseek_mcp.py`""

Write-Host ""
Write-Host "Servidores HTTP no ar. Registre no host como URL (type: http) e abra"
Write-Host "as abas do Gemini e do DeepSeek logadas no Chrome com as extensoes."
