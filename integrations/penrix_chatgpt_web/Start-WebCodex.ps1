param([string]$ProjectDir, [string]$RuntimeDir = $PSScriptRoot, [switch]$RealTest)
$ErrorActionPreference = 'Stop'
$interactive = -not $ProjectDir
if ($interactive) { Add-Type -AssemblyName System.Windows.Forms }
try {
    if (Get-NetTCPConnection -LocalPort 17842 -State Listen -ErrorAction SilentlyContinue) {
        $notice = '17842 端口已被占用。如果已有 WebCodex 服务，请先关闭，再切换项目。'
        if ($interactive) { [System.Windows.Forms.MessageBox]::Show($notice, 'WebCodex') | Out-Null } else { throw $notice }
        exit 0
    }
    if (-not $ProjectDir) {
        $picker = New-Object System.Windows.Forms.FolderBrowserDialog
        $picker.Description = '选择允许 ChatGPT 通过 WebCodex 操作的本地 Git 项目'
        $picker.ShowNewFolderButton = $false
        if ($picker.ShowDialog() -ne 'OK') { exit 0 }
        $ProjectDir = $picker.SelectedPath
        $picker.Dispose()
    }
    $projectPath = (Resolve-Path -LiteralPath $ProjectDir).Path
    & git -C $projectPath rev-parse --show-toplevel 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { throw '请选择已初始化的 Git 项目目录' }
    $runtimePath = (Resolve-Path -LiteralPath $RuntimeDir).Path
    $pythonPath = (Get-Command python.exe -ErrorAction Stop).Source
    $entryPath = Join-Path $runtimePath 'integrations\penrix_chatgpt_web\browser_entry.py'
    if (-not (Test-Path -LiteralPath $entryPath)) { throw '运行包缺少 browser_entry.py' }
    $logsPath = Join-Path $env:USERPROFILE '.codex\webcodex-browser-logs'
    New-Item -ItemType Directory -Path $logsPath -Force | Out-Null
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $arguments = @(('"' + $entryPath + '"'), '--project-dir', ('"' + $projectPath + '"'), '--webcodex-bin-dir', ('"' + $runtimePath + '"'))
    if ($RealTest) { $arguments += '--real-test' }
    $stdoutPath = Join-Path $logsPath "$stamp-out.log"
    $stderrPath = Join-Path $logsPath "$stamp-err.log"
    $launched = Start-Process -FilePath $pythonPath -ArgumentList $arguments -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru
    $deadline = [DateTime]::UtcNow.AddSeconds(45)
    $ready = $false
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($launched.HasExited) { throw "本地服务启动失败，诊断日志：$stderrPath" }
        if ((Test-Path -LiteralPath $stdoutPath) -and (Select-String -LiteralPath $stdoutPath -SimpleMatch 'WebCodex browser entry ready' -Quiet)) { $ready = $true; break }
        Start-Sleep -Milliseconds 200
    }
    if (-not $ready) { throw "本地服务尚未确认就绪，请查看日志：$stderrPath。不要重复启动。" }
    $notice = 'WebCodex 已就绪。在已有的 ChatGPT 对话中点击 WebCodex → 连接项目。无需启动 Codex Web GPT。'
    if ($interactive) { [System.Windows.Forms.MessageBox]::Show($notice, 'WebCodex') | Out-Null } else { Write-Output $notice }
} catch {
    if ($interactive) { [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'WebCodex 启动失败') | Out-Null } else { Write-Error $_.Exception.Message -ErrorAction Continue }
    exit 1
}
