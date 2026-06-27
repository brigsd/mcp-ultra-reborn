<#
.SYNOPSIS
    Clona um perfil JA LOGADO do Qwen Chat (desktop) para um novo
    --user-data-dir, permitindo rodar varias instancias logadas da MESMA conta
    sem refazer o login do Google em cada uma.

.DESCRIPTION
    O Qwen Chat usa login via Google (OAuth). O handler do protocolo `qwen://`
    registrado no Windows aponta para o Qwen.exe SEM --user-data-dir, entao o
    callback do login sempre cai no perfil default. Resultado: nao da para logar
    diretamente numa segunda instancia.

    A saida e logar uma vez (perfil default) e copiar o estado de sessao
    (cookies + Local State + Local Storage) para um novo perfil. Funciona porque
    e o mesmo usuario Windows: a chave DPAPI que descriptografa os cookies e a
    mesma. O Qwen precisa estar FECHADO durante a copia (arquivos travados).

.PARAMETER DestDir
    Pasta do novo perfil (vira o valor de --user-data-dir). Ex.:
    C:\Users\voce\QwenChat2

.PARAMETER SrcDir
    Perfil de origem, ja logado. Padrao: %APPDATA%\Qwen (perfil default).

.PARAMETER Force
    Fecha o Qwen via taskkill se estiver aberto e sobrescreve o DestDir mesmo
    que ja exista com conteudo.

.EXAMPLE
    .\clone-qwen-profile.ps1 -DestDir "C:\Users\voce\QwenChat2"

.EXAMPLE
    .\clone-qwen-profile.ps1 -DestDir "C:\Users\voce\QwenChat3" -Force
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$DestDir,
    [string]$SrcDir = "$env:APPDATA\Qwen",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $SrcDir)) {
    throw "Perfil de origem nao encontrado: $SrcDir (o Qwen ja foi instalado e logado?)"
}

# 1) Qwen precisa estar fechado (cookies/leveldb ficam travados com o app aberto).
$proc = Get-Process -Name "Qwen" -ErrorAction SilentlyContinue
if ($proc) {
    if ($Force) {
        Write-Host "Qwen aberto -> encerrando via taskkill (-Force)..." -ForegroundColor Yellow
        taskkill /F /IM Qwen.exe /T 2>$null | Out-Null
        Start-Sleep -Seconds 2
    } else {
        throw "Qwen esta aberto. Feche-o (icone na bandeja -> Sair) ou rode com -Force."
    }
}

# 2) Protege contra sobrescrever um destino com conteudo por engano.
if ((Test-Path $DestDir) -and (Get-ChildItem $DestDir -Force -ErrorAction SilentlyContinue) -and (-not $Force)) {
    throw "DestDir ja existe e nao esta vazio: $DestDir. Use -Force para sobrescrever."
}

# 3) Clona o perfil, sem os caches regeneraveis nem o lockfile/log.
Write-Host "Clonando '$SrcDir' -> '$DestDir' ..." -ForegroundColor Cyan
robocopy $SrcDir $DestDir /MIR `
    /XD Cache "Code Cache" GPUCache DawnGraphiteCache DawnWebGPUCache `
    /XF lockfile qwen-electron-debug.log `
    /NFL /NDL /NP /R:1 /W:1 | Out-Null
$rc = $LASTEXITCODE
if ($rc -ge 8) { throw "robocopy falhou (exit=$rc)." }

# 4) Confere os arquivos que carregam o login.
$ok = $true
function Check-Size($rel, [switch]$Dir) {
    $sp = Join-Path $SrcDir $rel; $dp = Join-Path $DestDir $rel
    if ($Dir) {
        $s = (Get-ChildItem $sp -EA SilentlyContinue | Measure-Object Length -Sum).Sum
        $d = (Get-ChildItem $dp -EA SilentlyContinue | Measure-Object Length -Sum).Sum
    } else {
        $s = (Get-Item $sp -EA SilentlyContinue).Length
        $d = (Get-Item $dp -EA SilentlyContinue).Length
    }
    $match = ($s -eq $d) -and ($s -gt 0)
    if (-not $match) { $script:ok = $false }
    "{0,-22} origem={1,-9} destino={2,-9} {3}" -f $rel, $s, $d, $(if ($match) { "OK" } else { "FALHA" })
}
Write-Host "`n=== Verificacao do estado de login ===" -ForegroundColor Cyan
Check-Size "Network\Cookies"
Check-Size "Local State"
Check-Size "Local Storage\leveldb" -Dir

if (-not $ok) { throw "Algum arquivo de login nao foi copiado corretamente." }

# 5) Mostra como abrir a nova instancia.
$exe = "$env:LOCALAPPDATA\Programs\Qwen\Qwen.exe"
Write-Host "`nPronto. Abra a nova instancia com:" -ForegroundColor Green
Write-Host ('  "{0}" --user-data-dir="{1}"' -f $exe, $DestDir)
Write-Host "`nConfirme na tela: deve abrir JA LOGADO, e as duas instancias devem"
Write-Host "coexistir sem uma derrubar o login da outra (sessao duplicada)."
