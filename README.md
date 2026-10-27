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
