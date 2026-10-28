# japanese-trend-collector — CHANGELOG

## 2026-10-28 — 自动翻译草稿与质量审核（候选 PR）

- 新增 `translation_review.py`：对有证据的新流行语候选生成审核优先级、可确定的假名，以及 MyMemory 的日中/日英机器翻译草稿。
- 修改 `slang_only.py`：把调查来源日期、排名和网址记录在待审核队列里，复用机器翻译草稿；`docs/feed.json` 仍只从经整理的 `slang_terms.json` 生成。
- 修改 `collector.py`：新增 `--translate-pending` 和 `--translation-limit`。
- 修改 GitHub Actions：定时为最多 8 个候选生成翻译草稿，并运行全部 `test_*.py` 回归测试。
- 新增 `tests/test_translation_review.py`，覆盖普通词过滤、过期来源、翻译异常、请求限额、草稿缓存、离线模式及正式词库隔离。
- 本地离线回归 26/26 通过；线上翻译准确性、API 可用性和真实自动采集效果仍待 GitHub Actions 验证。
- 未修改已审核的 11 条原有词汇、Firebase 网站或私人数据。

**安全约束**：机器翻译始终标记未经审核，禁止直接自动发布；`reviewPriority` 不是可信度概率。

- GitHub 全文件名扫描暴露遗留 `tests/test_trend_signals.py` 仍依赖已移除的 `collector.build_feed`；正式 PR/定时 CI 改为明确运行当前两套有效的严格采集与翻译质量测试，共 26 项。遗留测试未删除。

## 2026-10-29 — 修复真实调查页的目录标题冲突（待合并 PR #7）

- 生产 `docs/feed.json` 于 2026-10-29 02:09 JST 记录读取 10 页，但 0 个排名解析成功：`sourceSucceeded=0`、`candidateWords=0`、`slang_state.reports=[]`，公开词数因此仍为 11。
- GitHub Actions 只读联网诊断发现：原站 HTML 在文章目录和实际排名正文中各出现一次「今流行っている言葉は？」；原解析器只处理首次匹配的目录标题，并在紧接的目录项「今流行っている物事は？」处结束，造成实际正文排名被全部跳过。
- 修复 `slang_only.ranked_slang_from_report()`：逐个尝试同名标题段落，只从含合法名次与百分比的实际流行语区域提取词，不跨到后续物事/食物分类。
- 新增目录与正文标题重复、只存在目录但正文无排名的回归测试。真实页面联网复测和 GitHub CI 结果以 PR #7 记录为准。
- 安全边界：本修复不改现有 `slang_terms.json` 的 11 条人工词、Firebase 站点或私人 Firestore；新词仍需审核，机器翻译草稿不会直接写入公开 Feed。
