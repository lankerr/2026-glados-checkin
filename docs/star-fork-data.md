# Star 与 Fork 曲线数据说明

本图是 **2026-11-16 的静态快照**，使用 [star-history/star-history](https://github.com/star-history/star-history) 的 `XYChart` 手绘渲染组件在本地生成，不是官方网站托管的动态图。渲染源版本：`8f5608175d95aa224c656e8b4efa55ed094b889f`。绘图代码按其 MIT 许可证使用，附带许可见 [star-history-LICENSE.txt](star-history-LICENSE.txt)。

## 数据口径

- 仓库：[lankerr/2026-glados-checkin](https://github.com/lankerr/2026-glados-checkin)。查询时仓库接口返回 **108 Stars / 347 Forks**。
- Star 曲线：GitHub [`stargazers/history`](https://api.github.com/repos/lankerr/2026-glados-checkin/stargazers/history) 两页，共 44 个周记录，将返回的每日创建数量累计，终点 **108**。这不是每天实时记录的净 Star 余额；无法由此恢复已取消的星标。GitHub 文档说明日/周边界不保证与 UTC 对齐，图仅将 API 日期标签映射到横轴，不声称北京时间日统计。
- Fork 曲线：GitHub [`forks`](https://api.github.com/repos/lankerr/2026-glados-checkin/forks?per_page=100&sort=oldest) 四页，共 **303 个可列出仓库**，按 `created_at` 的 UTC 日期累计。它不等于全部历史 Fork 事件，也不保证恢复已删除或不可见 Fork。
- **347 − 303 = 44**：总数与可列出记录之间有差额，原因本次未确定，缺少的日期不补造。因此 Fork 线终点仍为 303，官方总数 347 单列于脚注。
- 不根据曲线断言公告、推广或修复带来的因果效果。未添加未经证实的“修复成功”事件标记。

每日曲线数据见 [star-fork-history.csv](star-fork-history.csv)。源说明：[GitHub 星历史 API 文档](https://docs.github.com/en/rest/activity/starring?apiVersion=2026-03-10#get-repository-star-history)。静态图片不会自动更新，需要重新获取数据并渲染。
