import os
import subprocess
import sys
import time
import urllib.request
import json
from pathlib import Path

def set_window_title(port, title):
    try:
        url = f"http://127.0.0.1:{port}/evaluate"
        js_code = f"document.title = '{title}'; const el = document.querySelector('.title-bar-title-text, [class*=\"title\"]'); if(el) el.innerText = '{title}';"
        data = js_code.encode('utf-8')
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=2) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception:
        pass

def main():
    print("=== Iniciando Ecossistema Multi-Agente Qwen (Metodo Grafico Interativo) ===")
    
    # 1. Parar processos do Qwen rodando no momento
    print("Fechando instâncias do Qwen ativas...")
    if sys.platform == "win32":
        subprocess.run("taskkill /f /im Qwen.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5)
        
    local_app_data = os.environ.get("LOCALAPPDATA")
    user_profile = os.environ.get("USERPROFILE")
    if not local_app_data or not user_profile:
        print("Erro: Variaveis de ambiente basicas nao encontradas.")
        sys.exit(1)
        
    qwen_exe = Path(local_app_data) / "Programs" / "Qwen" / "Qwen.exe"
    dest_profile = Path(user_profile) / "QwenChat2"
    workspace = Path(r"C:\Users\tiago\Desktop\mcp-ultra-reborn")
    
    if not qwen_exe.exists():
        print(f"Erro: Qwen.exe nao encontrado em: {qwen_exe}")
        sys.exit(1)
        
    # 2. Clonar perfil se nao existir
    if not dest_profile.exists():
        print(f"Clonando perfil padrão para subagente em: {dest_profile}...")
        clone_script = workspace / "mcp-qwen-coder" / "scripts" / "clone-qwen-profile.ps1"
        if clone_script.exists():
            try:
                subprocess.run(
                    f'powershell.exe -ExecutionPolicy Bypass -File "{clone_script}" -DestDir "{dest_profile}" -Force',
                    shell=True,
                    check=True
                )
                print("Perfil clonado com sucesso.")
            except subprocess.CalledProcessError as e:
                print(f"Erro ao clonar perfil via PowerShell: {e}")
                sys.exit(1)
        else:
            print("Erro: Script de clonagem clone-qwen-profile.ps1 nao encontrado.")
            sys.exit(1)
            
    # 3. Cria arquivos Batch temporários na área do projeto para inicialização gráfica real
    bat1_path = workspace / "launch_agent1.bat"
    bat2_path = workspace / "launch_agent2.bat"
    
    bat1_content = f"""@echo off
set QWEN_HTTP_PORT=8780
start "" "{qwen_exe}" --remote-debugging-port=9222
exit
"""
    
    bat2_content = f"""@echo off
set QWEN_HTTP_PORT=8781
start "" "{qwen_exe}" --remote-debugging-port=9223 --user-data-dir="{dest_profile}"
exit
"""
    
    bat1_path.write_text(bat1_content, encoding="utf-8")
    bat2_path.write_text(bat2_content, encoding="utf-8")
    
    # 4. Executa os Batchs via explorer.exe para rodar na sessao grafica do usuario
    print("Iniciando Instância 1 (Orquestrador) via Shell do Windows...")
    subprocess.run(f'explorer.exe "{bat1_path}"', shell=True)
    
    time.sleep(2)
    
    print("Iniciando Instância 2 (Subagente Executor) via Shell do Windows...")
    subprocess.run(f'explorer.exe "{bat2_path}"', shell=True)
    
    # Limpa os arquivos temporários
    time.sleep(3)
    try:
        bat1_path.unlink(missing_ok=True)
        bat2_path.unlink(missing_ok=True)
    except Exception:
        pass
        
    # 5. Define os títulos das janelas na barra de tarefas para identificação
    print("Identificando e renomeando as janelas na barra de tarefas...")
    time.sleep(4) # Espera o boot dos servidores HTTP
    set_window_title(8780, "QWEN ORQUESTRADOR (8780)")
    set_window_title(8781, "QWEN SUBAGENTE CODER (8781)")
    
    print("\nAmbos os agentes foram disparados com sucesso no Desktop do usuário!")
    print("Verifique os nomes das janelas na sua barra de tarefas para saber qual é qual!")

if __name__ == "__main__":
    main()
