# 🎁 5 分钟配置 GLaDOS 自动签到

> [!IMPORTANT]
> **✅ GLaDOS 自动签到已恢复（2026-09-30）。** 新版认证修复已发布，维护者仓库已验证签到与 PushPlus 通知正常，[查看恢复公告和实测记录](https://github.com/lankerr/2026-glados-checkin/releases/tag/v2026.9.30)。
>
> Fork 用户请先 **Sync fork → Update branch**。**已能正常签到的用户无需更换 Cookie。**
>
> 同步后若仍提示“没有权限”、`device-mismatch` 或 “Automated check-in detected”，再重新登录，从成功的 `/api/user/status` 请求中复制**完整单行 Cookie**（包含 `gld:sess` 与 `gld:sess.sig`）更新 `GLADOS_COOKIE`，并将同一登录浏览器的完整 User-Agent 配置为 `GLADOS_USER_AGENT`。
>
> **同步代码不会更新个人仓库的 Secrets 和 Variables。** 请手动运行一次验证自己的配置。
>
> 希望收到后续修复公告，可在原仓库选择 **Watch → Custom → Releases**。Fork 本身不代表订阅更新通知。

<div align="center">

**你不用写代码 · 不用买服务器 · 不用每天登录**

**一次配置，每天 9:30 自动签到；失败自动重试**

---

### ✨ 为什么选择本项目？

| 优势                  | 说明                                                |
| --------------------- | --------------------------------------------------- |
| ✅ **2026年验证可用** | 持续通过 Actions 日志和单元测试验证                 |
| ✅ **结果可信**       | 正确区分签到完成、重复签到和真实失败                |
| ✅ **新手友好**       | 全程图解，不会也能照着做                            |
| ✅ **作者持续维护**   | 遇到问题提Issue，作者很乐意帮忙                     |

---

### 📱 签到成功预览

![签到成功示例](images/success.jpg)

> **签到积分可累积兑换会员时长。每日奖励会随套餐、连续签到和海缆状态变化，请以控制台实际到账为准。**

---

### 🚀 3 步完成自动签到

```text
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   ① Fork 项目    ──→  点一下右上角 Fork 按钮                 │
│                                                             │
│   ② 配置 Cookie  ──→  浏览器复制一下，贴到 GitHub Secrets    │
│                                                             │
│   ③ 启用 Actions  ──→  手动测试一次，之后每天自动运行         │
│                                                             │
│   ✅ 完成！每天自动签到 + 微信通知                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**[👉 点击开始配置](#-快速部署)**

---

[![Auto Checkin](https://github.com/lankerr/2026-glados-checkin/actions/workflows/checkin.yml/badge.svg)](https://github.com/lankerr/2026-glados-checkin/actions)
[![GitHub Stars](https://img.shields.io/github/stars/lankerr/2026-glados-checkin?style=social)](https://github.com/lankerr/2026-glados-checkin)

**⭐ 觉得有用？点个 Star 支持一下！**

</div>

---

## 使用说明与免责声明

本项目为非官方社区辅助工具。使用前请阅读以下说明，并确认自己的部署方式符合所用平台的要求。

- **账号与平台规则**：仅用于本人或已获明确授权的账号，遵守适用法律法规以及 GLaDOS、GitHub 和所选推送服务的服务条款。请自行确认平台是否允许相应的自动化使用方式。
- **运行与奖励限制**：接口、验证流程、积分规则、服务额度和访问策略可能发生变化。测试通过或维护者账号运行成功，不构成持续可用、固定积分、补发差额、兑换成功或账号权益不受影响的保证；签到和奖励以平台实际记录为准。
- **凭据与通知隐私**：请妥善保管 Cookie、Token、SendKey 等凭据，GitHub 部署时使用 Secrets，不要提交到代码、公开日志或 Issue。通知触发时，签到摘要可能包含邮箱、积分和剩余天数，并会发送给你配置的推送服务；配置前请了解该服务的数据处理规则。
- **风险与责任范围**：本项目按“现状”提供。在适用法律允许的范围内，维护者和贡献者不对使用本项目产生的服务中断、数据或凭据泄露、积分及账号权益损失等承担赔偿责任。本说明不排除依法不得免除的责任。

## 💡 重要说明

> 默认只使用仓库内置的 **GitHub Actions** 定时任务，无需创建外部 cron。
>
> 本项目每月自动提交一次保活时间戳，避免公开仓库因 60 天无活动而停用计划任务。
>
> `cron-job.org` 仅作为可选备用方案。**内置 schedule 与外部 cron 二选一**，同时启用会重复签到和重复通知。
>
> 已经 Fork 很久的用户需要先点击 **Sync fork → Update branch**，再重新启用 Actions。

---

## 🔥 为什么你需要这个？

> > **⚠️ 重要：如果你使用其他签到脚本失败，显示 "please checkin via [https://glados.cloud](https://glados.cloud)"，请使用本项目！**

GLaDOS 在 2026 年初进行了 API 更新，**绝大多数旧签到脚本已失效**。我们通过抓包分析发现了问题：

| 问题       | 旧脚本                  | 本项目（已修复）           |
| ---------- | ----------------------- | -------------------------- |
| 签到 Token | `glados.one` ❌         | `glados.cloud` ✅          |
| 域名支持   | rocks/network ❌        | cloud ✅                   |
| 签到结果   | "please checkin via..." | "Checkin!" 或 "Repeats" ✅ |

<details>
<summary><b>🔬 技术细节：我们是怎样修复问题的（感兴趣的看）</b></summary>

### 🔬 我们的探索过程

#### 问题现象

- GitHub Actions 可以正常运行
- 推送消息显示 "成功0/1"
- 签到结果始终为 "please checkin via https://glados.cloud"
- 手动点击签到按钮正常，但机器人签到无效

#### 排查步骤

1️⃣ **浏览器抓包分析**

- 使用 Chrome DevTools 抓取真实签到请求
- 对比浏览器请求和 Python 脚本请求的差异

2️⃣ **尝试的方案（失败）**

- ❌ 添加更多 Headers（sec-ch-ua、sec-fetch-\* 等）
- ❌ 使用 requests.Session 保持会话
- ❌ 使用 curl_cffi 模拟浏览器 TLS 指纹
- ❌ 添加代理配置

3️⃣ **最终发现**
通过对比不同 token 值的请求结果：

```python
# 失败 ❌
{'token': 'glados.one'}  → "please checkin via https://glados.cloud"

# 成功 ✅
{'token': 'glados.cloud'} → "Checkin Repeats! Please Try Tomorrow"
```

**问题根源**：GLaDOS 更新了 API，签到 token 必须从 `glados.one` 改为 `glados.cloud`！

</details>

---

> **📢 重要提示**
>
> - GLaDOS 官网已迁移至 **glados.cloud**（不再是 glados.rocks）
> - 本项目专为 2026 积分制度优化，每天自动签到一次
> - 完全免费，使用 GitHub Actions，无需自己的服务器
> - 不会的话可以提 Issue，作者很乐意帮助技术新手！

---

## ✨ 功能特点

| 功能            | 说明                            |
| --------------- | ------------------------------- |
| 🎯 **精准积分** | 获取真实积分数据 + 每日变化量   |
| 🎁 **兑换提示** | 显示当前可兑换选项及差额        |
| ⏰ **每日一次** | 北京时间 9:30 自动签到          |
| 🔄 **失败重试** | 最多尝试三次，最终失败才报警    |
| 📱 **微信推送** | PushPlus HTML 报告 / Server酱 Markdown 报告 |
| ☁️ **2026 API** | 适配最新 glados.cloud API       |
| 🔧 **持续维护** | 发现问题及时修复                |

---

## 🛠 配置参数 (环境变量)

本项目支持以下环境变量配置：

| 变量名               | 必填  | 说明                                                                       |
| -------------------- | ----- | -------------------------------------------------------------------------- |
| `GLADOS_COOKIE`      | ✅ 是 | GLaDOS 的完整 Cookie，必须包含 `gld:sess` 与 `gld:sess.sig`。多个账号请用 `&` 或换行符分隔。 |
| `GLADOS_USER_AGENT`  | ❌ 否 | 生成当前 `gld:sess` 时浏览器的完整 User-Agent；新版设备校验失败时需要配置。 |
| `PUSHPLUS_TOKEN`     | ❌ 否 | PushPlus 微信推送 Token。                                                  |
| `SERVERCHAN_SENDKEY` | ❌ 否 | Server酱 SendKey，支持 Turbo（`SCT...`）与 Server酱³（`sctp...`）。         |
| `TELEGRAM_BOT_TOKEN` | ❌ 否 | Telegram 机器人的 Token（例如 `123456:ABC-DEF1234...`）                    |
| `TELEGRAM_CHAT_ID`   | ❌ 否 | 接收推送的 Telegram Chat ID                                                |
| `PUSH_LEVEL`         | ❌ 否 | 推送级别：`fail_only`（默认，仅失败推送）或 `all`（每次均推送）            |
| `EXCHANGE_PLAN`      | ❌ 否 | 积分自动兑换计划（#11）：`plan500`（默认，500 分自动兑换 100 天）、`plan200`（200 分→30 天）、`plan100`（100 分→10 天）或 `off`（关闭）。兑换结果即使 `PUSH_LEVEL=fail_only` 也会推送。 |

PushPlus、Server酱和 Telegram 均为可选，可单独使用，也可同时配置；多个渠道配置后会分别发送同一份多账号汇总，并遵循同一个 `PUSH_LEVEL` 设置。只读诊断（`diagnose_only`）不发送推送。

### 🍪 2026 年 9 月新版会话 Cookie

2026 年 9 月的新认证新增了 `gld:sess` 与 `gld:sess.sig`。旧的两项 `koa:sess`
即使尚未过期，也可能只能维持网页兼容状态，调用新版 API 时会返回“没有权限”。请在
Chrome 开发者工具的 **Network** 中选中一次成功的 `/api/user/status` 请求，从
**Request Headers → Cookie** 复制完整值，并确认其中同时存在 `gld:sess` 和
`gld:sess.sig`。`__stripe_mid` 属于支付组件 Cookie，不是签到认证的必要字段，保留也
不会影响请求。请勿在 Issue、日志或聊天中公开任何 Cookie 内容。

新版签到还会校验登录设备。若日志显示 `device-mismatch` 或 “Automated check-in
detected”，请打开同一个浏览器的 `chrome://version`，复制“用户代理”完整内容，并在
仓库 **Settings → Secrets and variables → Actions → Variables** 中设置
`GLADOS_USER_AGENT`。浏览器升级后，应重新登录并同步更新 Cookie 与 User-Agent。

更新后可以先运行只读检查：在 **Actions → GLaDOS 2026 Checkin → Run workflow** 中，
`dispatch_source` 选 `manual`，勾选 `diagnose_only`。只读检查仅请求登录状态，日志不输出
Cookie、邮箱或账号余额，也不会签到、兑换积分或发送推送。所有账号状态查询通过时工作流
成功；查询失败时工作流失败。GitHub 自身仍可能发送工作流失败邮件。
本地使用时设置 `CHECKIN_DIAGNOSTIC_ONLY=true` 后运行脚本即可。

注意：只读查询成功不代表签到的设备校验也已通过。确认 Cookie 与 User-Agent 对应后，
再取消勾选 `diagnose_only` 执行一次实际签到；若不希望自动兑换，可先将仓库变量
`EXCHANGE_PLAN` 设为 `off`。

完整 Cookie 与 User-Agent 都已配置但仍失败时，请先核对以下信息：

- 普通签到和只读诊断都会显示 `浏览器 User-Agent: 已配置` 或 `未配置，使用默认值`，
  不输出具体值。Actions 优先读取 **Variables** 中的 `GLADOS_USER_AGENT`；Variable
  未设置或为空时，兼容读取同名 **Secret**。两处都配置时以 Variable 为准，更新时请注意
  不要留下旧的 Variable。只含空格的 Variable 也会优先于 Secret，随后使用默认值；
  请清空或删除它。两处都为空时仍使用默认值。同步工作流后此兼容才会生效。
- 推荐只粘贴完整单行 User-Agent 的值，不要附带说明文字。脚本可自动去掉一对完整的
  英文外层双引号及误复制的 `User-Agent:` 前缀；包含空格的完整浏览器值也兼容一对
  英文外层单引号。自定义单个产品标识中的合法单引号会保留，只记录已规范化，不打印内容。
  含内嵌换行、无效控制字符、不支持的字符、重复引号或不成对双引号时，会在任何账号请求、
  签到、兑换和推送前报配置错误并停止，请重新复制对应浏览器的值。
  显示“已配置”只证明配置已传入并通过本地格式检查，不证明它与当前登录会话匹配。
- 提供失败运行的链接（或 commit SHA）、浏览器名称/版本、GitHub Actions 或本地运行、
  是否多账号，以及 `diagnose_only` 是否通过。日志中的 `code`、已知 `reason` 和
  `http_status` 可以帮助区分会话拒绝与网络错误。请勿公开 Cookie、Token、完整请求头或
  含个人信息的响应体。
- 签到返回设备/认证拒绝，或 HTTP 401/403 时，脚本会停止该账号的重试和后续积分查询、
  兑换请求；HTTP 401/403 不会再换域名尝试。其他账号仍继续处理。
- HTTP 5xx、请求超时或响应格式异常属于本次请求失败，不能据此认定 Cookie 失效或当天
  未签到。重试耗尽后，脚本会跳过该账号的后续积分查询和兑换，仍发送失败通知并返回失败。
  通知标题标明“本次运行失败”，未知的积分和天数显示“未获取”；请结合当天其他成功运行或
  官网签到日历核对。日志和推送正文的时间统一使用北京时间（UTC+8）。

`Automated check-in detected` 是服务端的拒绝结果，仅凭这句文案不能确定具体触发条件，
也不能保证设置 User-Agent 后必然恢复。只读查询通过但实际签到仍被拒绝时，请保留脱敏
结果并联系服务方确认会话或自动化使用策略，不要反复触发签到。

### 签到只获得 1 积分（#28）

2026-11-06 已核对官网控制台的新流程：签到前会获取一次性 challenge，等待后提交对应的
nonce/proof。旧脚本仅提交 token，缺少这一步；请同步最新 `checkin.py`。新版本为每次尝试
获取新验证，并在签发验证的同一域名提交；验证失败或过期时会停止本次提交并给出脱敏错误，
不会静默退回旧流程。只读诊断仍只查询状态，不获取验证、不签到。

服务端决定实际入账积分。接口返回 `Checkin! Got 1 Points` 且流水增加 1，说明已签到但
本次奖励较低；不应把它当作网络失败反复补签。当天已经入账的积分不保证能补差，适配后的
奖励数额需由下一次首次签到的服务端响应和积分流水验证。此项与 User-Agent 配置问题分别排查。

### 🎁 积分自动兑换（#11）

签到攒够积分后自动兑换会员天数，实现无感自动续期：

- 每天签到后检查积分，达到阈值就自动调用 GLaDOS 兑换接口；
- 默认 **500 分 → 100 天**（`plan500`），无需任何配置即可生效；
- 想换别的档位或关闭，设置 `EXCHANGE_PLAN` 环境变量（GitHub 上可配在 **Settings → Secrets and variables → Actions → Variables**）；
- 兑换成功或失败都会推送通知（积分不足时静默跳过，不打扰）。

---

<details>
<summary><b>📚 给小白的科普：什么是 Fork、Cookie、Secrets？（新手必看）</b></summary>

> 💡 如果你已经熟悉这些概念，可以跳过这部分直接看 [快速部署](#-快速部署)

<details>
<summary><b>🍴 什么是 Fork？</b></summary>

**Fork** = 把别人的项目复制一份到你自己的账号下。

就像复印一份文档，原件还在别人那里，你有一份自己的副本可以随便改。Fork 之后这个项目就属于你了，你可以自己配置和使用。

</details>

<details>
<summary><b>🍪 什么是 Cookie？</b></summary>

**Cookie** = 网站记住你是谁的"通行证"。

当你登录 GLaDOS 后，网站会给你的浏览器一个"通行证"（Cookie），下次访问时浏览器出示这个通行证，网站就知道你是谁了。

我们需要把这个通行证告诉签到程序，这样程序就能"假装"是你去签到。

</details>

<details>
<summary><b>🔐 什么是 Secrets？</b></summary>

**Secrets** = 保险箱，用来存放敏感信息。

你的 Cookie 和 Token 都是隐私信息，不能直接写在代码里（否则别人都能看到）。GitHub Secrets 就像一个保险箱，把这些敏感信息锁起来，只有你的程序运行时才能访问。

</details>

<details>
<summary><b>⚙️ 什么是 GitHub Actions？</b></summary>

**GitHub Actions** = 免费的自动化机器人。

它可以按照你设定的时间表（比如每天 9:30）自动运行程序。你不需要自己的服务器，GitHub 会免费帮你跑代码。

</details>

<details>
<summary><b>▶️ 什么是 Run workflow？</b></summary>

**Run workflow** = 手动测试按钮。

| 按钮             | 作用                                               |
| ---------------- | -------------------------------------------------- |
| **Run workflow** | 选择 `dispatch_source: manual` 后立即执行一次，用于测试配置是否正确 |
| **定时任务**     | 每天 9:30 自动执行，不需要手动操作                 |

简单说：点 Run workflow 是**测试**，以后会**自动运行**。

</details>
</details>

---

## 🚀 快速部署

### 第一步：Fork 本仓库

点击页面右上角的 **Fork** 按钮，将项目复制到你的账号下。

---

### 第二步：获取 Cookie 🍪

> ⚠️ **注意**：GLaDOS 官网已迁移到 **[https://glados.cloud](https://glados.cloud)**，请使用新域名！

#### 2.1 打开浏览器开发者工具

推荐直接使用 Chrome/Edge 自带的开发者工具；也可以使用 Cookie-Editor：

![Cookie-Editor 扩展](images/cookie-extension.png)

> 💡 **提示**：无论使用哪种方式，都必须取得新版的 `gld:sess` 和 `gld:sess.sig`，
> 不能再只复制旧的两项 `koa:sess`。

![可选的 Cookie 扩展](images/cookie-alternative.png)

#### 2.2 登录 GLaDOS 并获取 Cookie

1. 打开 [https://glados.cloud](https://glados.cloud)，退出后重新登录；
2. 进入 **签到页面**（Console → Checkin），按 `F12` 打开开发者工具；
3. 选择 **Network**，刷新页面，点开一次成功的 `/api/user/status` 请求；
4. 在 **Request Headers** 中找到 `Cookie`，右键复制它的完整值；
5. 确认完整值中同时存在 `gld:sess=` 和 `gld:sess.sig=`。

![获取 Cookie](images/glados-cookies.png)

#### 2.3 Cookie 格式（重要！）

直接使用上一步复制的完整值。它通常包含新旧两组会话 Cookie，例如：

```text
koa:sess=旧会话; koa:sess.sig=旧签名; gld:sess=新会话; gld:sess.sig=新签名
```

其他 Cookie 可以保留；`__stripe_mid` 与签到认证无关，但不会造成问题。

也支持将 Cookie-Editor 导出的 JSON 数组整体保存到 `GLADOS_COOKIE`，可以保留缩进和
换行；整个数组按一个账号处理。多账号请使用上面的 Cookie 请求头格式，每个账号占一行。

**常见错误**：

- ❌ 仍然只复制 `koa:sess` 与 `koa:sess.sig`
- ❌ 漏掉 `gld:sess.sig`
- ❌ 把 `Cookie:` 之外的整段请求头一起复制
- ❌ 值两边多了引号
- ❌ 将 Cookie 发布到 Issue、日志或聊天中

#### 2.4 验证你的 Cookie 格式

运行以下 Python 代码验证格式是否正确：

```python
# 将你的 Cookie 粘贴到下面的引号中
cookie = "gld:sess=你的新会话; gld:sess.sig=你的新签名"

# 验证
if "gld:sess=" in cookie and "gld:sess.sig=" in cookie:
    print("✅ 已包含新版会话 Cookie！")
else:
    print("❌ Cookie 缺少 gld:sess 或 gld:sess.sig")
```

---

### 第三步：配置 GitHub Secrets 🔐

1. 进入你 Fork 的仓库
2. 点击 **Settings**（设置）
3. 左侧菜单找到 **Secrets and variables** → **Actions**
4. 点击右上角 **New repository secret**

![添加 Secret](images/add-secret.png)

按需添加以下 Secret：

| Name             | Value                    | 必需  |
| ---------------- | ------------------------ | ----- |
| `GLADOS_COOKIE`  | 第二步组合的 Cookie      | ✅ 是 |
| `PUSHPLUS_TOKEN` | 微信推送 Token（见下方） | ❌ 否 |
| `SERVERCHAN_SENDKEY` | Server酱 SendKey（见下方） | ❌ 否 |

---

### 第四步：配置微信推送（可选）📱

如果你希望收到**微信通知**，可选择 Server酱或 PushPlus，也可同时配置。

#### Server酱

1. 需要微信通知时，访问 [Server酱 Turbo](https://sct.ftqq.com/)，登录并绑定微信接收渠道。本项目也兼容 [Server酱³](https://sc3.ft07.com/) 的独立 App 推送，接收方式见[官方通道说明](https://sct.ftqq.com/docs/getting-started/channels/)。
2. 复制自己的 **SendKey**，Turbo 通常以 `SCT` 开头，Server酱³ 以 `sctp` 开头。
3. 回到仓库 **Settings** → **Secrets and variables** → **Actions** → **New repository secret**，Name 填 `SERVERCHAN_SENDKEY`，Secret 填完整 SendKey，然后保存。

只使用 Server酱时，无需配置 `PUSHPLUS_TOKEN`。推送包含账号、积分、剩余天数、签到结果和兑换信息，正文会转换为 Markdown。

默认 `PUSH_LEVEL=fail_only`，仅在签到失败或发生兑换时推送。若希望每次签到成功也收到通知，请在 **Settings** → **Secrets and variables** → **Actions** → **Variables** → **New repository variable** 中添加 `PUSH_LEVEL`，值设为 `all`。这里的 `PUSH_LEVEL` 应配置为 **Variable**。

#### PushPlus

1. 访问 [https://www.pushplus.plus](https://www.pushplus.plus)
2. 点击右上角 **登录**，使用微信扫码登录

![PushPlus 扫码登录](images/pushplus-checkin.png)

3. 登录后点击 **发送消息** → **一对一消息**
4. 复制页面上显示的 **Token**（类似 `05c3****dd36` 的字符串）

![获取 Token](images/pushplus-token.png)

5. 将 Token 添加到 GitHub Secrets，Name 填 `PUSHPLUS_TOKEN`

---

### 第五步：启用 Actions ⚡

1. 进入你 Fork 仓库的 **Actions** 标签页
2. 如果看到黄色提示，点击 **I understand my workflows, go ahead and enable them**
3. 点击左侧的 **GLaDOS 2026 Checkin**
4. 点击右侧 **Run workflow**，选择 `dispatch_source: manual` 后手动测试一次

![启用 Actions](images/workflow.png)

> [!IMPORTANT]
>
> 完成首次手动测试后，内置 schedule 会每天运行。请勿再配置相同时间的外部 cron，否则会重复执行。
>
> 当前 `dispatch_source` 为可选输入，省略时默认 `external`；建议外部任务显式填写，便于辨认来源。仅发送 `{"ref":"main"}` 也可触发当前工作流，不能用它阻止旧定时器；请在 cron-job.org 停用不再需要的任务。

---

## ⭐ 可选备用：cron-job.org

只有在你的网络环境或 GitHub 计划任务长期不触发时才需要外部 cron。使用它时，请删除或注释 `.github/workflows/checkin.yml` 中的 `schedule`，确保只保留一个调度器。

### 配置步骤

#### 第一步：获取 GitHub Personal Access Token

1. 访问 [https://github.com/settings/tokens](https://github.com/settings/tokens)
2. 推荐点击 **Generate new token** → **Fine-grained personal access token**
3. Repository access 只选择你自己的 `2026-glados-checkin` Fork
4. Repository permissions → **Actions: Read and write**
5. 生成后立即复制；不要把 Token 发到 Issue、截图或写入仓库

> 使用 classic PAT 时，此接口需要 `repo` scope；`workflow` scope 主要用于修改 workflow 文件，并不是调用 dispatch 接口的替代权限。优先使用权限更小的 fine-grained PAT。

#### 第二步：注册 cron-job.org

1. 访问 [https://cron-job.org](https://cron-job.org) 注册账号（免费）
2. 注册后登录，点击 **Create Cronjob** 创建任务

#### 第三步：创建签到任务（9:30）

![创建 Cron 任务](images/create_corn_job.png)

按照以下配置填写：

**基本信息**：

| 选项      | 填写                                                                                                   |
| --------- | ------------------------------------------------------------------------------------------------------ |
| **Title** | `GLaDOS 早签到`                                                                                        |
| **URL**   | `https://api.github.com/repos/你的用户名/2026-glados-checkin/actions/workflows/checkin.yml/dispatches` |

> ⚠️ **重要**：把 `你的用户名` 改成你的 GitHub 用户名！比如 `lankerr`

**执行时间**：选择每天 **09:30**（Asia/Shanghai 时区）

**高级配置**（点击 Advanced 展开）：

![高级配置](images/cron_advanced.png)

| 选项               | 值            |
| ------------------ | ------------- |
| **Request method** | POST          |
| **Time zone**      | Asia/Shanghai |

**请求头（Headers）**：点击 "+ 添加" 添加三行：

| Key             | Value                            |
| --------------- | -------------------------------- |
| `Accept`        | `application/vnd.github+json`     |
| `Authorization` | `Bearer 你复制的GitHub_Token`     |
| `Content-Type`  | `application/json`               |

> Authorization 示例只应写成占位形式：`Bearer github_pat_xxx`。不要公开真实 Token。

**请求体（Request body）**：选择 Raw Body，填入：

```json
{ "ref": "main", "inputs": { "dispatch_source": "external" } }
```

![常用配置预览](images/cron_common.png)

配置完成后点击 **Save** 保存。

#### 第四步：测试验证

1. 在任务列表点击 **Test run** 测试
2. 当前 GitHub API 成功时会返回 **200**；旧 API 版本可能返回 **204**，两者都代表 dispatch 已接受 ✅

![测试成功](images/cron_success.png)

3. 到 GitHub 仓库的 **Actions** 页面查看，应该有新的运行记录

---

### 🚨 常见陷阱与错误

| 错误                         | 现象         | 原因                   | 解决方法                                       |
| ---------------------------- | ------------ | ---------------------- | ---------------------------------------------- |
| **401 Unauthorized**         | 认证失败     | Authorization 格式错误 | 使用 `Bearer github_pat_xxx`                    |
| **422 Unprocessable Entity** | 请求无法处理 | ref 缺失/不存在或输入参数不合法 | 按上面的完整 Request body 填写                 |
| **404 Not Found**            | 找不到工作流 | Actions 未启用或文件不存在 | 先完成 Fork、启用 Actions 并手动运行一次      |
| Accept 被截断                | 配置错误     | 输入框显示不全         | 完整值：`application/vnd.github.v3+json`       |
| Token 有空格                 | 认证失败     | Token 被意外截断       | Token 是连续字符串，中间不能有空格             |
| 权限不足                     | 403 错误     | Token 无 Actions 写权限 | fine-grained PAT 设置 Actions: Read and write  |

> 💡 **小贴士**：遇到 401/422 错误时，先检查上面三行 Headers 是否完全正确！

**🎉 完成！** 外部 cron 会每天 9:30 触发一次。记得关闭内置 schedule，避免重复运行。

---

## 💻 本地/独立服务器部署教程

如果你有自己的长期运行的电脑（如树莓派、软路由、VPS 等），也可以非常简单地在本地运行：

### 第一步：安装依赖

首先确保你已经安装了 Python 3，然后安装依赖库：

```bash
git clone https://github.com/你的用户名/2026-glados-checkin.git
cd 2026-glados-checkin
pip install -r requirements.txt
```

### 第二步：配置并运行

使用环境变量传递 Cookie 并直接运行 Python 脚本：

```bash
# 配置 Cookie
export GLADOS_COOKIE="gld:sess=xxxxxx; gld:sess.sig=yyyyyy"

# 可选：配置推送
export PUSH_LEVEL="all"
export SERVERCHAN_SENDKEY="SCT..."
export TELEGRAM_BOT_TOKEN="xxx"
export TELEGRAM_CHAT_ID="yyy"

# 执行签到
python3 checkin.py
```

### 第三步：设置定时任务 (Cron)

通过 `crontab -e` 配置每天自动执行（例如每天早上 9:30）：

```bash
30 9 * * * export GLADOS_COOKIE="gld:sess=xxx; gld:sess.sig=yyy"; cd /path/to/2026-glados-checkin && python3 checkin.py >> glados.log 2>&1
```

---

## ❄️ NixOS 服务配置

本项目提供了标准的 Nix Flake，你可以直接作为 inputs 引入，系统会自动管理 Python 环境和依赖包。

### 使用方法 (Flakes)

在你的 [`flake.nix`](flake.nix) 中引入本项目：

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    glados-checkin.url = "github:lankerr/2026-glados-checkin"; # 若本地测试可改写为 path:/绝对路径
  };

  outputs = { self, nixpkgs, glados-checkin, ... }: {
    nixosConfigurations.my-server = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        # 引入 glados-checkin 的 NixOS 模块
        glados-checkin.nixosModules.default

        ({ config, pkgs, ... }: {
          # 配置服务
          services.glados-checkin = {
            enable = true;
            cookie = "gld:sess=xxx; gld:sess.sig=yyy";

            # 【可选】消息推送配置
            pushLevel = "all"; # 或 "fail_only"
            pushplusToken = "xxx";
            serverchanSendkey = "SCT...";
            telegramBotToken = "yyy";
            telegramChatId = "zzz";
          };
        })
      ];
    };
  };
}
```

部署配置后执行 `sudo nixos-rebuild switch --flake .#my-server`，签到任务即会自动注册为 systemd timers。

---

## 📊 推送效果预览

签到成功后，你会在微信收到类似这样的推送：

```text
👤 your@email.com

当前积分: 46 (+20)
剩余天数: 353 天
签到结果: Bindweed! Bindweed!

🎁 兑换选项:
❌ 100分→10天 (差54分)
❌ 200分→30天 (差154分)
❌ 500分→100天 (差454分)
```

---

## ⏰ 自动运行时间

| 时间（北京时间） | 说明     |
| ---------------- | -------- |
| **09:30**        | 早间签到 |

> 默认使用 GitHub Actions；脚本内部最多尝试三次。外部 cron 是备用方案，不应与内置 schedule 同时启用。

---

## ❓ 常见问题

<details>
<summary><b>Q: GitHub Actions 会不会在两个月后停止？</b></summary>

GitHub 官方规则是：公开仓库连续 **60 天没有仓库活动**时，计划任务会自动停用。计划任务还可能因高负载延迟，尤其是在整点附近。

本项目的 `.github/workflows/keep-alive.yml` 每月更新一次 `.github/last-active.txt`，早于 60 天期限。若你是旧 Fork：

1. 点击 **Sync fork → Update branch**。
2. 打开 Actions，选择两个 workflow，确认状态为 Enabled。
3. 手动运行一次 `GLaDOS 2026 Checkin` 验证 Cookie。

[GitHub 官方 schedule 说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)

</details>

<details>
<summary><b>Q: cron-job.org 测试返回 401/404/422 错误怎么办？</b></summary>

请对照以下检查：

**401 Unauthorized（认证失败）**：

```text
❌ Authorization: github_pat_xxx
✅ Authorization: Bearer github_pat_xxx
```

注意：`Bearer ` 前缀后面必须有一个**空格**。

**404 Not Found**：先完成 Fork，在 GitHub Actions 页面启用工作流并手动运行一次；同时确认 URL 中的用户名和仓库名正确。

**422 Unprocessable Entity（请求无法处理）**：

外部定时器建议使用：

```json
{"ref":"main","inputs":{"dispatch_source":"external"}}
```

当前 `dispatch_source` 可省略，默认 `external`，因此 `{"ref":"main"}` 本身不是错误。遇到 422，请检查是否提供 `ref`、对应分支是否存在，以及 `inputs` 名称和取值是否与工作流一致。旧定时器需要在调度服务中停用，不能依赖省略此输入来阻止执行。

**其他检查**：

- Accept 头是否完整：`application/vnd.github+json`
- Fine-grained PAT 是否有目标仓库的 `Actions: Read and write` 权限
- Token 是否过期（检查 Expiration 设置）

[🔝 查看完整陷阱列表](#-常见陷阱与错误)

</details>

<details>
<summary><b>Q: 显示 "please checkin via https://glados.cloud" 怎么办？</b></summary>

这表示你使用的签到脚本已过期！GLaDOS 在 2026 年更新了 API，旧脚本的 token 值 `glados.one` 已失效。

**解决方案**：使用本项目，我们已经修复了这个问题（token 改为 `glados.cloud`）。

</details>

<details>
<summary><b>Q: 显示 "Checkin Repeats! Please Try Tomorrow" 是什么意思？</b></summary>

这表示**今天已经成功签到过了**！这是正常的成功响应，说明签到功能正常工作。

</details>

<details>
<summary><b>Q: Cookie 多久过期？</b></summary>

没有固定保证。退出登录、修改密码、服务端会话策略变化都可能让 Cookie 提前失效。Actions 真正失败并提示登录/认证问题时，重新获取 Cookie 并更新 `GLADOS_COOKIE` 即可。

</details>

<details>
<summary><b>Q: 支持多个账号吗？</b></summary>

支持！用英文符号 `&` 分隔多个 Cookie：

```text
cookie1&cookie2&cookie3
```

</details>

<details>
<summary><b>Q: 没有收到微信推送怎么办？</b></summary>

1. 检查所选渠道的 Secret 是否配置正确：Server酱使用 `SERVERCHAN_SENDKEY`，PushPlus 使用 `PUSHPLUS_TOKEN`。
2. 在相应服务的网站测试发送功能，并确认已绑定接收渠道。
3. 默认 `PUSH_LEVEL=fail_only`，所有账号签到成功且没有兑换事件时不推送。需要每次推送时，在 Actions 的 **Variables** 中设置 `PUSH_LEVEL=all`。
4. 确认手动运行时没有勾选 `diagnose_only`，并查看 Actions 日志中的推送结果。

PushPlus 完全可选，不影响签到。[PushPlus 官方说明](https://www.pushplus.plus/doc/function/verify.html)要求发送消息的账号完成实名认证，未实名通常返回 `905`；认证费用以其当时页面为准，不是本项目收取的费用。

不使用该服务时，可以不配置或删除 `PUSHPLUS_TOKEN`；签到仍会执行，也可以配置 `SERVERCHAN_SENDKEY` 使用 Server酱，或配置 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_CHAT_ID` 使用 Telegram 推送。

</details>

<details>
<summary><b>Q: 为什么一天运行多次、收到多条通知？</b></summary>

通常是同时启用了 GitHub 内置 schedule 和 cron-job.org。请二选一；本项目默认只需内置 schedule。新版默认 `PUSH_LEVEL=fail_only`，正常完成时不会反复推送。

</details>

<details>
<summary><b>Q: 积分、兑换天数和流量怎么算？</b></summary>

签到积分、会员剩余天数和流量额度是不同的量。本项目从 GLaDOS API 读取积分、剩余天数与兑换选项；脚本不会为账号分配或重置流量，也不能用固定的“积分 → GB”比例计算流量。

自动兑换使用本仓库预设的 `EXCHANGE_PLAN`（默认 `plan500`，按 500 分→100 天配置）向服务端提交兑换请求；实际可选档位、到账天数、套餐流量和重置规则，均以自己账号的 [GLaDOS 控制台](https://glados.cloud/console) 为准。若不希望自动兑换，设置仓库 Variable `EXCHANGE_PLAN=off`。不要把某次显示的“500 分→90 天”或其他档位当作长期不变的承诺。

</details>

<details>
<summary><b>Q: Actions 运行失败怎么办？</b></summary>

1. 点击失败的运行记录查看详细日志
2. 检查 Cookie 格式是否正确
3. 如果还是不行，欢迎提 Issue！

</details>

---

## ⚠️ 运行机制与限制

GitHub 的 schedule 不是实时调度器：高负载时可能延迟，极端情况下可能丢弃排队任务；公开仓库连续 60 天无活动会自动停用 schedule。为降低风险，本项目采用非整点运行、脚本内三次重试和每月一次保活提交。

这仍不能保证第三方服务 100% 可用：GLaDOS 宕机、Cookie 失效、GitHub 故障或用户自行关闭 Actions 时，签到会失败。新版会让真正失败返回非零退出码，以便 Actions 邮件和可选通知准确报警。

---

## 📂 项目文件

| 文件                                                                         | 说明                |
| ---------------------------------------------------------------------------- | ------------------- |
| [`checkin.py`](checkin.py)                                                     | 核心签到脚本        |
| `.github/workflows/checkin.yml`                                              | GitHub Actions 配置 |
| [`requirements.txt`](requirements.txt)                                        | Python 依赖         |
| `tests/`                                                                       | 结果判断与重试测试  |
| `images/`                                                                    | 教程截图            |

---

## 🤝 需要帮助？

- 📝 **提 Issue**：遇到问题请提 Issue，作者很乐意帮助技术新手！
- ⭐ **Star**：如果对你有帮助，请点个 Star 支持一下
- 🍴 **Fork**：欢迎 Fork 并贡献代码

---

## 🙏 致谢

感谢通过 Pull Request 改进本项目的贡献者。每一项修复和文档改进都让自动签到更可靠，也让新用户更容易完成配置。

| 贡献者 | 贡献 | Pull Request |
| --- | --- | --- |
| [@Ch3nSir](https://github.com/Ch3nSir) | 添加 Server酱 Turbo / Server酱³ 推送支持，补充部署说明、NixOS 配置和通知回归测试。 | [#27](https://github.com/lankerr/2026-glados-checkin/pull/27) |
| [@badpinkman](https://github.com/badpinkman) | 适配新版 `gld:sess` 会话与浏览器设备校验，完善 Cookie 获取、User-Agent 配置和认证失败提示，并提供真实运行验证。 | [#18](https://github.com/lankerr/2026-glados-checkin/pull/18) |
| [@Unexpectedlyc](https://github.com/Unexpectedlyc) | 调整 README 的部署顺序与说明，减少 GitHub Actions 和外部定时器配置带来的误解。 | [#5](https://github.com/lankerr/2026-glados-checkin/pull/5) |
| [@Initsnow](https://github.com/Initsnow) | 添加 Telegram 推送、通知级别与 NixOS Flake 支持，并修复 Telegram 消息格式问题。 | [#3](https://github.com/lankerr/2026-glados-checkin/pull/3) |

同时感谢 [@LxFairy](https://github.com/LxFairy) 提交上游同步与冲突处理 PR（[#8](https://github.com/lankerr/2026-glados-checkin/pull/8)、[#9](https://github.com/lankerr/2026-glados-checkin/pull/9)，未合并），以及在 Issues 中提供报错日志、排查线索和复测反馈的用户。

感谢 [@chengchang1987-cloud](https://github.com/chengchang1987-cloud) 在 [Issue #28](https://github.com/lankerr/2026-glados-checkin/issues/28) 提供积分流水、challenge 排查证据和[参考脚本](https://github.com/lankerr/2026-glados-checkin/issues/28#issuecomment-6676702004)。参考脚本的核心 proof 算法与已合并的 #31 一致；本次进一步采纳日志即时刷新（`flush=True`）及 2.7 秒等待时间（在 2.5 秒基础上增加 0.2 秒余量）。原有的 nonce/TTL 校验、同域提交、失败时不回退旧签到流程、User-Agent 兼容和推送行为均保留。这两项改进不代表首次签到奖励已恢复，仍需以下一次首次签到返回及实际积分入账核验。

特别感谢 @badpinkman 对 2026 年 9 月认证故障的排查与修复，帮助本项目恢复正常签到。

---

## 📝 更新日志

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

**修复**：更新 [`checkin.py`](checkin.py) 中的 token 参数。

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

## 📝 License

MIT

---

<div align="center">

**Made with ❤️ for GLaDOS users in 2026**

**🔧 本项目最近一次维护验证：2026-11-06**

**⭐ Star 一下，支持作者持续更新！⭐**

</div>
