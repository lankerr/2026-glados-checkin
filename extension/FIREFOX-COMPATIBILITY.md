# Firefox 兼容计划与社区 #45 取舍

当前仅做静态审阅和离线测试，没有安装、执行或复制社区 ZIP/XPI。附件没有明确许可证，先请求作者提供源码仓库、基准提交、贡献许可与正式 PR；不能把其他图表的许可证当成扩展许可。

来源：https://github.com/lankerr/2026-glados-checkin/issues/45#issuecomment-6945892282

## 独立实现并纳入本地修订的部分

- API 选择边界优先标准 browser 命名空间，否则用 chrome；目前只用于后台适配层，不表示所有 UI 已适配 Firefox。
- 受限持久存储必须存在且设置成功才能初始化。能力缺失或被拒绝时失败关闭，不悄悄退化成内容脚本可访问的账本。
- Chrome / Edge 最低声明收紧至 140，覆盖当前兼容资料中 local 存储访问限制能力。最低版本声明不是实际运行认证。
- 继续保留已有单任务、持久 SUBMITTING/UNKNOWN、默认关闭、账号绑定与 document 身份校验。

以上按接口文档独立实现，不来自附件代码。

## 尚不能直接生成可用 Firefox 包

仅把 service_worker 改成 scripts 不够。官方文档显示 Firefox 使用非持久后台脚本而非 MV3 service worker；兼容数据中 Firefox 尚无 storage.local.setAccessLevel，MessageSender.documentId 也有版本限制。我们不会通过删除 documentId 校验、放开账本访问或伪造默认身份来宣称兼容。

后续可考虑：
1. 独立 Firefox manifest，非持久模块后台；API 统一 Promise 接口。
2. 用经过验证的仅扩展后台可访问持久化方案替换账本适配器，例如专用 IndexedDB；先验证内容脚本隔离和清除行为，不未经验证直接采用。
3. 在支持的 Firefox 版本上确认 documentId；不支持时先设计且审查 document-bound 授权机制，不能只退化为 tabId。
4. 明确 Gecko ID、最低版本与真实数据传输声明，采用正常签名/临时开发加载流程，不让用户关闭全局签名校验。
5. 实测后台卸载/重启、暂停与清除竞态、权限拒绝、会话、官网按钮和流水结构，然后才考虑发布。

## 只保留思路、不直接移植

- 精确请求分类和稳定 DOM 判定有价值，但当前版本不使用 MAIN-world 响应桥接。页面消息不能作为可信成功凭据。
- 网络指数可作为未来可选信息展示；未验证语义、相关性或收益，不加入默认调度，更不宣传“收益最大化”。
- 超时应转为 UNKNOWN / NEEDS_USER 并保留页面，不能强关用户接管页面后自动重试。
- 不复制默认自动启用、多域名宽权限、任意正流水视作成功、手动绕过并发锁等逻辑。

## 证据与验证范围

官方资料（2026-11-17 检查）：
- [MDN background](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/background)
- [MDN StorageArea.setAccessLevel](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/storage/StorageArea/setAccessLevel)
- [MDN runtime.MessageSender](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/runtime/MessageSender)
- [MDN storage 兼容数据](https://github.com/mdn/browser-compat-data/blob/main/webextensions/api/storage.json)
- [MDN runtime 兼容数据](https://github.com/mdn/browser-compat-data/blob/main/webextensions/api/runtime.json)
- [Mozilla 数据声明](https://extensionworkshop.com/documentation/develop/firefox-builtin-data-consent/)

21 项 Node 离线测试通过，含 4 项新增能力选择/拒绝/失败关闭检查。未运行附件、未加载我们的扩展、未登录账号、未执行签到、未推送或发布。官方资料会变化，正式发布前必须重新核查。
