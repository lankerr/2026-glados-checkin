# GLaDOS 签到工作台

[签到方案与逐项致谢](../docs/checkin-options.md)

[跟着截图安装、核对流水与排障](../docs/desk-walkthrough.md)

在官网标签页完成签到和验证，回到工作台点 **核对官网流水**。首页显示所选站点返回的脱敏账号、读取时间、余额和最近 10 条有效流水。官网将一条正变动明确标为签到，并且入账日期属于北京时间今天时，工作台才显示 **官网已有签到入账**。其他来源的积分、缺失的流水和未知类型都会保留各自的状态。

## 安装

| 浏览器 | 安装包 | 安装入口 |
| --- | --- | --- |
| Chrome / Edge | `glados-desk-chromium-0.2.1.zip` | 解压，在 `chrome://extensions` 或 `edge://extensions` 开启开发者模式，选择「加载已解压的扩展程序」，选含 `manifest.json` 的文件夹 |
| Firefox 140 及以上 | `glados-desk-firefox-0.2.1.zip` | 解压，打开 `about:debugging#/runtime/this-firefox`，点「临时载入附加组件」，选择 `manifest.json`。此包未签名，重启后需再次载入 |

安装后点击工具栏里的扩展图标，可打开完整工作台。源代码使用项目现有图标，两个浏览器包共用页面和读取逻辑。

## 第一次使用

1. 选择你已登录的 GLaDOS 域名，点 **去官网签到**。工作台会打开或切换到当前窗口中的官网签到页。
2. 在官网确认账号，完成签到及官网要求的验证。回到工作台，点 **核对官网流水**。如果你已通过现有本地任务签到，直接核对即可。
3. 查看 **官网积分流水** 与 **本机操作记录**。后者只记录打开页面和读取流水等动作。官网可能只给余额、缺少业务标签或只返回最近的一部分流水，此时当天签到状态可能仍待确认。
4. 需要通知时勾选 **北京时间 09:30**。首次安装默认关闭提醒。浏览器关闭或设备休眠会影响送达时间。

同一窗口存在多个匹配的签到标签页时，请保留要核对的一个。读取前后会核对官网账号，账号切换、失效或网络错误会清空本次展示。对于已迁移到 Railgun 的账号，这版没有对应站点适配。

## 数据与权限

点「核对官网流水」时，扩展在选定的官网标签页读取 `/api/user/status` 和 `/api/user/points`，复用该页的登录会话。扩展只在读数时运行站点脚本。余额、流水和脱敏账号随工作台页面关闭而释放。本机存储保存域名偏好、提醒设置和最近 30 次操作的时间、域名及类别。「清空记录」能清除操作历史。

需要原有三时段自动尝试功能，请查看[经典自动插件](../extension/README.md)。

## 从源码构建

在仓库根目录执行以下命令。打包只依赖 Python 标准库。

```sh
python webextension/build.py --out dist
node --test webextension/tests/core.test.cjs
```

输出目录同时包含两个可加载的文件夹及对应 ZIP。浏览器验收脚本可用独立配置和本地模拟数据复跑。Chromium 测试使用 Playwright，Firefox 测试使用 Selenium、geckodriver 和 cryptography；参数见 `webextension/tests/browser_smoke.py --help` 和 `webextension/tests/firefox_smoke.py --help`。
