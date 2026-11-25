# 在安卓手机核对今天有没有签到入账

这个入口适合已经从电脑或官网签过到、想在手机上核对结果的人。它逐个账号读取最近 10 条积分流水，按北京时间找当天带签到标签的正数入账。终端显示各账号的最近可见签到日期和连续天数，安卓通知只显示已确认入账的账号数。

## 第一次使用

1. 安装 Termux。想收本地通知的，请从与 Termux 相同的发行渠道安装 Termux:API 安卓应用，并允许系统通知。仅看终端结果也可以使用此脚本。[Termux:API 安装说明](https://github.com/termux/termux-api#installation)
2. 在 Termux 中下载项目并安装依赖。

   ```sh
   pkg install git python termux-api nano
   git clone https://github.com/lankerr/2026-glados-checkin.git
   cd 2026-glados-checkin
   python -m pip install requests
   ```

3. 在 Termux 的私有目录建立配置文件。

   ```sh
   umask 077
   mkdir -p ~/.config/glados-termux
   touch ~/.config/glados-termux/env
   chmod 600 ~/.config/glados-termux/env
   nano ~/.config/glados-termux/env
   ```

   在编辑器中填入自己账号的 Cookie。下行是格式示例，实际值只保存在本机。文件按 shell 语法读取，仅使用自己创建的配置。

   ```sh
   GLADOS_COOKIE='gld:sess=替换为自己的值; gld:sess.sig=替换为自己的值'
   ```

4. 在仓库目录运行。下次核对只需重复这条命令。

   ```sh
   bash termux/run-ledger.sh
   ```

已有部署可通过 `GLADOS_TERMUX_ENV` 指定配置文件，或通过 `GLADOS_TERMUX_CONFIG` 指定含 `env` 的目录。显式指定的文件不可读时，脚本会报告路径配置错误并停止。未指定且默认文件不存在时，脚本可使用终端已导出的 `GLADOS_COOKIE`。

## 怎样看结果

| 看到什么 | 含义和下一步 |
| --- | --- |
| 今日已确认签到入账 1/2 个账号 | 两个账号中有一个今天收到了签到积分。终端列出各账号结果，可去官网核对另一个账号。 |
| 最近可见签到为昨天 | 最近 10 条里没看到今日签到，活动积分和补偿积分不计入。可打开官网签到页核对当天记录。 |
| HTTP 401 或 403 | 官网拒绝了本次读取。请本人打开官网检查登录状态，按页面提示完成验证。 |
| 本地通知命令未成功 | 每个账号的结果仍在终端。检查 Termux:API 应用、命令和安卓通知权限。 |

## 可选：让安卓每天核对一次

先手动运行成功，再用 `termux-job-scheduler --pending` 查看手机已有的任务。以下示例选用编号 `5402`，请确认该编号空闲；已占用就另选一个。注册命令在仓库目录运行，任务读取上面的默认私有配置文件。

```sh
termux-job-scheduler --job-id 5402 --script "$PWD/termux/run-ledger.sh" --period-ms 86400000 --persisted true --network any
termux-job-scheduler --pending
```

安卓决定实际唤醒时间，约每 24 小时读取一次。需要停用时，按实际编号执行 `termux-job-scheduler --cancel --job-id 5402`，再用 `--pending` 核对。两个管理命令的参数已按 [Termux:API 命令源码](https://github.com/termux/termux-api-package/blob/master/scripts/termux-job-scheduler.in)核对。手机定时唤醒和通知送达仍待真机验证。

感谢 @chengchang1987-cloud 提出手机端需求，感谢 @lankerr 将 Termux 配置和本地通知整理成提案。[Issue #40](https://github.com/lankerr/2026-glados-checkin/issues/40) · [PR #54](https://github.com/lankerr/2026-glados-checkin/pull/54)
