# 使用手册

[返回项目首页](../README.md) · [当前运行边界](../README.md#status)

本页保留配置参数、图解部署和排障细节。**先选运行模式，再配置凭据**：Actions 定时默认只读；完整签到可能调用默认 `plan500` 自动兑换，不需要时设 `EXCHANGE_PLAN=off`。不要同时启用多个调度器。

> 当前通知的“今日加分”只基于接口返回的前 10 条记录，筛选当天正变动并排除 exchange/refund；不是完整当日流水，也不能与某次请求强行关联。

<a id="config"></a>
## 🛠 配置参数 (环境变量)

本项目支持以下环境变量配置：

| 变量名               | 必填  | 说明                                                                       |
| -------------------- | ----- | -------------------------------------------------------------------------- |
| `GLADOS_COOKIE`      | ✅ 是 | GLaDOS 的完整 Cookie，必须包含 `gld:sess` 与 `gld:sess.sig`。多个账号请用 `&` 或换行符分隔。 |
| `CHECKIN_DIAGNOSTIC_ONLY` | ❌ 否 | `true`：只检查状态，不签到、兑换或推送。 |
| `CHECKIN_NOTIFY_STATUS_ONLY` | ❌ 否 | `true`：只读取状态与积分并推送，不签到、兑换。 |
| `GLADOS_USER_AGENT`  | ❌ 否 | 生成当前 `gld:sess` 时浏览器的完整 User-Agent；新版设备校验失败时需要配置。 |
| `PUSHPLUS_TOKEN`     | ❌ 否 | PushPlus 微信推送 Token。                                                  |
| `SERVERCHAN_SENDKEY` | ❌ 否 | Server酱 SendKey，支持 Turbo（`SCT...`）与 Server酱³（`sctp...`）。         |
| `TELEGRAM_BOT_TOKEN` | ❌ 否 | Telegram 机器人的 Token（例如 `123456:ABC-DEF1234...`）                    |
| `TELEGRAM_CHAT_ID`   | ❌ 否 | 接收推送的 Telegram Chat ID                                                |
| `PUSH_LEVEL`         | ❌ 否 | 推送级别：`fail_only`（默认，仅失败推送）或 `all`（每次均推送）            |
| `EXCHANGE_PLAN`      | ❌ 否 | 积分自动兑换计划（#11）：`plan500`（默认，500 分自动兑换 100 天）、`plan200`（200 分→30 天）、`plan100`（100 分→10 天）或 `off`（关闭）。兑换结果即使 `PUSH_LEVEL=fail_only` 也会推送。 |
| `GLADOS_BROWSER_CHECKIN` | ❌ 否 | Turnstile 真浏览器兜底开关：默认开启；`0` 关闭。检测到 `GITHUB_ACTIONS` 时默认自动禁用，设 `1` 可显式尝试（尚未验证 Actions 首次签到恢复）。 |
| `GLADOS_BROWSER_HEADLESS` | ❌ 否 | 浏览器兜底改无头模式：默认 `0`（有头）；未验证不同环境的成功率。 |

PushPlus、Server酱和 Telegram 均为可选，可单独使用，也可同时配置；多个渠道配置后会分别发送同一份多账号汇总，并遵循同一个 `PUSH_LEVEL` 设置。只读诊断（`diagnose_only`）不发送推送。

<a id="cookie"></a>
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

完整签到模式可按所选计划尝试兑换会员天数；只读模式不兑换。实际档位和权益以账号控制台为准：

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

**GitHub Actions** = 仓库的自动化运行平台。

它可以按照你设定的时间表（比如每天 9:30）自动运行程序。你不需要自己的服务器，实际额度和计费以 GitHub 账号与仓库规则为准。

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

<a id="deploy"></a>
## 🚀 快速部署

### 第一步：Fork 本仓库

点击页面右上角的 **Fork** 按钮，将项目复制到你的账号下。

---

<a id="get-cookie"></a>
### 第二步：获取 Cookie 🍪

> ⚠️ **注意**：GLaDOS 官网已迁移到 **[https://glados.cloud](https://glados.cloud)**，请使用新域名！

#### 2.1 打开浏览器开发者工具

推荐直接使用 Chrome/Edge 自带的开发者工具；也可以使用 Cookie-Editor：

![Cookie-Editor 扩展](../images/cookie-extension.png)

> 💡 **提示**：无论使用哪种方式，都必须取得新版的 `gld:sess` 和 `gld:sess.sig`，
> 不能再只复制旧的两项 `koa:sess`。

![可选的 Cookie 扩展](../images/cookie-alternative.png)

#### 2.2 登录 GLaDOS 并获取 Cookie

1. 打开 [https://glados.cloud](https://glados.cloud)，退出后重新登录；
2. 进入 **签到页面**（Console → Checkin），按 `F12` 打开开发者工具；
3. 选择 **Network**，刷新页面，点开一次成功的 `/api/user/status` 请求；
4. 在 **Request Headers** 中找到 `Cookie`，右键复制它的完整值；
5. 确认完整值中同时存在 `gld:sess=` 和 `gld:sess.sig=`。

![获取 Cookie](../images/glados-cookies.png)

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
# 从已配置的环境变量检查格式，不打印 Cookie
import os
cookie = os.environ.get("GLADOS_COOKIE", "")

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

![添加 Secret](../images/add-secret.png)

按需添加以下 Secret：

| Name             | Value                    | 必需  |
| ---------------- | ------------------------ | ----- |
| `GLADOS_COOKIE`  | 第二步组合的 Cookie      | ✅ 是 |
| `PUSHPLUS_TOKEN` | 微信推送 Token（见下方） | ❌ 否 |
| `SERVERCHAN_SENDKEY` | Server酱 SendKey（见下方） | ❌ 否 |

---

<a id="notifications"></a>
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

![PushPlus 扫码登录](../images/pushplus-checkin.png)

3. 登录后点击 **发送消息** → **一对一消息**
4. 复制页面上显示的 **Token**（类似 `05c3****dd36` 的字符串）

![获取 Token](../images/pushplus-token.png)

5. 将 Token 添加到 GitHub Secrets，Name 填 `PUSHPLUS_TOKEN`

---

### 第五步：启用 Actions ⚡

1. 进入你 Fork 仓库的 **Actions** 标签页
2. 如果看到黄色提示，点击 **I understand my workflows, go ahead and enable them**
3. 点击左侧的 **GLaDOS 2026 Checkin**
4. 点击右侧 **Run workflow**，选择 `dispatch_source: manual`，先勾选 `diagnose_only` 做只读认证检查；需要状态通知时改勾选 `notify_status_only`。两者均不勾选才是完整签到模式，可能触发默认自动兑换。

![启用 Actions](../images/workflow.png)

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

![创建 Cron 任务](../images/create_corn_job.png)

按照以下配置填写：

**基本信息**：

| 选项      | 填写                                                                                                   |
| --------- | ------------------------------------------------------------------------------------------------------ |
| **Title** | `GLaDOS 早签到`                                                                                        |
| **URL**   | `https://api.github.com/repos/你的用户名/2026-glados-checkin/actions/workflows/checkin.yml/dispatches` |

> ⚠️ **重要**：把 `你的用户名` 改成你的 GitHub 用户名！比如 `lankerr`

**执行时间**：选择每天 **09:30**（Asia/Shanghai 时区）

**高级配置**（点击 Advanced 展开）：

![高级配置](../images/cron_advanced.png)

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

![常用配置预览](../images/cron_common.png)

配置完成后点击 **Save** 保存。

#### 第四步：测试验证

1. 在任务列表点击 **Test run** 测试
2. 当前 GitHub API 成功时会返回 **200**；旧 API 版本可能返回 **204**，两者都代表 dispatch 已接受 ✅

![测试成功](../images/cron_success.png)

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

以下为 Python 手动部署。接口状态查询可在多种环境运行；本地浏览器签到需要可用的浏览器及对应运行环境，不保证在 VPS、容器、树莓派或无头模式通过验证。

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

通过 `crontab -e` 配置每天尝试执行（下例使用系统本地时区）。示例仅含占位值；不要把真实凭据留在共享 crontab、终端历史或公开日志中，应通过受保护的本地配置注入。请只启用一个调度器，不能以重复尝试保证成功：

```bash
30 9 * * * export GLADOS_COOKIE="gld:sess=xxx; gld:sess.sig=yyy"; cd /path/to/2026-glados-checkin && python3 checkin.py >> glados.log 2>&1
```

---

<a id="nixos"></a>
## ❄️ NixOS 服务配置

本项目提供 Nix Flake。**当前模块将 Cookie/推送凭据写入生成的服务环境，可能进入可读的 Nix store；不要直接将真实秘密填入下方演示配置。**本节保留接口参考，不表示已实现安全凭据注入或真实浏览器验收。

### 使用方法 (Flakes)

在你的 [`flake.nix`](../flake.nix) 中引入本项目：

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

以下为旧版格式示意，不是当前真实余额，也不证明本次入账。当前通知会区分接口结果与流水观察：

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
| **09:30**        | Actions 默认只读核对，可能延迟 |

> Actions 的 schedule 当前默认只读核对，不是首次签到；计划时间为北京时间 09:30，实际运行可能延迟。外部 cron 与内置 schedule 二选一。脚本的重试不等于幂等保证，模糊结果应先核对官网。

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

这是历史 API 兼容问题的常见表现，请核对版本与日志。不能仅凭这句话判断所有故障原因。

**解决方案**：使用本项目，我们已经修复了这个问题（token 改为 `glados.cloud`）。

</details>

<details>
<summary><b>Q: 显示 "Checkin Repeats! Please Try Tomorrow" 是什么意思？</b></summary>

这表示服务端认为**今天已经签到过**。它可能出现在网页手动签到之后；不能单凭此响应证明脚本完成了当日首次签到或新增积分，请核对积分流水。

</details>

<details>
<summary><b>Q: Cookie 多久过期？</b></summary>

没有固定保证。退出登录、修改密码、服务端会话策略变化都可能让 Cookie 提前失效。Actions 真正失败并提示登录/认证问题时，重新获取 Cookie 并更新 `GLADOS_COOKIE` 即可。

</details>

<details>
<summary><b>Q: 支持多个账号吗？</b></summary>

输入解析支持多个账号。**当前浏览器通道共用 profile，存在会话混用风险，不建议依此假定多账号浏览器签到已隔离。**普通 Cookie 请求头可用英文符号 `&` 分隔：

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
| [`checkin.py`](../checkin.py)                                                     | 核心签到脚本        |
| `.github/workflows/checkin.yml`                                              | GitHub Actions 配置 |
| [`requirements.txt`](../requirements.txt)                                        | Python 依赖         |
| `tests/`                                                                       | 结果判断与重试测试  |
| `images/`                                                                    | 教程截图            |

---
