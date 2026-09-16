# UI 测试工程师独立复测 · 2026-09-15

## 范围与方法

在 `https://social-sim-arena-e2e-test.vercel.app` 用实际浏览器完成只读交互，检查标量/profile/ranking 详情、筛选、注册表单锁定状态及 390×844 手机视口。读取线上 `/data.json` 作为成绩对照（generated_at `2026-09-15T05:04:07Z`）。没有触发 Run test、LLM、注册 PR 或写入参赛数据；没有修改实现、部署。手机视口测试后已恢复。未发现本任务路径适用的 AGENTS.md。

## 失败：可独立复现

### UI-01 · P1 · Crowd 的两种详情页分数不一致

- 题目页：[Michigan August prelim](https://social-sim-arena-e2e-test.vercel.app/#question/umich-2026-08-prelim)。找到 Crowd 行，显示 `62.2 ± 12.0 / Error 11.2 / CRPS 5.52`：前轮题目表修复复测通过。
- 点击该行进入 [Crowd 单条预测详情](https://social-sim-arena-e2e-test.vercel.app/#forecast/umich-2026-08-prelim/crowd)。实际显示 `CRPS 6.70`，其余相同题号、参赛者与预测一致。
- 期望：两个页面均使用同一权威成绩 `5.523`，格式化为 `5.52`；不能在单条预测页把分位数预测退化为正态分布重算。
- 证据：实际浏览器 DOM 文本，题目行 `22 Crowd Aug 12, 07:00 AM 62.2 ± 12.0 11.2 5.52`；单条页 Error 卡 `11.2 / CRPS 6.70`。

### UI-02 · P1 · 已评分多维/排名题仍显示等待结算，成绩缺失

- [Google Trends 9/5 profile](https://social-sim-arena-e2e-test.vercel.app/#question/trends-basket-2026-09-05)：实际 `locked · answer expected Sep 5`、`no number forecasts`，表头 `Error / CRPS`，所有分数为点号。
- [Wikipedia 9/6 ranking](https://social-sim-arena-e2e-test.vercel.app/#question/wiki-top10-2026-09-06)：实际 `locked · answer expected Sep 8`、`no number forecasts`，表头 `Error / CRPS`，所有分数为点号。
- 线上 `/data.json` 已含 `profile.rounds` 的 Trends 9/5 GLM web+sfc `energy: 1.2464`、Trends 9/12 `energy: 2.4927`，以及 `ranking.rounds` 的 Wiki 9/6 Claude Opus web+sfc `loss: 0.806`。但主 `rounds` 中这三题仍是 `awaiting_resolution`。
- 期望：已结算题的主状态与权威成绩一致；profile 展示 Energy 和各维结果，ranking 展示对应排名损失及实际排名，不用标量 CRPS 列。问题包括数据状态同步与题型模板两个层面。
- [Civiqs 16-cell w37](https://social-sim-arena-e2e-test.vercel.app/#question/civiqs-profile-2026-w37) 同样套用标量模板；该题本次没有权威结算结果，不将空分数单独判错。

## 通过与覆盖边界

| 检查 | 实际结果 |
|---|---|
| Questions → Open → 搜索 Civiqs | 返回 Civiqs 开放题，包括16-cell题；截止时间、题型和来源链接可见 |
| 无匹配词 `zzqa-no-match` | 清晰显示 No matching questions，并建议调整过滤条件 |
| Questions → Enter the arena → Register an agent | 正常进入 submit.html；人类参赛入口保持 disabled |
| 注册表单未测试状态 | 填写普通测试字符串、HTTP URL 与非法 ID 后 Submit for review、Copy JSON 仍 disabled；未点击 Run test，所以本轮不声称验证了发送前的错误提示 |
| 手机 390×844 | 题目卡、状态筛选、注册说明可读可达；主文档宽度不超过视口，导航局部可横向滚动；仅一个代表性视口，不代表全设备验收 |
| 手机 profile 行点击 | Civiqs w38 Persistence 行可打开单条预测，16个细分组 mean/sd 表可读 |
| 手机测试清理 | 已恢复默认视口 |

## 建议回归验收

修复后应同时比对题目表、单条预测、任务榜的权威成绩；至少用 Crowd 分位数标量、已结算5-cell profile、已结算10-item ranking 三个固定历史样本。仅截图或单页渲染成功不能证明成绩一致。此报告不包含支付、外部写入、自动结算或免费模型可靠性验证。

## 修复记录 · 2026-09-16

UI-01 与 UI-02 已在分支 `fix-ui-lifecycle` 修复，回归测试 `tests/site/render_question.js`（由 `tests/test_site_render.py` 调用）同时比对题目页与单条预测页：

- UI-01：单条预测页改为读管线发布的 `r.scores[entrant].crps`，只有没有发布分数的非 Crowd 预测才用正态闭式回退。Crowd 在两个页面均为 `5.52`。
- UI-02：`ssa/refresh.py` 的 `attach_round_scores` 在把 profile / ranking 的分数写回题目时，同时把题目状态置为 `resolved`，并把结算结果放进 `resolution.outcome`（ranking 另有 `items`）。题目页按题型切换列头（Energy / Skill、Loss / Skill），显示已发布的 profile 向量或排名列表；单条预测页显示对应的 energy / loss 与 skill。
- 页面模板用 headless Chrome 对 `#question/wiki-top10-2026-09-06`、`#question/trends-basket-2026-09-05`、`#forecast/umich-2026-08-prelim/crowd`、`#forecast/wiki-top10-2026-09-06/claude-opus-5-web-superfc` 截图核对。

本 fork 不运行 `ssa.refresh`，所以提交的 `site/data.json` 里这两道题仍是 `awaiting_resolution`；状态修复在下一次真实 refresh 生成的 `data.json` 中生效。正式站有同样的缺陷（`refresh.py` 与上游一致），修复需要移植。
