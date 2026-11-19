# GLaDOS 自动签到 一键安装脚本（Windows）
# 流程：Python 检查 -> 依赖安装 -> Cookie/UA 模板 -> 计划任务(09:30/12:30/20:30) -> 自检
# 重复运行安全：已存在的配置与任务会被更新而非报错。

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$dir = $PSScriptRoot
Set-Location $dir
Write-Host '====================================' -ForegroundColor Cyan
Write-Host ' GLaDOS 自动签到 一键安装' -ForegroundColor Cyan
Write-Host '====================================' -ForegroundColor Cyan

# ---- 1. Python 检查 ----
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if ($py) {
    & $py.Source --version
} else {
    Write-Host '[X] 未检测到 Python。请先安装 Python 3.10+：' -ForegroundColor Red
    Write-Host '    https://www.python.org/downloads/  （安装时勾选 Add to PATH）'
    Write-Host '    或在终端运行: winget install Python.Python.3.12'
    exit 1
}

# ---- 2. 依赖 ----
Write-Host '[1/5] 安装依赖（requests + playwright）...' -ForegroundColor Yellow
& $py.Source -m pip install --quiet --disable-pip-version-check -r (Join-Path $dir 'requirements.txt')
if ($LASTEXITCODE -ne 0) { Write-Host '[X] 依赖安装失败，请检查网络/代理后重试' -ForegroundColor Red; exit 1 }

# 浏览器：本机有 Chrome/Edge 即可用；都没有才需要下载 chromium
$hasChrome = (Test-Path "$env:ProgramFiles\Google\Chrome\Application\chrome.exe") -or (Test-Path "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe")
$hasEdge = Test-Path "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
if (-not ($hasChrome -or $hasEdge)) {
    Write-Host '     未检测到 Chrome/Edge，下载 Playwright chromium（约 120MB）...'
    & $py.Source -m playwright install chromium
}

# ---- 3. Cookie / UA 模板 ----
Write-Host '[2/5] 检查 Cookie 配置...' -ForegroundColor Yellow
$cookieFile = Join-Path $dir 'cookie.txt'
if (-not (Test-Path -LiteralPath $cookieFile) -or [string]::IsNullOrWhiteSpace((Get-Content -LiteralPath $cookieFile -Raw))) {
    @'
把下面一行替换成你的 GLaDOS Cookie（登录 glados.cloud -> F12 -> Network -> 刷新 -> 点第一个请求 -> Request Headers 里 cookie: 后面的整串）
必须同时包含 gld:sess 与 gld:sess.sig
gld:sess=粘贴到这里; gld:sess.sig=粘贴到这里
'@ | Out-File -LiteralPath $cookieFile -Encoding utf8
    Write-Host '     已生成 cookie.txt 模板——请用记事本打开并粘贴你的 Cookie！' -ForegroundColor Magenta
}
$uaFile = Join-Path $dir 'user-agent.txt'
if (-not (Test-Path -LiteralPath $uaFile) -or [string]::IsNullOrWhiteSpace((Get-Content -LiteralPath $uaFile -Raw))) {
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36' | Out-File -LiteralPath $uaFile -Encoding utf8
    Write-Host '     已生成 user-agent.txt 默认值（建议换成你登录所用浏览器的 UA）' -ForegroundColor DarkYellow
}

# ---- 4. 启动脚本（若仓库未带 run-checkin.ps1 则生成本地版）----
$runPs1 = Join-Path $dir 'run-checkin.ps1'
if (-not (Test-Path $runPs1)) {
    @'
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$dir = $PSScriptRoot
$env:PYTHONIOENCODING = 'utf-8'
$cookieFile = Join-Path $dir 'cookie.txt'
$raw = if (Test-Path -LiteralPath $cookieFile) { Get-Content -LiteralPath $cookieFile -Raw }
if ([string]::IsNullOrWhiteSpace($raw)) { Write-Output '[错误] cookie.txt 为空'; exit 1 }
$env:GLADOS_COOKIE = $raw.Trim()
$ua = if (Test-Path (Join-Path $dir 'user-agent.txt')) { [IO.File]::ReadAllText((Join-Path $dir 'user-agent.txt')).Trim() } else { '' }
if ($ua) { $env:GLADOS_USER_AGENT = $ua }
$env:EXCHANGE_PLAN = 'plan500'
$env:PUSH_LEVEL = 'fail_only'
$logDir = Join-Path $dir 'logs'; New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("checkin_" + (Get-Date -Format 'yyyy-MM-dd') + ".log")
python (Join-Path $dir 'checkin.py') *>&1 | ForEach-Object { Write-Output $_; $_ | Out-File -LiteralPath $log -Append -Encoding utf8 }
exit $LASTEXITCODE
'@ | Out-File -LiteralPath $runPs1 -Encoding utf8
}

# ---- 5. 计划任务（幂等重建）----
Write-Host '[3/5] 注册计划任务（每天 09:30 / 12:30 / 20:30）...' -ForegroundColor Yellow
if ($env:GLADOS_INSTALL_NO_TASK -eq '1') { Write-Host '     (测试模式：跳过任务注册)' } else {
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runPs1`""
$triggers = @(
    (New-ScheduledTaskTrigger -Daily -At '09:30'),
    (New-ScheduledTaskTrigger -Daily -At '12:30'),
    (New-ScheduledTaskTrigger -Daily -At '20:30')
)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
$name = 'GLaDOS自动签到'
if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $name -Confirm:$false
}
Register-ScheduledTask -TaskName $name -Action $action -Trigger $triggers -Settings $settings -Description 'GLaDOS 自动签到（本地浏览器通道+三层兜底，幂等可重复运行）' | Out-Null
Write-Host "     已注册任务: $name" -ForegroundColor Green
}

# ---- 6. 自检 ----
Write-Host '[4/5] 运行离线自检（单元测试）...' -ForegroundColor Yellow
$out = (& $py.Source -m unittest discover -s (Join-Path $dir 'tests') 2>&1 | Out-String)
($out -split "`r?`n" | Where-Object { $_.Trim() } | Select-Object -Last 3) | ForEach-Object { Write-Host "     $_" }
if ($LASTEXITCODE -ne 0) { Write-Host '     [!] 自检未全部通过：若因缺少 .github 目录可忽略；持续失败请到仓库提 Issue' -ForegroundColor DarkYellow }

Write-Host '[5/5] 完成！' -ForegroundColor Green
Write-Host ''
Write-Host '下一步（唯一要你做的事）：' -ForegroundColor Cyan
Write-Host "  1. 用记事本打开 $cookieFile 粘贴你的 GLaDOS Cookie（含 gld:sess 与 gld:sess.sig）"
Write-Host '  2. 双击 run-checkin.ps1 立即试跑一次（会短暂弹出浏览器窗口，属正常）'
Write-Host '  3. 之后每天 09:30 / 12:30 / 20:30 自动签到；结果看 logs\ 目录'
Write-Host '  （可选）要收微信通知：编辑 run-checkin.ps1 按 顶部 README 配 PUSHPLUS_TOKEN'
