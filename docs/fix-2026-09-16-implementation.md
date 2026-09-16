# 实现文档 · 2026-09-16 修复批次

分支 `fix-ui-lifecycle`，提交 `d4e2df8c`，基于 fork `main`（`4b2b6f98`）。本地提交，未推送，未部署。

本批次修四个问题：两个正式站也存在的界面缺陷、一个测试生命周期的误报、一个会随日期变红的测试。不改任何评分规则，不改任何已发布的分数。

## 1. 已评分的 profile / ranking 题显示"等待结算"

### 现象

`#question/trends-basket-2026-09-05` 和 `#question/wiki-top10-2026-09-06` 显示 `locked · answer expected`，表头是 Error / CRPS，所有分数是点号。但 `data.json` 的 `profile.rounds` 和 `ranking.rounds` 里这两道题已经有每个参赛者的分数。正式站 `social-simulation-arena.com` 同样如此。

### 原因

题目状态由 `refresh.round_status` 推导，它只查 `resolutions/resolved.json` 里有没有这道题。数字题结算时会写进这个文件；profile 和 ranking 题不写，它们的结算结果是 `build_profile_leaderboard` / `build_ranking_leaderboard` 从归档序列现场算出来的。于是榜单有分，题目本身的状态永远停在 `awaiting_resolution`。

前端只有一套数字题模板，看到不是 resolved 就套上去。

### 改动

**后端** `ssa/refresh.py` · `attach_round_scores`

这个函数原本只做一件事：把榜单里每道题的每个参赛者分数复制到题目的 `scores` 字段。现在多做两件：

- 题目状态置为 `resolved`。
- 把榜单结算用的结果放进题目的 `resolution.outcome`：profile 是 `{cell: value}`，ranking 是有序列表。ranking 另外复制一份到 `resolution.items`，因为排名图表原本就读这个键。榜单记录的结算元数据（method、week_start 等）一并合入。

它在主流程里的位置是三个榜单都建好之后、`data` 组装之前，所以 `leaderboard.resolved_rounds` 的计数随之正确。没有分数的题不动，数字题不动。

**前端** `site/index.html`

新增 `roundKind(r)`：按 `target_type` 返回 `number` / `profile` / `ranking`。

`renderQuestion` 按 kind 分支：

| 位置 | number | profile | ranking |
|---|---|---|---|
| Released 卡片 | 数值 | `N cells` | `top N` |
| What the models say 卡片 | 中位数 | 说明是联合 profile，没有单一数字 | 最多列表排第一的标题 |
| 结果区 | 无 | 新增"The released profile"表 | 新增"The released list"有序列表 |
| 表头 | Error / CRPS | Energy / Skill | Loss / Skill |
| 排序 | CRPS 或误差 | energy 升序 | loss 升序 |

分数只读 `r.scores[entrant]`，前端不再为这两类题算任何分。

`renderForecast` 同样分支：Released 卡片和分数卡片按题型显示 energy 或 loss 加 skill；ranking 预测下方增加"The released list"，profile 预测下方增加"The released profile"（并列显示该参赛者每格的预测均值）。

### 测试

- `tests/test_round_scores_status.py`：给三道假题和两份榜单，断言 profile / ranking 题变 resolved、`resolution.outcome` 和 `scores` 正确、没分数的题不动、数字题不动、resolved 计数为 3。
- `tests/site/render_question.js`：用真实 `data.json` 跑 `index.html` 自己的脚本，渲染题目页和单条页，断言 ranking 题表头是 Loss、不含 CRPS、显示 released list、状态是 resolved；profile 题同理用 Energy；单条页显示对应 loss / energy。由 `tests/test_site_render.py` 新增的用例调用，进 CI 循环。

这个 JS 测试自己做一遍 `attach_round_scores` 的镜像，所以对旧快照的 `data.json` 也能跑，测的是模板不是数据。

## 2. Crowd 单条预测页分数与题目页不一致

### 现象

`#question/umich-2026-08-prelim` 的 Crowd 行显示 CRPS 5.52，点进 `#forecast/umich-2026-08-prelim/crowd` 显示 6.70。

### 原因

Crowd 预测是所有参赛者的分位数混合，不是正态分布。管线用经验 CRPS 给它打分，结果存在题目的 `scores.crowd.crps`。题目页在提交 `26a33a1c` 已改为读这个值；单条页还在拿显示用的均值和标准差当正态分布重算。

### 改动

`renderForecast` 改成和题目页一样的规则：有发布分数就用发布分数；没有的话，Crowd 不算，其他预测才用正态闭式回退。

### 测试

`tests/site/render_question.js` 里找一道已结算、Crowd 有发布分数的数字题，断言题目页 Crowd 行和单条页都显示同一个两位小数。

## 3. 生命周期测试每天 00:43 撞 404

### 现象

Wikimedia 的每日 top 列表在 UTC 当天结束后几小时才出来。2026-09-16 01:12 UTC 实测，09-15 的列表仍是 404。`qa-lifecycle.yml` 每天 00:43 运行，会去抓前一天，从 9/22 目标周开始每天这次运行会把待结算的题标成 `blocked`、运行变红、页面显示 6 小时。

### 改动

`tools/qa_lifecycle.py`

- 新增异常类 `NotYetPublished`。`main` 里的抓取函数遇到 404 抛它，其他状态码行为不变。
- `execute` 在"结果未发布、逐日归档目标周"的循环里捕获它：记录 `target_day_waiting`，停止本轮归档（后面的天也不会有），题目保持 `pending`。
- 结算路径（`week()`）不捕获，所以到了结果发布时间还缺天仍然是 `blocked`，不会凭空结算。

### 测试

`tests/test_qa_lifecycle.py` 新增用例：9/24 00:43 抓 9/23 遇 404，题目仍 pending、已归档 2 天、记录等待日、9/23 文件不存在；9/24 06:43 再跑归档到 3 天、等待标记消失；9/29 结算成功。另起一个目录，结算时所有天都 404，断言 `blocked` 且原因含 `NotYetPublished`。

## 4. 发布器测试读真实日期

`tools/publish_qa_results.py` 在 2026-10-01 UTC 之后拒绝写入，`tests/test_qa_publish.py` 原本用真实时钟调它，到那天会红。

`publish(channel, root, now=None)` 加了时钟参数；测试传固定的 9/20；新增用例断言 10/1 之后不发任何 API 调用。

## 验证

```sh
# 全部 Python 套件（CI 循环的做法）
for t in tests/test_*.py; do PYTHONPATH=. .local/venv/bin/python "$t" >/dev/null 2>&1 || echo "RED $t"; done
# 结果：67 通过；红的 4 个（test_contract_consistency、test_landing_audit、test_reliability、test_workflows）改动前就红，原因是 fork 把 refresh.yml 改名为 .disabled

.local/venv/bin/python -m unittest tests.test_qa_lifecycle tests.test_qa_publish tests.test_qa_contract_fixes tests.test_qa_api_scoring
node tests/site/render_question.js            # 对提交的 data.json
node tests/site/render_question.js <patched>  # 对用新代码重算过的 data.json
```

页面用 headless Chrome 截图核对（本地起 `python3 -m http.server`，`data.json` 用新 `attach_round_scores` 重算过的副本）：

- `#question/trends-basket-2026-09-05`：resolved，5 格 released profile 表，Energy / Skill 列，25 行有分
- `#question/wiki-top10-2026-09-06`：resolved，released list 十项，Loss / Skill 列，24 行有分
- `#forecast/umich-2026-08-prelim/crowd`：CRPS 5.52
- `#forecast/wiki-top10-2026-09-06/claude-opus-5-web-superfc`：Loss 0.806、skill 0.15、预测列表与 released list 并列

注意：截图时本机 8765 端口已有别的服务在跑，第一批截图拍到的是那个服务，换端口后才对。

## 改动文件

```
docs/qa-ui.md                     +10   修复记录
site/index.html                   +48 -11 roundKind、renderQuestion、renderForecast
ssa/refresh.py                    +23   attach_round_scores
tests/site/render_question.js     +114  新
tests/test_qa_lifecycle.py        +33
tests/test_qa_publish.py          +12
tests/test_round_scores_status.py +80   新
tests/test_site_render.py         +23
tools/publish_qa_results.py       +4
tools/qa_lifecycle.py             +21
```

## 部署与移植

**fork 部署**：`vercel deploy --prod --yes --scope yangs-projects-36e22525`，在仓库根目录。fork 不运行 `ssa.refresh`，提交的 `site/data.json` 是旧快照，其中两道题仍是 awaiting；部署后要看到状态修复，要么用新代码重算这份快照再提交，要么等真实 refresh。Crowd 修复和模板修复部署后立即生效。

**移植到正式仓库**：正式站有同样的两个缺陷（`refresh.py` 和 `index.html` 在这两处与上游一致）。要移植的是 `ssa/refresh.py` 的 `attach_round_scores`、`site/index.html` 的三处改动、以及 `tests/test_round_scores_status.py`、`tests/site/render_question.js`、`tests/test_site_render.py` 的新用例。第 3、4 项只属于 fork 的 QA 工具，不移植。正式站跑 refresh，所以那边合并后下一次刷新状态就对。PR 目标是上游 `dev`。

## 未做

- 后端冷缓存并发不幂等：需要引入原子锁，决定不修，文档已说明。
- `season0.json` 里 Civiqs 题的"人工截图"文案：与实际规则不符，纯文案，用户决定不改。
