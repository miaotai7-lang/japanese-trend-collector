# 日本最新网络流行语｜V8.5.3（只收录网络梗与流行语）

此 GitHub 仓库 **只负责自动更新公开数据**，与原有 Firebase 建筑专业词典、Firestore 私人数据完全隔离。

## 本次重点变化

- **取消**从普通新闻标题、はてな热榜及 Google 搜索热词的日语分词中自动提取「高频词」。它们测量新闻话题，而不是网络流行语。
- 仅关注注明「今流行っている言葉」「若者言葉」「ネットスラング」的真实调查及相关专题。
- 公开 `docs/feed.json` **只显示有具体来源、假名、中文、英文的已整理网络表达**。任何无意义普通词，包括「情報／会社／見る／食べる／アクセス」都不会进入正式词库。
- 每次采集自动尝试查找最新调查，识别排名中的新候选，保存至 `docs/slang_pending.json` 供后续核对；不提供可信中英文的未知新词**不会自动发布**。
- 词条依来源**发布日期**确定新鲜度，而不是 Github Actions 的执行日期；超过120天且没有新的来源支持时自动退出当前列表。
- 旧 `docs/state.json`（普通新闻词频归档）不再读取；正式运行时删除旧文件，但保留新的 `slang_state.json` 作为来源监测记录。

## 为什么不能保证“全自动新增任意网络梗”

流行语通常是语境梗、谐音、文字游戏。普通日中、日英词典无法准确翻译这些表达。为了避免旧版「いい＝你问」「れる＝a cable」之类的错误，程序自动发现新词，但**只有补齐可靠的假名、中文、英文并核对出处后才发布**。这一机制宁可减少数量，也不造假。维护者可在 `slang_terms.json` 中增补经过核对的词条并提交。后台继续每天自动扫描、更新报告证据和过期状态。

## 采集来源与更新计划

当前来源：渋谷トレンドリサーチ近期高校生流行语调查及其公开 RSS，另有特定词汇的 Impress Watch／FOMO²／朝日コネクト报道作为阅读参考。以上来源不等于全日本人群流行度的代表样本。

运行计划：日本时间每天08:15及20:15（GitHub Actions 可能延迟）；可以手动 Run workflow。

## 更新仓库与网站

1. 在Windows上下载 **V8.5.3 GitHub 修复包**，解压后运行 `RUN_UPLOAD_V853.cmd`；它会重新 `git clone` 仓库到一个新的纯英文文件夹 `Downloads\japanwords-v853`，并建立安全测试分支 `fix/v8-5-3-slang-only`，不会直接更改 `main`。
2. 浏览器自动打开 GitHub Pull Request 页面。选择 Create pull request，确认 `Validate genuine internet slang only` 测试通过后，再点击 Merge pull request → Confirm merge。
3. GitHub Actions → `Collect Japanese Trends and Publish Feed` → Run workflow（main）。成功时 `docs/feed.json` 会更新为 `feedType: japanese-internet-slang-only`。`docs/slang_pending.json` 仅供人工审核。
4. **之后**部署独立的 **V8.5.3 Firebase 网站包**，更新网页的流行语栏目文案与旧数据缓存。原网址、Firestore、建筑专业词库、收藏、背诵、朗读不变。

数据地址：
`https://miaotai7-lang.github.io/japanese-trend-collector/feed.json`

## 本地测试

```bash
python -m unittest discover -s tests -p 'test_slang_only.py' -v
python collector.py --root docs --no-network
```

以上第二条会生成**离线的已整理词条预览**，不能证明当天网络调查抓取成功。真正网络抓取需以 GitHub Actions 采集日志和 `docs/feed.json` 为准。

## 数据来源标注

每条学习词保留 `sources[]` 参考链接、日期和出处。中文和英文是依报道语境整理的**学习释义，不是官方逐字翻译**。对于歧义或可能冒犯的表达，请结合原文使用。不要把第三方报道大段转载进公开词库。


## 候选修复：流行语调查自动发现与解析（2026-10-28）

> 2026-10-28 自动发现修复已通过 PR #5 合并；真实定时采集的结果仍需另行核查。

- 同时读取流行语调查索引与官方 RSS，降低单一 RSS 不可用导致持续重复旧报告的风险。
- 识别无空格排名行（如 `1位メロい(20.3%)`）及全角括号/百分号，限定于原出版者的“今流行っている言葉”排名区域。
- 区分网页读取成功与实际排名解析成功；若无法识别排名，在 `docs/feed.json` 的 `sourceStatus` 记录解析失败，不再误报来源成功。
- 离线回归测试增加至 13 项，涵盖索引发现、网页排版、解析失败和未审候选词隔离。
- **新词不会直接公开**：自动发现仅进入 `docs/slang_pending.json`；人工审核假名、中文、英文、出处之后才纳入 `slang_terms.json`。这次没有引入机器生成的假释义。
- 单一调查网站并不能覆盖全部日本网络流行语，实际采集范围、来源日期与排名格式仍需在真实 GitHub Actions 环境确认，之后再逐步扩展可信来源。

## 自动翻译候选与质量审核模块（候选，2026-10-28）

**核心边界**：自动翻译提供待审核草稿，绝不能当作网络流行语的准确释义；正式 `docs/feed.json` 仍只消费经过整理的 `slang_terms.json`，并非从草稿直接构建。

- `translation_review.py` 结合近期调查的真实日期、排名、来源、日文文本和普通词黑名单，对候选给出审核优先级。`reviewPriority` 不是翻译准确率，也不保证一定是网络流行语。
- 仅将可确定的片假名转换成平假名；含汉字、存在歧义的读音不作自动猜测。
- 对符合基础审核条件的**公开候选词**，通过 MyMemory 公共翻译接口生成 `ja→zh-CN` 和 `ja→en` 机器草稿，写入 `docs/slang_pending.json` 的 `translationDraft`，附 `verified=false` 和 `approvedForPublication=false`。失败或不完整翻译保留待审核状态，不阻断正式词库。
- 每次定时执行最多处理 8 个尚无有效草稿的新候选（最多 16 次翻译请求），完整草稿最长复用 14 天，部分草稿短期复用；避免重复调用和意外耗尽免费接口配额。
- **隐私与公开范围**：翻译请求仅包含已经从公开调查取得的词条字符串，不上传任何 Firebase 用户信息；`docs/slang_pending.json` 本身通过 GitHub Pages 可公开访问，请勿放入密钥、个人记录或第三方长篇版权内容。
- 生产 GitHub Actions 将通过 `python collector.py --root docs --translate-pending --translation-limit 8` 执行。手动离线检查用 `--no-network` 禁用翻译请求。回归测试依次运行 `python -m unittest discover -s tests -p 'test_slang_only.py' -v` 和 `python -m unittest discover -s tests -p 'test_translation_review.py' -v`。旧版 `tests/test_trend_signals.py` 依赖已经废弃的 `collector.build_feed` 接口，暂不纳入当前发布门槛，保留历史文件以供后续清理。
- **尚待验证**：GitHub Actions 访问 MyMemory 的成功率、调用限制、真实日语网络语义准确度。即便中日英字形和长度检查通过，也不能判定翻译准确。

该模块实现自动形成**翻译草稿＋自动初筛＋待审队列**，尚不是无人值守直接发布新词的最终系统。高可信自动发布机制必须在建立独立来源、译文交叉核验与审校基准后另外评估。

## 2026-10-30：有证据的自动更新与真实发布链路

此次修复针对“发现了 4 条候选、机器翻译也生成了，但网站长期只显示 11 条”的真正阻塞：此前公开 `feed.json` 仅从固定 `slang_terms.json` 生成，发现/翻译流水线与正式发布完全断开。

- 新增 `data/reviewed_auto_publish.json` **独立已核实释义表**：仅包含独立对照专业词典/日语来源核对过的 `jp/kana/zh/en`；初始条目 `ネ申`、`滅`，语义来源与排名来源分别保存。**这里绝不自动导入 MyMemory 草稿**。
- `slang_only.reviewed_auto_terms()` 在每次采集时对照最新有效调查记录：只有词形与原始调查排名完全匹配、来源 URL/发布日期一致、在 120 天窗口内、且具备两份语言依据，才会自动进入公开 Feed；过期或来源失效时失去新增资格。单字词只允许已核实的 `滅`，普通单字不放开。
- 正式 Feed 保留既有 `schemaVersion=1`、`feedType` 和原始词条 ID，增设 `counts.autoPublishedReviewed` 与 `counts.reviewedCatalog` 便于核查。其他机器候选仍留在 `docs/slang_pending.json`。
- GitHub Actions 除每日约 08:15 / 20:15（日本时间）外，今后相关采集器/审核词表被合并进 `main` 时会自动触发；GitHub 自动生成的 `docs/` 提交不触发循环发布。
- 工作流新增严格验收：如果联网读取虽成功却未解析出任何有排名的流行语，**运行失败、不提交新的 Feed、更不冒充更新成功**。
- 测试：`python -m unittest discover -s tests -p 'test_auto_publish.py' -v`。新增检查真实文章的目录/正文格式、单字白名单、已核对词自动发布、自动新增后旧 ID 不变、过期/错源阻断、未审核词禁止公开。

**重要边界**：此模式实现“针对已核实语义的网络表达，自动按最新真实证据收录”。它不能无条件让任意新造网络梗生成准确的中英解释；未经审核的陌生词仍待审核。要做到更广泛的零人工新词审核，需要额外的独立权威语义数据源和跨语种一致性门槛，不能直接依赖免费机器翻译。

## 2026-10-30 社区来源候选采集（PR 阶段，真实效果待验收）

新增 `community_sources.py`，在原来的渋谷トレンドリサーチ**调查采集之外**尝试从两个公开社交/社区渠道发现日本流行语：

- はてなブックマーク（Hatena Bookmark）搜索标签 `ネットスラング`、`若者言葉` 的 RSS（平台官方公开 RSS 搜索格式）。
- Mastodon 公共话题 `#ネットスラング`、`#流行語` 的 RSS（Mastodon 官方提供标签 RSS 的能力；实际服务器可用性需测试）。
- 每次最多请求 4 个固定来源，每个来源只读取最多 35 篇近期记录；只识别明确与“网络用语、流行语、梗”等语境直接关联、带引号的候选，不从普通新闻标题随意分词。
- 只保存**候选词、公开原帖链接、发布日期及来源类型**到 `docs/community_state.json`；不保存帖子全文、作者、评论者、头像或个人记录。35 天到期、去重、总数限制 100 词；失败的来源会在 `sourceStatus` 记录，不会破坏正式调查模块。
- 与 `docs/slang_pending.json` 合并供审核，并在 `feed.json` 的计数中增加 `communityCandidateWords` 和 `communitySourceSucceeded`，但 **不会直接进入正式词库**。仅一篇社区帖子提到的词暂不调用翻译服务；两篇以上也只是机器翻译草稿，不会自动“审核通过”。
- 正式 `docs/feed.json` 仍只来自原有人工词典和经过独立核实的 `data/reviewed_auto_publish.json`；用户现有 13 条词、Firebase 登录/学习数据及 PWA 不改。
- 新增 `tests/test_community_sources.py`，回归 RSS 1.0/RSS 2.0/Atom 格式、来源过期、证据去重、黑名单、链接安全、正式词库隔离。PR 中还进行了真实 GitHub Runner 来源连通性探测，最终以日志为准。

**来源限制**：Reddit 官方宣布 2026-11-13 将停用 RSS，故不把将停止的 RSS 作为新采集基础；X/TikTok/Instagram/YouTube 评论、5ch 等尚未接入，后续需按平台正式接口、授权及访问条款分别处理。当前社区信号主要用于*发现候选*，不是独立事实核查，也不代表全部日本人的流行程度。
