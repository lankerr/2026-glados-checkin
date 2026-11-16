# Star 与 Fork 曲线数据说明

本图是 **2026-11-16 的静态快照**，使用 [star-history/star-history](https://github.com/star-history/star-history) 的 `XYChart` 手绘渲染组件在本地生成，不是官方网站托管的动态图。渲染源版本：`8f5608175d95aa224c656e8b4efa55ed094b889f`。绘图代码按其 MIT 许可证使用，附带许可见 [star-history-LICENSE.txt](star-history-LICENSE.txt)。

## 数据口径

- 仓库：[lankerr/2026-glados-checkin](https://github.com/lankerr/2026-glados-checkin)。查询时仓库接口返回 **108 Stars / 347 Forks**。
- Star 曲线：GitHub [`stargazers/history`](https://api.github.com/repos/lankerr/2026-glados-checkin/stargazers/history) 两页，共 44 个周记录，将返回的每日创建数量累计，终点 **108**。这不是每天实时记录的净 Star 余额；无法由此恢复已取消的星标。GitHub 文档说明日/周边界不保证与 UTC 对齐，图仅将 API 日期标签映射到横轴，不声称北京时间日统计。
- Fork 曲线：先取根仓库 `forks` 四页共 303 条，再递归取其中有下级 Fork 的 6 个仓库，得到 47 条额外记录；按仓库 ID 去重后，共 **350 个可见 Fork 网络仓库**。47 个额外仓库逐个 GET 核验 `fork=true` 且 `source.id=1140052622`，属于本项目网络，包含间接 Fork。曲线按创建时间 `created_at` 的 UTC 日期累计。
- **图上大字 347 为根仓库官方 `forks_count` 快照，曲线终点 350 为递归枚举结果**。两者差 3，原因本次未确定，不能视为同一口径或将曲线缩放、补点强行对齐。曲线不能还原已删除、不可见或断开关联的历史 Fork，也不是逐日官方净总数。
- 此次找到的间接 Fork 说明早先“缺少 44 个是隐藏/风控账户”的解释没有证据；不能根据总数差额判断原因。
- 不根据曲线断言公告、推广或修复带来的因果效果。未添加未经证实的“修复成功”事件标记。

每日曲线数据见 [star-fork-history.csv](star-fork-history.csv)。源说明：[GitHub 星历史 API 文档](https://docs.github.com/en/rest/activity/starring?apiVersion=2026-03-10#get-repository-star-history)。静态图片不会自动更新，需要重新获取数据并渲染。
