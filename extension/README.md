# 旧版浏览器插件（v0.1.x）停用与迁移说明

> [!IMPORTANT]
> 旧版自动点击浏览器插件（`v0.1.0` / `v0.1.1`）已停用，由 **[GLaDOS 签到工作台 0.2.1](../webextension/README.md)** 正式替代。如浏览器中仍安装有旧版 `0.1.x` 扩展，请在扩展管理页将其移除后再安装工作台 `0.2.1`。

## 立即迁移到签到工作台 0.2.1

- **一键下载安装包（无需命令行）：** 前往 **[Releases v2026.11.24](https://github.com/lankerr/2026-glados-checkin/releases/tag/v2026.11.24)** 下载 `glados-desk-chromium-0.2.1.zip`（Chrome / Edge）或 `glados-desk-firefox-0.2.1.zip`（Firefox 140+）
- **安装与权限说明：** [webextension/README.md](../webextension/README.md)
- **九步截图安装与流水核对教程：** [docs/desk-walkthrough.md](../docs/desk-walkthrough.md)

工作台采用**「可选本地 09:30 提醒 → 一键打开所选域名官网由本人完成签到与人机验证 → 点击核对官网真实积分流水」**机制，完整支持 5 个官方域名（`glados.cloud` / `glados.rocks` / `glados.network` / `glados.space` / `glados.one`）以及 Chrome、Edge、Firefox。

## 为什么停用旧版 v0.1.x 自动点击插件？

经社区反馈与复现核查（[#50](https://github.com/lankerr/2026-glados-checkin/pull/50)、[#53](https://github.com/lankerr/2026-glados-checkin/pull/53)、[#56](https://github.com/lankerr/2026-glados-checkin/pull/56)、[#58](https://github.com/lankerr/2026-glados-checkin/issues/58)），旧版 `v0.1.x` 存在以下结构性限制：

1. **MV3 隔离环境无法捕获页面请求：** Manifest V3 内容脚本默认运行在 Isolated World，旧版通过劫持 `window.fetch` / `XMLHttpRequest` 无法可靠读取页面主环境（Main World）的真实 `POST /api/user/checkin` 响应，或误将 `GET /api/user/checkin/challenge` 的 `200` 准备响应当作签到成功。
2. **中英文按钮与多域名限制：** 旧版仅匹配英文 `Check in` 文案（中文界面「签到」按钮超时失败），且后台硬编码 `glados.cloud` 单一域名。
3. **后台静默页与人机验证冲突：** 旧版在后台静默打开标签页（`active: false`），遇到官网要求用户本人完成的 Cloudflare Turnstile 交互验证时无法处理，且在多触发源重叠时可能重复打开多个标签页。

## 致谢

- 感谢 [@Unexpectedlyc](https://github.com/Unexpectedlyc) 为早期扩展补齐中英双语国际化与后台运行说明（[#44](https://github.com/lankerr/2026-glados-checkin/pull/44)）。
- 感谢 [@EchoChan314](https://github.com/EchoChan314) 在中文 Edge 环境定位按钮识别、`challenge` 响应误判及重复开页问题并提交修复方案（[#50](https://github.com/lankerr/2026-glados-checkin/pull/50)、[#56](https://github.com/lankerr/2026-glados-checkin/pull/56)）。
- 感谢 [@mem4tgo](https://github.com/mem4tgo) 报告扩展签到失效问题（[#58](https://github.com/lankerr/2026-glados-checkin/issues/58)）。
