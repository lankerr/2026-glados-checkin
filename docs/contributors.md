# 贡献与致谢

[返回首页](../README.md)

## 🙏 致谢

感谢通过 Pull Request 改进本项目的贡献者。每一项修复和文档改进都让自动签到更可靠，也让新用户更容易完成配置。

| 贡献者 | 贡献 | Pull Request |
| --- | --- | --- |
| [@Ch3nSir](https://github.com/Ch3nSir) | 添加 Server酱 Turbo / Server酱³ 推送支持，补充部署说明、NixOS 配置和通知回归测试。 | [#27](https://github.com/lankerr/2026-glados-checkin/pull/27) |
| [@badpinkman](https://github.com/badpinkman) | 适配新版 `gld:sess` 会话与浏览器设备校验，完善 Cookie 获取、User-Agent 配置和认证失败提示，并提供真实运行验证。 | [#18](https://github.com/lankerr/2026-glados-checkin/pull/18) |
| [@Unexpectedlyc](https://github.com/Unexpectedlyc) | 调整 README 的部署顺序与说明，减少 GitHub Actions 和外部定时器配置带来的误解。 | [#5](https://github.com/lankerr/2026-glados-checkin/pull/5) |
| [@Unexpectedlyc](https://github.com/Unexpectedlyc)（再次贡献） | 修复浏览器插件 `_locales` 缺失导致 Chrome/Edge 无法加载的问题，为插件补齐中英双语国际化（36 条消息）并增加后台运行设置说明。 | [#44](https://github.com/lankerr/2026-glados-checkin/pull/44) |
| [@Initsnow](https://github.com/Initsnow) | 添加 Telegram 推送、通知级别与 NixOS Flake 支持，并修复 Telegram 消息格式问题。 | [#3](https://github.com/lankerr/2026-glados-checkin/pull/3) |

同时感谢 [@LxFairy](https://github.com/LxFairy) 提交上游同步与冲突处理 PR（[#8](https://github.com/lankerr/2026-glados-checkin/pull/8)、[#9](https://github.com/lankerr/2026-glados-checkin/pull/9)，未合并），以及在 Issues 中提供报错日志、排查线索和复测反馈的用户。

感谢 [@chengchang1987-cloud](https://github.com/chengchang1987-cloud) 在 [Issue #28](https://github.com/lankerr/2026-glados-checkin/issues/28) 提供积分流水、challenge 排查证据和[参考脚本](https://github.com/lankerr/2026-glados-checkin/issues/28#issuecomment-6676702004)。参考脚本的核心 proof 算法与已合并的 #31 一致；本次进一步采纳日志即时刷新（`flush=True`）及 2.7 秒等待时间（在 2.5 秒基础上增加 0.2 秒余量）。原有的 nonce/TTL 校验、同域提交、失败时不回退旧签到流程、User-Agent 兼容和推送行为均保留。这两项改进不代表首次签到奖励已恢复，仍需以下一次首次签到返回及实际积分入账核验。

特别感谢 @badpinkman 对 2026 年 9 月认证故障的排查与修复，帮助本项目恢复正常签到。

---
