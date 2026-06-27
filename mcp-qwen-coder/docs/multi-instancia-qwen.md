# Rodar várias instâncias logadas do Qwen Chat (multi-agente)

O Qwen Chat desktop não tem multi-agente nativo. Para ter vários agentes em
paralelo, a ideia é abrir **várias instâncias** do app, cada uma com seu próprio
perfil (`--user-data-dir`). O obstáculo é o **login**.

## O problema

O Qwen Chat loga via Google (OAuth). Ao terminar o login, o Google redireciona
para `qwen://callback?code=...`. No Windows, o handler desse protocolo está
registrado assim (em `HKCU\Software\Classes\qwen\shell\open\command`):

```
"C:\Users\<voce>\AppData\Local\Programs\Qwen\Qwen.exe" "%1"
```

Repare: **sem `--user-data-dir`**. Então o callback do login sempre abre o
**perfil default**, não a instância que pediu o login. Por isso "o login sempre
cai na janela 1" e não dá para autenticar diretamente uma segunda instância.

## A solução: clonar o perfil já logado

Em vez de brigar com o OAuth, loga-se **uma vez** no perfil default e copia-se o
estado de sessão para os perfis novos. Cada instância nasce logada na mesma
conta. Funciona porque é o **mesmo usuário Windows**: a chave (DPAPI) que
descriptografa os cookies do Chromium é a mesma entre perfis.

O login mora em três lugares dentro do perfil:

| Arquivo/pasta | Papel |
|---|---|
| `Network\Cookies` | cookies de sessão (SQLite) |
| `Local State` | guarda a chave que descriptografa os cookies (DPAPI) |
| `Local Storage\leveldb\` | token de sessão do app web |

> Copie sempre `Cookies` **junto com** `Local State`. Sem a chave do `Local
> State`, os cookies copiados não descriptografam.

### Via script (recomendado)

Com o Qwen **fechado** e o perfil default já logado:

```powershell
# cria/atualiza um segundo perfil
.\scripts\clone-qwen-profile.ps1 -DestDir "C:\Users\<voce>\QwenChat2"

# mais um, e fechando o Qwen automaticamente se estiver aberto
.\scripts\clone-qwen-profile.ps1 -DestDir "C:\Users\<voce>\QwenChat3" -Force
```

O script fecha o Qwen (com `-Force`), copia o perfil (sem caches), confere se os
três arquivos de login chegaram, e imprime o comando para abrir a instância.

### Manual (o que o script faz por baixo)

1. Logue normalmente no Qwen Chat (perfil default, em `%APPDATA%\Qwen`).
2. **Feche o Qwen por completo** (bandeja → Sair). Os arquivos de cookie/leveldb
   ficam travados com o app aberto e a cópia sai corrompida.
3. Copie o perfil para o novo diretório, pulando os caches regeneráveis:
   ```powershell
   robocopy "$env:APPDATA\Qwen" "C:\Users\<voce>\QwenChat2" /MIR `
     /XD Cache "Code Cache" GPUCache DawnGraphiteCache DawnWebGPUCache `
     /XF lockfile qwen-electron-debug.log
   ```
4. Abra a nova instância:
   ```
   "%LOCALAPPDATA%\Programs\Qwen\Qwen.exe" --user-data-dir="C:\Users\<voce>\QwenChat2"
   ```

Como o perfil é copiado inteiro, o `settings.json` vem junto — então a config de
servidores MCP (ex.: `ia-local`) já aparece na instância nova, sem reconfigurar.

## ⚠️ Validação pendente

Que os arquivos são copiados corretamente é verificável (o script confere
tamanhos). O que **ainda precisa ser confirmado na prática** é o comportamento
do servidor do Qwen:

- a instância clonada abre **já logada**, sem repetir o Google;
- as duas instâncias **coexistem** logadas, sem o servidor derrubar uma como
  "sessão duplicada".

Confirme isso abrindo as instâncias antes de depender disso para algo sério.

## Limites e ressalvas

- **Mesma conta.** Todas as instâncias clonadas usam a mesma conta Google. Para
  paralelismo de tarefas, serve. Se o Qwen Chat tiver algum limite de uso (não é
  publicamente anunciado para o app consumer, mas "grátis" raramente é ilimitado)
  ou anti-abuso, várias sessões robóticas da mesma conta podem ser barradas. Para
  multiplicar capacidade de verdade, use contas Google diferentes (um perfil
  logado por conta).
- **Não é isolamento de segurança.** A jaula `MCP_ALLOWED_DIR` do servidor MCP
  restringe as ferramentas de arquivo, mas não o `run_command`. Veja o README.
- **Reclonar após relogin.** Se o login do perfil default expirar e você logar de
  novo, reclone para propagar a sessão nova aos outros perfis.
