# GLaDOS Check-in 浏览器插件（Beta）

## 设计理念（与本项目 Python 版同一套哲学）

| 设计点 | 说明 |
| --- | --- |
| **零配置** | 用浏览器自身登录态——登录过 glados.cloud 即可，不粘贴 Cookie、不配账号 JSON |
| **三时段幂等调度** | 北京时间 09:30 / 12:30 / 20:30 自动尝试；浏览器启动时当日未签会补跑；已签自动跳过（含识别本地脚本/手动已入账） |
| **验证由官方完成** | 到点打开官方签到页，由页面自身完成人机验证，插件只点击按钮并读取结果，完成即自动关页 |
| **徽章 = 连续天数** | 图标角标实时显示连续入账天数（与主仓库 README 每日战报同口径），一眼看到"火还在烧" |
| **最小权限** | MV3 service worker，仅 glados 域名 host 权限 + alarms/storage/notifications，无常驻后台页 |

## 安装（开发者模式加载，约 30 秒）

1. 下载并解压 `glados-checkin-extension-v0.1.0.zip`
2. Chrome 打开 `chrome://extensions`（Edge 为 `edge://extensions`），右上角开启**开发者模式**
3. 点**加载已解压的扩展程序**，选择解压目录
4. 确保浏览器已登录 glados.cloud，完成——徽章出现 🔥 天数即工作正常

## 国际化

默认语言为简体中文（`_locales/zh_CN`），并提供英文（`_locales/en`）。Chrome 会按浏览器语言自动切换；缺少对应语言时回退到 `default_locale`（zh_CN）。弹窗文案通过 `data-i18n` + `chrome.i18n.getMessage()` 填充（HTML 中的 `__MSG_*__` 不会自动替换）。

打包 zip 时必须带上 `_locales` 目录，否则会报 `Default locale was specified, but _locales subtree is missing.`

## 使用

- 什么都不用做：到点自动开页签到后关页，弹系统通知告知结果。关窗口前请先打开「关闭浏览器后继续运行后台应用」
- 弹出面板可看：连续天数 / 今日状态 / 当前积分 / 手动"立即签到"
- 与 Python 本地版可共存：谁先签上，另一方自动跳过（流水互认）

## 边界

- 单浏览器配置 = 单账号（多账号请用多个浏览器 Profile）
- 关窗口后仍可到点签到：请在系统设置开启「关闭浏览器后继续运行后台应用」（Chrome：`chrome://settings/system`，Edge：`edge://settings/system/manageSystem`）。点窗口 **X** 即可；托盘里选「退出」、睡眠、关机或结束进程后不会签
- 追求完全无人值守（不依赖浏览器进程）请用主仓库的 Python 本地模式（系统计划任务，无需开浏览器）
- 验证是否放行由 Cloudflare 官方组件决定；被拒时下个时段自动重试，本插件不绕过、不打码
