# GLaDOS 签到怎么选

如果已有定时签到，只想知道今天有没有入账，直接看云端日报。想在浏览器里自己确认账号、完成官网验证并查看流水，可以在**单独的浏览器配置**里试用签到工作台。以下状态核对于 2026-11-22。

## 可使用的方案

| 我想做什么 | 选哪个，能看到什么 | 致谢和来源 |
| --- | --- | --- |
| 自己完成官网签到 | 打开[官网签到页](https://glados.cloud/console/checkin)，在自己的账号中完成页面要求的操作，再看当天的积分流水。 | 感谢 GLaDOS 提供官网入口，感谢 @chengchang1987-cloud 和 @1996yorkjiang-afk 提供积分变化和验证提示的观察。[#28](https://github.com/lankerr/2026-glados-checkin/issues/28) · [#37](https://github.com/lankerr/2026-glados-checkin/issues/37) |
| 已有本机定时任务 | 沿用[本地安装和配置](../README.md#local)。完整模式可能执行积分兑换，配置项见使用手册。遇到提交结果不明时，先到官网查当天流水。 | 感谢 @badpinkman 修复新版登录会话和 User-Agent 的兼容问题，感谢 @lankerr 维护安装器。[#18](https://github.com/lankerr/2026-glados-checkin/pull/18) · [#48](https://github.com/lankerr/2026-glados-checkin/pull/48) |
| 远程核对余额、连续签到天数 | Actions 定时任务默认查询状态；[连续签到日报](https://github.com/lankerr/2026-glados-checkin/actions/workflows/streak.yml)按北京时间统计最近可见的 10 条流水。更早的日期可能超出可见范围。 | 感谢 @lankerr 修正统计口径，补上官网的 `system:checkin` 标签。[#39](https://github.com/lankerr/2026-glados-checkin/pull/39) · [#49](https://github.com/lankerr/2026-glados-checkin/pull/49) |
| 在浏览器里看签到是否入账 | **独立工作台 0.2.1，桌面试用版。** 人在官网操作，点击「核对官网流水」后才读取账号和积分。可选本地 09:30 提醒，初始关闭。安装方法见下节。 | 感谢 @lankerr 开发工作台，感谢 @Unexpectedlyc 为经典扩展补齐中英语言包和安装说明。[#44](https://github.com/lankerr/2026-glados-checkin/pull/44) |
| 已经在用经典浏览器插件 | [经典插件](../extension/README.md)按时段尝试签到。中文按钮识别和结果误判已有反馈，使用者可在官网查流水。它和独立工作台是两个扩展。 | 感谢 @Unexpectedlyc 修复经典插件加载，感谢 @EchoChan314 提交中文页面的故障原因和修复提案。[#44](https://github.com/lankerr/2026-glados-checkin/pull/44) · [#50](https://github.com/lankerr/2026-glados-checkin/pull/50) |
| 在微信或 Telegram 收到运行结果 | 在[使用手册](usage.md)选择通知渠道。消息中的「查询失败」表示这次没读到有效数据，可回官网核对。 | 感谢 @Ch3nSir 添加 Server酱 Turbo / Server酱³，感谢 @Initsnow 添加 Telegram 推送及通知级别。[#27](https://github.com/lankerr/2026-glados-checkin/pull/27) · [#3](https://github.com/lankerr/2026-glados-checkin/pull/3) |

## 试用独立工作台

1. 在本试用 PR 的检查列表打开 **Desk pilot** 运行摘要，从 **Artifacts** 下载 `glados-desk-pilot` 并解压。里面有 Chromium 和 Firefox 两个 ZIP。也可以从包含 `webextension/` 的分支根目录运行 `python webextension/build.py --out dist`，直接得到可加载的目录和 ZIP。
2. 在浏览器新建一个专用于试用的配置。Chrome / Edge 解压 Chromium 包，在扩展管理页点「加载已解压的扩展程序」，选含 `manifest.json` 的目录。Firefox 140 及以上用「临时载入附加组件」打开 Firefox 包里的 `manifest.json`，重启后需重新载入。[安装说明与权限](../webextension/README.md)
3. 点击工作台图标，选官网域名。在试用配置中登录自己的账号。今天已有定时签到的，直接点「核对官网流水」。当天有带签到标签的正数入账，页面会显示「官网已有签到入账」。只有余额、补偿积分或缺少签到标签时，仍显示待确认。切换账号或退出登录后重新核对，旧读数会清空。

下图来自隔离浏览器里的模拟账号。示例余额为 37，当日签到 +4，前一天活动 +3。三个桌面浏览器的模拟账本均已读取成功，手机端仍待实机验证。

![独立工作台测试截图，模拟流水显示当天签到加 4 分、余额 37 分](assets/checkin-desk-pilot.png)

## 社区提案

| 提案 | 解决的问题与当前状态 | 致谢和讨论 |
| --- | --- | --- |
| 用系统浏览器运行（PR #47） | 让 Linux / NixOS 用户复用已安装的浏览器，减少安装依赖。仍在审阅；调试连接能接触登录会话，连接目标和账号隔离是待解决的问题。此次工作台试用没有启用该驱动。 | 感谢 @Initsnow 提供实现、NixOS 配置与测试。[PR #47](https://github.com/lankerr/2026-glados-checkin/pull/47) |
| 修复经典插件的中文按钮和结果识别（PR #50） | 中文「签到」按钮可能找不到，准备验证的响应也可能被当成成功。贡献者提交了两个修复。PR 仍在审阅；独立工作台按官网流水判断入账。 | 感谢 @EchoChan314 在中文 Edge 定位问题并提交修复。[PR #50](https://github.com/lankerr/2026-glados-checkin/pull/50) |
| 多账号隔离与重复提交保护（草稿 PR #38） | 给每次运行独立会话，核实账号，并在提交结果不确定时停止重试。草稿与主线有冲突，仍待整合和验收。 | 感谢 @lankerr 整理风险、提交隔离方案和离线测试。[PR #38](https://github.com/lankerr/2026-glados-checkin/pull/38) |
| 手机上完成日常签到（Issue #40） | 目前可在手机浏览器打开官网。工作台的窄屏布局已在桌面测试，手机扩展安装与提醒仍待实机验证。 | 感谢 @chengchang1987-cloud 提出手机端使用需求。[Issue #40](https://github.com/lankerr/2026-glados-checkin/issues/40) |
| 按官网 Current Index 提醒（Issue #45） | 建议提醒用户何时查看官网。目前仍在确认数据来源和指标含义，与签到积分之间的关系尚待证实。 | 感谢 @luckyboychn-ship 提出指标提醒建议。[Issue #45](https://github.com/lankerr/2026-glados-checkin/issues/45) |

本项目为社区工具。请仅在本人或获得明确授权的账号上使用，并遵守服务规则。遇到官网要求的人机验证，请本人在官网完成。签到结果和奖励以账号的实际流水为准。
