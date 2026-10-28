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
