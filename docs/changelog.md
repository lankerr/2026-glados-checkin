# 更新记录

[返回首页](../README.md)

历史条目只说明当时版本和观察，不代表当前或未来可用性。

## 📝 更新日志

### 2026-11-14：签到状态公告（文档更新）

- 在 README 顶部区分 Turnstile 拒绝实测、历史成功、手动/重复签到及工单反馈。
- 添加来源和脱敏数据征集入口；本次没有修改签到代码或发布验证修复。

### 2026-09-30：新版会话与设备校验修复

- 合并 [@badpinkman 的 PR #18](https://github.com/lankerr/2026-glados-checkin/pull/18)，适配 `gld:sess` / `gld:sess.sig` 和 `GLADOS_USER_AGENT`。
- 旧会话导致的“没有权限”需要通过重新登录、更新完整 Cookie 解决；设备校验还要求 User-Agent 与生成会话的浏览器一致。Fork 同步代码不会自动更新个人仓库的 Secrets 和 Variables。
- 维护者仓库在更新配置后完成真实验证：[首次签到成功](https://github.com/lankerr/2026-glados-checkin/actions/runs/36687039069)，[同日重复签到正常返回](https://github.com/lankerr/2026-glados-checkin/actions/runs/36708285323)。

### v1.2.0 (2026-08-05)

- 识别 `Today's observation logged...` 等 2026 正常返回，不再显示“成功 0/1”
- 失败自动重试三次，最终失败返回非零退出码
- 默认仅失败推送，避免多个调度器造成通知轰炸
- 每天一次签到、每月一次保活，替代每天保活提交
- 修正 workflow dispatch 的 PAT 权限、HTTP 状态码和 404 排障说明

### v1.1.0 (2026-01-25) 🔥 重大修复

**问题**：签到始终返回 "please checkin via https://glados.cloud"，导致机器人无法签到。

**原因**：GLaDOS 官方更新了 API，签到 token 必须从 `glados.one` 改为 `glados.cloud`。

**修复**：更新 [`checkin.py`](../checkin.py) 中的 token 参数。

**排查过程**：

1. 使用浏览器 DevTools 抓包分析真实签到请求
2. 对比 Python 脚本与浏览器请求的差异
3. 尝试添加 Headers、模拟 TLS 指纹等方案（均无效）
4. 最终通过测试不同 token 值发现问题根源

> 💡 如果你在使用其他签到项目遇到同样问题，可以参考本项目的修复方案！

### v1.0.0 (2026-01-20)

- 初始版本发布
- 支持 glados.cloud 域名
- PushPlus 微信推送
- GitHub Actions 自动签到

---
