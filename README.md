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
- 生产 GitHub Actions 将通过 `python collector.py --root docs --translate-pending --translation-limit 8` 执行。手动离线检查用 `--no-network` 禁用翻译请求。新测试命令为 `python -m unittest discover -s tests -p 'test_*.py' -v`。
- **尚待验证**：GitHub Actions 访问 MyMemory 的成功率、调用限制、真实日语网络语义准确度。即便中日英字形和长度检查通过，也不能判定翻译准确。

该模块实现自动形成**翻译草稿＋自动初筛＋待审队列**，尚不是无人值守直接发布新词的最终系统。高可信自动发布机制必须在建立独立来源、译文交叉核验与审校基准后另外评估。
