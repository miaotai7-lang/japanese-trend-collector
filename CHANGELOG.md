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

- **真实联网验证补录**：GitHub Actions 只读实测同一篇 `/monthlytrendsurvey/4622/` 调查网页，修复前 `extracted=[]`，修复后从正确的正文区域提取 **9 条合法排名**，其中含 `メロい`、`ドパガキ`、`ネ申`、`冷笑`、`アツい`；两套离线测试分别为 15/15、13/13。暂存诊断步骤已移除，避免每次 PR 依赖实时网络源。提取排名不等于新词自动审核发布。

## 2026-10-30 — 修复长期无新词的正式发布链路

- **根因（线上证据）**：2026-10-30 02:25 JST 的 `docs/feed.json` 显示 3 份调查成功解析、30 条排名记录、4 条待审候选、0 条自动发布。实际 MyMemory 草稿中 `アツい` 被翻成“热”、`ネ申` 被误译为 `Neshen`，不能不经审校入库。
- `slang_only.py` 新增逐词证据核对的自动发布门槛，不允许机器翻译草稿直接进入 Feed。
- `data/reviewed_auto_publish.json` 新增独立审核且带词义引用的 `ネ申`（かみ，神级）和 `滅`（めつ，表达情绪爆棚）以检验从真实排名到发布的完整链路。查询凭证/用户数据均不涉及。
- 修复单字 `滅` 原先被所有长度过滤条件误排的问题，但不开放其他普通单字。
- GitHub Actions 增加主分支采集文件变更时即时发布、无有效排名时失败阻断、对新增正式条目的自动化回归测试。
- 没有修改 Firebase 主网站的 `public/`、Firestore 数据或 `slang_terms.json` 的原 11 条历史词。最终发布数量及实际 Pages 展示须以合并后 Actions 运行结果为准。

## 2026-10-30 — GitHub Pages 公网发布验收

- 给定时/代码合并触发的发布工作流追加 GitHub Pages 公网读取校验：部署后带随机查询参数读公开 `feed.json`，必须与刚生成的本地文件的 `generatedAt`、全部词条 `(id,jp)` 与词数完全一致。
- 允许 CDN 生效延迟，最多 12 次重试；如网络失败或继续返回旧版，工作流将明确失败，不再仅凭推送 GitHub 仓库成功就声称网站已更新。
- 本修改不改实际词库、采集器选择逻辑、Firebase、Firestore 或原有 PWA。

## 2026-10-30 — 多平台公开社区流行语候选采集（PR 阶段）

- 新增 `community_sources.py`：Hatena Bookmark 标签及标题关键词 RSS 和 Mastodon 公开标签 RSS，支持 RSS1/2/Atom、来源发布日期、显式引号与流行语语境提取、35 天过期、最多 100 个候选、每词最多 6 条证据。
- `slang_only.py` 将公开社区发现结果与原有调查候选去重合并，增加来源统计；维持原有编辑审核词库、自动发布资格和 ID 不变。
- `translation_review.py` 将单独一条社交证据保留待确认，不直接翻译和入库。
- 定时采集工作流添加模块变更触发与单元测试；PR 检查增加四个公开 RSS 源的只读连通性诊断。
- 独立新测试涵盖来源 XML、不可信链接/日期、普通词过滤、重复、失败保护和正式 Feed 不变；真实 GitHub Runner 结果见 PR CI。
- 不抓取登录后/私有内容，不引入第三方访问密钥，不触碰 Firebase 网站或原有词库。

- 真实 GitHub Actions 只读源测：Hatena 标题流行语搜索近期 1+3 条、8 次明确提及；Mastodon 日语话题近期 20 条、严格词义规则下 0 候选。为避免在低活跃标签上空转，来源扩展为 6 个固定公开 RSS，区分可读但暂无近期内容与确有近期内容，并拒绝非 HTTPS 重定向。四套回归测试共 48 项通过；线上正式候选结果以合并后数据为准。

## 2026-10-30 — 社区采集噪声防护修复

- 首次真实多来源采集记录了 6 个社区线索，且当前全部只来自单独公开页面；审查发现「行った」「プログラマーの脳みそ」等不可靠短语，不能视为网络流行语。
- `community_sources.extract_claimed_slang` 对 Hatena 只从相关文章标题抽取引号词，避免文章摘要中的无关引用造成污染；Mastodon 仍从公开帖子文本抽取。
- 单篇社区帖子只保存到独立 `docs/community_state.json` 作为弱线索；至少出现两个不同公开来源 URL，或与原有真实调查候选合并时才进入 `docs/slang_pending.json` 的审核队列。无论多少帖子都不能直接进入正式 Feed。
- 添加 `counts.communitySignals`（未经确认的所有线索）与 `counts.communityHeldForCorroboration`（未达独立证据门槛）以区分“发现线索”和“可供审核的候选”。
