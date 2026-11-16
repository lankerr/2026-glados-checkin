@echo off
rem GLaDOS 自动签到 - 一键安装入口（右键"以管理员身份运行"不必需，普通双击即可）
chcp 65001 >nul
cd /d "%~dp0"
where pwsh >nul 2>nul
if %errorlevel%==0 (
  pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
)
pause
