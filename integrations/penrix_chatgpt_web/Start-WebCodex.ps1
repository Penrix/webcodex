param([string]$ProjectDir, [string]$WorkspaceDir, [string]$RuntimeDir = $PSScriptRoot, [switch]$RealTest)
$ErrorActionPreference = 'Stop'
$interactive = -not ($ProjectDir -or $WorkspaceDir)
if ($interactive) { Add-Type -AssemblyName System.Windows.Forms }
try {
    if (Get-NetTCPConnection -LocalPort 17842 -State Listen -ErrorAction SilentlyContinue) {
        $notice = '17842 端口已被占用。如果已有 WebCodex 服务，请先关闭，再切换项目。'
        if ($interactive) { [System.Windows.Forms.MessageBox]::Show($notice, 'WebCodex') | Out-Null } else { throw $notice }
        exit 0
    }
    if ($ProjectDir -and $WorkspaceDir) { throw 'ProjectDir 与 WorkspaceDir 只能指定一个' }
    if (-not ($ProjectDir -or $WorkspaceDir)) { $WorkspaceDir = $env:USERPROFILE }
    $selectedPath = if ($WorkspaceDir) { $WorkspaceDir } else { $ProjectDir }
    $projectPath = (Resolve-Path -LiteralPath $selectedPath).Path
    if (-not (Test-Path -LiteralPath $projectPath -PathType Container)) { throw '请选择目录' }
    $scopeArgument = if ($WorkspaceDir) { '--workspace-dir' } else { '--project-dir' }
    $runtimePath = (Resolve-Path -LiteralPath $RuntimeDir).Path
    $pythonPath = (Get-Command python.exe -ErrorAction Stop).Source
    $entryPath = Join-Path $runtimePath 'integrations\penrix_chatgpt_web\browser_entry.py'
    if (-not (Test-Path -LiteralPath $entryPath)) { throw '运行包缺少 browser_entry.py' }
    $logsPath = Join-Path $env:USERPROFILE '.codex\webcodex-browser-logs'
    New-Item -ItemType Directory -Path $logsPath -Force | Out-Null
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $arguments = @(('"' + $entryPath + '"'), $scopeArgument, ('"' + $projectPath + '"'), '--webcodex-bin-dir', ('"' + $runtimePath + '"'))
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
    $notice = "WebCodex 已就绪。操作范围：$projectPath。在已有 ChatGPT 对话中点击 WebCodex → 连接工作区。"
    if ($interactive) { [System.Windows.Forms.MessageBox]::Show($notice, 'WebCodex') | Out-Null } else { Write-Output $notice }
} catch {
    if ($interactive) { [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'WebCodex 启动失败') | Out-Null } else { Write-Error $_.Exception.Message -ErrorAction Continue }
    exit 1
}
