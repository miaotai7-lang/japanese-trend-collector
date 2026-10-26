# 日本网络流行语・高频词库 — 自动采集后端

这份后端**独立于**原有 Firebase 建筑日语网站。它仅读取所列**公开 RSS feed**里的标题及链接，对日语词进行统计，并将 `docs/feed.json` 发布到 GitHub Pages。绝不登录论坛、绕过反爬验证、抓取帖子全文或修改私人 Firebase 数据。

## 采集与频率范围

- **搜索热词／话题**：Google Trends 日本 RSS（若当前可以访问）；记录的是「查询话题」，不等同于常用词。
- **标题高频词**：はてなブックマーク开放 RSS 的综合、科技、生活、娱乐榜，另包括 Yahoo! 新闻经济 RSS。使用 Janome 进行基础日语切词和假名候选。
- 采样指标 `last7` 是本系统**最近 7 天抓到的去重 RSS 标题出现次数**，不是全日本网络词频。首次运行没有历史对照，真正的趋势变化需要几次采集后才有意义。
- 个人/网站作者的 RSS 来源可能修改、停止服务或限流。单一来源失败不会删除已收集词汇；全部来源失败会直接报错并保留上一次发布的数据。
- 最多公开展示约 800 个词；保留最近 45 天的累计样本。
- 假名是自动形态素分析候选，中文与英文是通过 MyMemory 获取的**机器翻译候选，未经逐条核实**。每次至多为 8 个缺译词请求翻译，失败保留为空。不能把这些候选当成官方专业术语翻译。

## 不用打开网站也自动运行的启用流程

1. 登录 GitHub，创建一个**新的空白公开仓库**，建议名称 `japan-word-feed`（注意不要创建 README、.gitignore 或 license，以免和本目录初始化冲突）。
2. 在 Windows 安装 [Git for Windows](https://git-scm.com/download/win)。解压后，进入**本 `trend-collector` 文件夹**，双击 `初始化GitHub自动词库_Windows.bat`，输入新仓库的 `https://github.com/USERNAME/japan-word-feed.git`，确认上传。若不使用脚本，也可把本目录的所有文件（包括 `.github` 隐藏目录）提交到仓库的 `main` 分支。
3. 仓库 Settings → Pages → **Build and deployment → Source: GitHub Actions**。无需任何 Firebase 私钥。
4. 仓库 Actions → 选择 **Collect Japanese Trends and Publish Feed** → `Run workflow`。首次运行下载日语分词库、读取公开 RSS，完成后在工作流的 `github-pages` 部署步骤显示公开网址。
5. 找到 `https://USERNAME.github.io/japan-word-feed/feed.json`（替换为你的账户和仓库名），先在浏览器中打开，确认 `generatedAt` 是真实时间且 `items` 不为空。
6. 解压并部署主网站 V8.5，然后在「日本网络新词」模块 →「连接 GitHub 自动采集源」填入以上**完整 feed.json 地址**并点击「保存地址并连接」。手机与电脑目前需各保存一次源地址。

### 自动时间

GitHub Actions 计划在**日本时间每天 08:15、20:15**采集（UTC `15 23,11 * * *`）；可能排队、延迟甚至跳过一次。也可随时在 GitHub → Actions 手动触发。

### 数据和安全边界

- 使用 GitHub 免费公共仓库＋GitHub Pages；Firebase 原项目继续停留在 Spark，不需要 Blaze。
- GitHub 定时程序只更新自己的 `docs/` 数据和 GitHub Pages，**不会自动部署、覆盖或更改 Firebase Hosting 网站**。
- 采集的数据是公开的；`docs/state.json` 也会公开，不能存个人信息、账号密码或密钥。
- 词条的本机关注标记保存在当前设备的浏览器 localStorage。点击「加入我的词典」只是将候选带入原有编辑器，**需要你人工确认并保存**才进入 Firebase 私人术语库。
- 若要禁用外部翻译请求，在工作流中将 `python collector.py --root docs` 改为 `python collector.py --root docs --no-translation`。
- GitHub 账户和 Actions 设置因平台政策、配额和权限可能发生变化。遇到部署被拒绝，检查仓库 Actions permissions (`Read and write permissions`) 与 Pages 的 GitHub Actions 来源设置。

## 测试

无需联网的测试：`python -m unittest discover -s tests -v`。

本地手动采集（已安装 Python 3.12 和 `pip install -r requirements.txt`）：

```bash
python collector.py --root docs
```

容器或开发环境若无法访问外部网络，不能当作真实采集成功；`docs/feed.json` 初始模板不含任何伪造的“当前热门词”。
