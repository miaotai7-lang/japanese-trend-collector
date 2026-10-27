# Japanese Trends / 日本网络流行表达与标题高频词（V8.5.3）

本仓库与 Firebase 个人专业词库分离。GitHub Actions 定时抓取可公开访问的 RSS 标题，更新 `docs/state.json` 与 `docs/feed.json`，通过 GitHub Pages 发布。无需 Firebase 服务端私钥。

## 最重要的更正

2026-10-26 之前的 484 条全部是标题高频词，**并没有合格的网络流行语**。V8.5.3 严格区分：

- `kinds:["trend"]` + `trendVerified:true` + `trendCurrent:true`：**近 180 天有调查／研究出处的网络流行语**，附日期、来源、中文、英文、假名与用法提醒；资料存于 `data/verified_slang.json`。
- `kinds:["freq"]`：新闻／社区 RSS **标题高频词**，是词典候选而不是网络流行语。
- `topics`：Google Trends 搜索查询话题（并非网络流行语），作为独立元数据保留。
- `slangReviewQueue`：从与“若者言葉／流行語／ネットスラング”相关 RSS 标题发现的**待审核候选**，仅保存在 `docs/state.json`，没有可靠含义不发布，不编造翻译。

研究排名指该份调查的排名，不是日本全网排名。中文及英文是释义整理，不是来源机构的官方翻译。过期趋势保留为历史资料但不再作为“最新”。

## 后续自行补充经过核实的流行语

修改 `data/verified_slang.json` 的 `items`：每条必须包含 `jp`、`kana`、`zh`、`en`、`category`、`date`、`publisher`、`source`；`rank` 可为 0；`note` 解释语境。必须引用确实报道了该表达的 HTTPS 原始或可靠出处。避免仅从热门新闻标题猜测译义。更新后创建 Pull Request，运行 `python -m unittest discover -s tests -v`，再合并到 `main` 并手动运行采集任务。

详细标准与来源：`docs/TRENDS_POLICY.md`。

## 初次或手动运行

GitHub Pages：`Settings → Pages → Source: GitHub Actions`。
GitHub Actions：`Collect Japanese Trends and Publish Feed → Run workflow → main`。
采集计划：每天日本时间 08:15、20:15，平台可能延迟。GitHub Pages JSON：`https://miaotai7-lang.github.io/japanese-trend-collector/feed.json`。

本项目保留已成功的 Firebase 网站地址和 GitHub 仓库，**不需要重新初始化仓库**。V8.5.3 Windows 脚本从已有 GitHub `main` 克隆到临时英文路径后创建独立测试分支，避免中文路径或误输旧项目路径。

## 离线测试

```sh
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

采集完成后检查 `counts.currentSlang`, `counts.reviewQueue`, `items[].trendCurrent` 和来源日期；不要把 `counts.words` 当成所有流行语数量。
