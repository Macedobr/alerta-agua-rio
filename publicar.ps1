# publicar.ps1 - publica o Alerta Agua RJ no GitHub (Actions + Pages)
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File .\publicar.ps1
#
# O script:
#   1. instala Git e GitHub CLI pelo winget (se faltarem)
#   2. pede o login do GitHub (abre o navegador)
#   3. cria um repositorio publico e envia o codigo
#   4. grava o token do Telegram como secret
#   5. liga o GitHub Pages na pasta /docs
#   6. dispara a primeira execucao
#
# Para ver o que ele faria, sem mudar nada:  -Simular
#
# Texto sem acentos de proposito: o PowerShell 5.1 le arquivos .ps1 sem BOM
# como ANSI e os acentos apareceriam corrompidos.

[CmdletBinding()]
param(
    [string]$TelegramToken,
    [string]$ChatId,
    [string]$NomeRepo = "alerta-agua-rio",
    [switch]$Simular
)

# "Continue" de proposito: no PowerShell 5.1, qualquer linha que o gh ou o git
# escrevem no stderr vira erro FATAL quando isto esta em "Stop" - e o gh usa o
# stderr para mostrar o codigo de login. Cada passo critico confere o exit code.
$ErrorActionPreference = "Continue"
$Raiz = $PSScriptRoot
if (-not $Raiz) { $Raiz = (Get-Location).Path }

function Titulo($texto) {
    Write-Host ""
    Write-Host "== $texto ==" -ForegroundColor Cyan
}
function Info($texto) { Write-Host "   $texto" }
function Falhou($texto) {
    Write-Host ""
    Write-Host "   ERRO: $texto" -ForegroundColor Red
    exit 1
}

function Achar($nome, $caminhos) {
    $cmd = Get-Command $nome -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($c in $caminhos) { if (Test-Path $c) { return $c } }
    return $null
}

function Instalar($id, $nome, $caminhoFinal) {
    if (Test-Path $caminhoFinal) { return $caminhoFinal }
    Info "instalando $nome pelo winget (pode pedir confirmacao do Windows)..."
    # Out-Host: mostra o progresso sem deixar a saida entrar no valor de retorno.
    & winget install --id $id -e --source winget --accept-package-agreements --accept-source-agreements --silent 2>&1 | Out-Host
    if (Test-Path $caminhoFinal) { return $caminhoFinal }
    return $null
}

Write-Host ""
Write-Host "  Alerta Agua RJ - publicacao no GitHub" -ForegroundColor White
Write-Host "  pasta: $Raiz"

# ---------------------------------------------------------------------------
if ($Simular) {
    Titulo "Simulacao (nada sera alterado)"
    Info "1. instalaria Git e GitHub CLI, se faltassem"
    Info "2. pediria login no GitHub (navegador, codigo de 8 digitos)"
    Info "3. git init + commit + gh repo create --public --push"
    Info "4. gravaria TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID como secrets"
    Info "5. ligaria o Pages em main:/docs"
    Info "6. rodaria o workflow 'monitor.yml' uma vez"
    Info ""
    Info "Repositorio: https://github.com/SEU-USUARIO/$NomeRepo"
    Info "Painel:      https://SEU-USUARIO.github.io/$NomeRepo/"
    exit 0
}

# ---------------------------------------------------------------------------
Titulo "1/6 Ferramentas"

$git = Achar "git" @(
    "C:\Program Files\Git\cmd\git.exe",
    "C:\Program Files (x86)\Git\cmd\git.exe",
    "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe"
)
if (-not $git) {
    $git = Instalar "Git.Git" "Git" "C:\Program Files\Git\cmd\git.exe" | Select-Object -Last 1
}
if (-not $git -or -not (Test-Path $git)) {
    Falhou "Git nao encontrado. Instale manualmente: winget install Git.Git"
}
Info "Git: $git"

$gh = Achar "gh" @(
    "C:\Program Files\GitHub CLI\gh.exe",
    "$env:LOCALAPPDATA\GitHubCLI\gh.exe"
)
if (-not $gh) {
    $gh = Instalar "GitHub.cli" "GitHub CLI" "C:\Program Files\GitHub CLI\gh.exe" | Select-Object -Last 1
}
if (-not $gh -or -not (Test-Path $gh)) {
    Falhou "GitHub CLI nao encontrado. Instale manualmente: winget install GitHub.cli"
}
Info "GitHub CLI: $gh"

# ---------------------------------------------------------------------------
Titulo "2/6 Login no GitHub"

& $gh auth status 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Info "vou abrir o navegador. Copie o codigo que aparecer e autorize."
    & $gh auth login --hostname github.com --git-protocol https --web
    & $gh auth status 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Falhou "login nao concluido. Rode manualmente: gh auth login --web"
    }
} else {
    Info "ja autenticado"
}

$usuario = [string](& $gh api user --jq ".login")
$usuario = $usuario.Trim()
if (-not $usuario) { Falhou "nao consegui descobrir seu usuario do GitHub" }
Info "usuario: $usuario"

$repoCompleto = "$usuario/$NomeRepo"

# ---------------------------------------------------------------------------
Titulo "3/6 Commit local"

# O init precisa vir ANTES do config: fora de um repositorio o "git config"
# falha, o commit fica sem autor e o push nao tem o que enviar.
if (-not (Test-Path (Join-Path $Raiz ".git"))) {
    & $git -C $Raiz init -q
    Info "repositorio local criado"
}
# O Pages depende da branch "main"; o git init pode criar "master".
& $git -C $Raiz branch -M main 2>&1 | Out-Null

& $git -C $Raiz config user.name $usuario
& $git -C $Raiz config user.email "$usuario@users.noreply.github.com"

& $git -C $Raiz add -A
& $git -C $Raiz commit -q -m "Alerta Agua RJ: monitor de abastecimento com painel" 2>&1 | Out-Null

& $git -C $Raiz rev-parse --verify HEAD 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Falhou "o commit nao foi criado (pasta vazia ou Git sem autor configurado)"
}
Info "commit criado"

# ---------------------------------------------------------------------------
Titulo "4/6 Repositorio no GitHub"

& $gh repo view $repoCompleto 2>&1 | Out-Null
$existe = ($LASTEXITCODE -eq 0)

if ($existe) {
    Info "repositorio $repoCompleto ja existe; vou enviar para ele"
    & $git -C $Raiz remote remove origin 2>&1 | Out-Null
    & $git -C $Raiz remote add origin "https://github.com/$repoCompleto.git"
    & $git -C $Raiz push -u origin main
    if ($LASTEXITCODE -ne 0) { Falhou "nao consegui enviar o codigo (git push)" }
} else {
    & $gh repo create $NomeRepo --public --source $Raiz --remote origin --push
    if ($LASTEXITCODE -ne 0) { Falhou "nao consegui criar o repositorio" }
    Info "repositorio publico criado e codigo enviado"
}

# ---------------------------------------------------------------------------
Titulo "5/6 Telegram"

if (-not $TelegramToken) {
    $seguro = Read-Host "   Cole o token do bot (@BotFather)" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($seguro)
    $TelegramToken = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
}
if (-not $TelegramToken) { Falhou "token vazio" }

# Valida o token antes de seguir.
try {
    $me = Invoke-RestMethod -Uri "https://api.telegram.org/bot$TelegramToken/getMe" -TimeoutSec 20
} catch {
    $me = $null
}
if (-not $me -or -not $me.ok) {
    Falhou "token invalido (confira no @BotFather)"
}
Info "bot: @$($me.result.username)"

# Descobre o chat_id sozinho: basta mandar uma mensagem para o bot.
if (-not $ChatId) {
    Info "abra o Telegram e mande um 'oi' para @$($me.result.username). Esperando..."
    for ($i = 0; $i -lt 40; $i++) {
        try {
            $resposta = Invoke-RestMethod -Uri "https://api.telegram.org/bot$TelegramToken/getUpdates?timeout=5" -TimeoutSec 15
        } catch {
            $resposta = $null
        }
        $achados = @()
        if ($resposta -and $resposta.result) { $achados = @($resposta.result) }
        if ($achados.Count -gt 0) {
            $msg = $achados[0].message
            if (-not $msg) { $msg = $achados[0].edited_message }
            if ($msg -and $msg.chat) { $ChatId = [string]$msg.chat.id; break }
        }
        Start-Sleep -Seconds 3
    }
}
if (-not $ChatId) {
    $ChatId = Read-Host "   Nao encontrei. Cole o seu chat id"
}
if (-not $ChatId) { Falhou "chat id vazio" }
Info "chat id: $ChatId"

$TelegramToken | & $gh secret set TELEGRAM_BOT_TOKEN --repo $repoCompleto
$ChatId | & $gh secret set TELEGRAM_CHAT_ID --repo $repoCompleto
Info "secrets gravados"

# ---------------------------------------------------------------------------
Titulo "6/6 GitHub Pages e primeira execucao"

& $gh api -X POST "repos/$repoCompleto/pages" -f "source[branch]=main" -f "source[path]=/docs" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    & $gh api -X PUT "repos/$repoCompleto/pages" -f "source[branch]=main" -f "source[path]=/docs" 2>&1 | Out-Null
}
if ($LASTEXITCODE -ne 0) {
    Info "aviso: nao consegui ligar o Pages pela API."
    Info "ative manualmente em Settings > Pages > Deploy from a branch > main > /docs"
} else {
    Info "Pages ligado em main:/docs"
}

& $gh workflow run monitor.yml --repo $repoCompleto 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Info "aviso: nao consegui disparar agora; rode em Actions > Monitor > Run workflow"
} else {
    Info "primeira execucao disparada"
}

Write-Host ""
Write-Host "  Pronto." -ForegroundColor Green
Write-Host ""
Write-Host "  Repositorio: https://github.com/$repoCompleto"
Write-Host "  Acoes:       https://github.com/$repoCompleto/actions"
Write-Host "  Painel:      https://$usuario.github.io/$NomeRepo/"
Write-Host ""
Write-Host "  O painel pode levar 1-2 minutos para aparecer na primeira vez."
Write-Host ""
