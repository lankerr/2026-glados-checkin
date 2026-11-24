# 安卓手机自动签到（Termux 方案）

把仓库已验证的 Python 签到引擎搬进安卓手机，用 Termux + 系统任务调度实现每天自动签到，并把结果推到手机通知栏或你现有的远程渠道（PushPlus / Server酱 / Telegram）。

本方案回答 [Issue #40](https://github.com/lankerr/2026-glados-checkin/issues/40) 提出的"本地签到能否迁移至手机端"。**当前验证状态：脚本逻辑已通过离线合成测试，真机安装、定时唤醒与通知送达尚未实机验证。** 在真机跑通之前，请把它当作"待验收方案"，保留你现有的签到渠道并行观察。

## 一、安装 Termux（约 5 分钟）

从 [F-Droid](https://f-droid.org/packages/com.termux/) 安装 **Termux**，并从同一来源安装 **Termux:API**（本地通知需要这两个应用配套；Google Play 版 Termux 已停止更新，不要混用两个来源的版本）。

把本仓库放进手机。最省事的方式是直接克隆：

```sh
pkg install -y git
git clone https://github.com/lankerr/2026-glados-checkin.git
cd 2026-glados-checkin
```

也下载 ZIP 解压后用 `cd` 进入目录，效果相同。

## 二、一键引导

```sh
bash termux/bootstrap.sh
```

引导脚本会依次完成四件事，每步都有回显：

1. 安装 `python`、`termux-api` 命令行与引擎依赖 `requests`（Termux 不支持 playwright，脚本会显式关闭浏览器兜底，只走 requests 通道）；
2. 在 `~/.config/glados-termux/env` 生成配置模板并设为 600 权限（已存在则不覆盖）；
3. 获取唤醒锁（`termux-wake-lock`），允许 Termux 在后台被定时唤醒；
4. 注册系统级每日任务（JobScheduler，`--persisted true`，手机重启后仍生效，要求联网且电量不低）。

## 三、填 Cookie，手动试跑一次

编辑 `~/.config/glados-termux/env`，把 `GLADOS_COOKIE` 换成你自己浏览器里的 Cookie（获取方式与 Python 本地版相同，见[使用手册](usage.md)）。远程推送渠道按需取消注释——环境变量与仓库其他部署完全同一套。

```sh
bash termux/run-checkin.sh
```

试跑会打印引擎完整输出，并在装有 Termux:API 的手机上弹一条本地通知。锁屏只显示本轮账号结果计数；推送成功、诊断和跳过兑换都不计作签到成功。如果通知命令不可用或返回失败，终端仍会显示摘要。**Cookie 是凭据**：只放在这个 600 权限的文件里，不要截图、不要提交仓库、不要发给任何人。

## 四、定时任务的节奏

默认任务从**注册时刻**起每 24 小时跑一次（JobScheduler 的周期语义，不支持"固定 09:30"）。想贴近上午签到，在上午跑一次下面这行刷新起点：

```sh
termux-job-scheduler --job-id 101 --script "$PWD/termux/run-checkin.sh" --period-ms 86400000 --persisted true --network any --battery-not-low true --charging false
```

常用管理命令：

```sh
termux-job-scheduler --list-job     # 查看已注册任务
termux-job-scheduler --cancel-job 101
```

手机厂商的省电策略可能杀死后台 Termux。Termux 通知栏常驻的 "Acquire wakelock" 即引导脚本获取的唤醒锁；若仍被清理，在系统设置里给 Termux 与 Termux:API 关闭电池优化（各品牌路径不同，搜索"你的型号 + 电池优化白名单"）。

## 边界与已知限制

- **Turnstile 人机验证与 PC 版同一限制**：手机 IP 与机房 IP 不同、通过率可能更好，但验证由服务端决定，无法保证。遇到验证失败时，推送里的措辞与 PC 版一致，去官网手动完成当次签到即可，无需反复重试。
- **自动兑换**沿用 `EXCHANGE_PLAN` 环境变量，与 PC 版行为一致。
- **多账号**：JobScheduler 的任务编号不能证明账号隔离。安装脚本和运行入口使用不同的配置路径参数，多任务定时运行仍待验证，请勿按此草稿为不同账号注册多个任务。
- 本方案不读取通讯录、位置或短信；Termux 权限仅涉及网络与通知。

## 与其他手机路径的关系

- 浏览器插件路径（[懒人浏览器方案](../extension/README.md)）：安卓 Chrome 不支持扩展；Firefox 安卓版与部分 Chromium 内核浏览器（如 Lemur）支持部分扩展，真机安装与后台存活仍待验证，优先级低于本方案。
- 云端 GitHub Actions 路径：不需要手机保持运行，适合"手机只收通知"的用户——在仓库 Secrets 配置后，推送渠道与本文同一套。

## 验证记录

| 项目 | 状态 |
| --- | --- |
| 通知摘要（账号结果、隐私与命令失败） | ✅ 离线合成测试通过（`tests/test_termux_deploy.py`） |
| 脚本防线（禁用浏览器兜底、配置不覆盖、任务持久化） | ✅ 同上（内容级守卫） |
| shell 语法 | ✅ `bash -n` 通过 |
| 真机安装、JobScheduler 唤醒、本地通知送达、省电策略存活 | ⏳ 待实机验证（欢迎在 [Issue #40](https://github.com/lankerr/2026-glados-checkin/issues/40) 回报机型与结果） |

感谢 @chengchang1987-cloud 提出手机端需求。
