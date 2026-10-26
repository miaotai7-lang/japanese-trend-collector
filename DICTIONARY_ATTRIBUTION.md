# 公开日中英词汇数据的出处及许可

本项目公开采集 RSS **标题**（不抓取正文），并将合格词条和各自标题来源链接汇总。日语到中英文释义属于参考词典候选，不是语境核对过的官方翻译。

## 日英辞典（EDRDG）

© Electronic Dictionary Research and Development Group，EDICT2u（源于 JMdict）。来源：<https://www.edrdg.org/pub/Nihongo/>；许可：<https://www.edrdg.org/edrdg/licence.html>。按照上游许可进行署名、遵守相同方式共享等要求。请同时访问上游站查看完整版、更新的词汇资料。对数据处理所作的修改：只按日文原形筛选并提取有限首义，未复制整部词典至公开仓库。

## 日中辞典

来源：<https://github.com/lxl66566/Japanese-Chinese-thesaurus>，The Unlicense。对其中日文原形相匹配的条目提取中文释义候选，过滤明显属于课文语法说明等长文本。

## 衍生数据许可

`docs/feed.json` 中的参考释义和映射以 **CC BY-SA 4.0** 方式提供（受 EDRDG 上游许可条件约束），具体出处也包含在每条数据的 `translationSources` 字段内。请勿将“词典候选”视为经过人工核对的语境译法。自动采集程序本身的代码独立于参考词典数据。

参考：<https://creativecommons.org/licenses/by-sa/4.0/>
