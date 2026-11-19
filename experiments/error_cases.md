# 错误案例分析（人工撰写）

数据来源：`data/reviews.csv` 中 split=test 的 200 条样本；
逐条预测见 `experiments/predictions_test.csv`，自动汇总见 `experiments/error_cases_auto.md`。

## 总体情况

- 测试集 200 条（负面 100 / 正面 100）
- TF-IDF + 逻辑回归：Accuracy 0.8150，Macro-F1 0.8150
- DistilBERT SST-2：Accuracy 0.9150，Macro-F1 0.9150
- 两模型一致率 0.8100
- **两个模型都判错：8 条**；**两个模型意见不一致：38 条**

下面按类型挑选 7 条分析。所有引文都是样本原文的开头部分，完整原文可用样本 ID 在影评资料库页面检索。

## 案例一：反讽表达被当作真心夸赞（test-003788）

真实标签：负面。TF-IDF 判正面，DistilBERT 判正面。

原文开头：

> Minor spoilers First I must say how rare and charming it is to find a movie with such basic messages in it: nuclear war will inevitably destroy all of civilization, and women are for making babies. It is absolutely incredible how well formulated the plot is to hit in these two points, as with a golden hammer.

**原因分析**：这是典型的反讽。作者通篇使用褒义词（rare、charming、incredible、well formulated），但实际意思是嘲讽：把"核战毁灭文明"和"女人负责生孩子"称为"基本信息"，再用"像用金锤子砸"形容剧本的生硬。两个模型都只看到褒义词的密度，没有把它和后面的 `everything about this movie annoyed me` 组合起来判断。

**类型**：反讽 / 情感极性反转。

## 案例二：以剧情复述为主，负面情绪靠语气暗示（test-002958）

真实标签：负面。两个模型都判正面。

原文开头：

> This film is about a party put together by the high school "scary girl." Per the illogic of these sorts of films, she gets permission to hold the party at a house which used to be a crematorium, a dubious place long shut down and locked up.

**原因分析**：这条影评大部分篇幅在复述剧情，真正的态度分散在 `illogic`、`dubious` 这类带贬义的形容词里，还有 `I like these kill-kill-kill films ... as long as there is something in them not copied from a hundred other films` 这种"先让步再否定"的句式。模型看到的正面词（like、highlights）比负面词更显眼，于是判成正面。

**类型**：间接表达 / 让步句式。

## 案例三：混合评价，数据集标签来自用户评分而非文本（test-016153）

真实标签：正面。两个模型都判负面。

原文开头：

> The animation quality here is decidedly below par IMO, regardless of the age of the OAV. The plot itself makes sense, but the characters don't. ... Seems sloppy to me. ... Little light is shed on the backstory at all, a great pity.

**原因分析**：这条影评的文本几乎全是批评（below par、sloppy、a great pity），但 IMDB 的标签来自用户打分，该用户给了正分。也就是说**标签与文本倾向并不总是一致**。两个模型都按文本判负面，从文本角度其实是"合理"的，错在标签本身。

**类型**：混合评价 / 标签噪声。

## 案例四：重复粘贴的无效文本（test-023647）

真实标签：正面。两个模型都判负面。

原文（完整）：

> black tar can't be snorted there's a documentary: dark end of the street about s.f. street punks and b.t. abuse - not bad - quite heavy. in wasted there's this stuff that looks like coke but should be something else... no big deal.

同一段文字在样本里重复了三遍，通篇在对比两部影片里的毒品描写，没有对影片本身的评价，其中的 `not bad` 是唯一的准情感表达。

**原因分析**：这类文本本身几乎没有可用的情感信息，模型只能抓住 `can't`、`no big deal` 之类的否定词判负面。属于数据质量问题，不是模型能力问题。

**类型**：数据噪声 / 无情感内容。

## 案例五：反讽赞美混在大量对比里（test-008504）

真实标签：负面。两个模型都判正面。430 词。

原文开头：

> This film is strictly for fans of Debbie Reynolds and Eddie Fisher. I get angry at TCM for showing this mess more frequently than Bachelor Mother, the delightful original. ... Instead, Hollywood could have spent the time, money, energy and talent wasted on this horrible remake to give us something new and original - Wow, what a concept!

**原因分析**：作者真正在骂这部翻拍片（this mess、horrible remake），但同时大量赞美原版（delightful original、a spicy stew），末尾还用 `Wow, what a concept!` 反讽。模型把对原版的赞美当成了对影片的赞美。样本长度 430 词，其中真正的负面判断集中在前两句。

**类型**：反讽 + 对比对象混淆（把对 A 的赞美当成对 B 的赞美）。

## 案例六：长文本被截断，关键评价在后半段（test-004366）

真实标签：负面。TF-IDF 判负面（正确），DistilBERT 判正面（错误）。876 词，约 1099 token。

原文开头：

> Title: Dracula A.D. 1972 ... Sometimes movies can be time capsules that transport you back to any given time. In this case...our time capsule is Hammers Dracula A.D. 1972 which transports us back to a time in which Austin Powers would have felt right at home.

**原因分析**：这条影评超过 256 token，按截断策略只把前 256 个 token 送进 DistilBERT，而开头恰好是调侃式的介绍（Hollywood 风格、Austin Powers 类比），语气轻松；真正"这片子很糟糕"的结论在后半段，被截掉了。TF-IDF 使用全文，所以没有受这个影响。

**类型**：截断损失（正是本项目要说明的局限）。

## 案例七：短文本 + 委婉表达，两模型分歧（test-001809）

真实标签：负面。TF-IDF 判负面（正确），DistilBERT 判正面（错误）。仅 40 词。

原文（完整）：

> If you have few expectations, then this will entertain for 90 minutes. My problem is that they've dumbed down this tale for the modern audience. Highwaymen are already sexy, exciting characters. They don;t need the techno soundtrack and snappy dialogue.

**原因分析**：`will entertain for 90 minutes` 是限定式让步，`dumbed down` 才是真正的批评；后面还有拼写错误 `don;t`。TF-IDF 靠 `problem`、`dumbed` 这类词抓到负面，DistilBERT 更依赖上下文语义，在这么短的文本里被前两句的"能看"带偏。

**类型**：短文本信息不足 / 委婉表达。

## 从这些案例得到的结论

1. **反讽与否定是主要失分点**。两个模型都对褒义词密度敏感，对"褒词贬用"不敏感。这与设计文档里"否定、转折、褒贬混合"的背景描述完全对应。
2. **标签本身不干净**。IMDB 标签来自用户打分，混合评价与无效文本都会让指标偏低，这部分不是模型能修好的。
3. **截断是真实存在的损失**。200 条测试集里有 69 条超过 256 token（34.5%），长影评的结论往往在结尾，截断会系统性地丢掉这类信息。
4. **传统模型并不总是更差**。在案例六这种"关键词明确、长文本"的情形下，TF-IDF 反而判对了，因为它用的是全文。
5. **两模型一致率 0.81，但错误并不重合**：8 条是共同错，38 条是分歧，说明两个模型的偏差来源不同，这也是本项目要同时保留两个模型的意义。
