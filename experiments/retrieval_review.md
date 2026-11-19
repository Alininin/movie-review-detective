# 25 条检索相关性复核单

判据：**相关性以是否表达查询的主要观点为依据，不能只看有没有相同单词**；
话题相关即算相关，情感正负都算（夸演技和骂演技都算「演技相关」）。

怎么用：逐条读摘录（或点开对应 ID 看全文），在心里给出判断，
和「当前判断」不一致时，记下要说的话；改完 `experiments/retrieval_check.csv` 里
的 `relevant`（相关 / 不相关）与 `reason` 两列，再跑 `--score` 重算。

## 一眼看全：当前 25 条判断

| 查询 | 主题 | 相关 / 5 | P@5 |
|---|---|---|---|
| Q1 | 演技 | 5/5 | 1.00 |
| Q2 | 剧情 | 2/5 | 0.40 |
| Q3 | 节奏 | 3/5 | 0.60 |
| Q4 | 配乐 | 4/5 | 0.80 |
| Q5 | 台词与幽默 | 4/5 | 0.80 |
| **平均** | — | 18/25 | 0.7200 |

## Q1 · 演技

> 查询：The lead actor gave a powerful performance with great emotional depth.

**#1 · pool-008346 · 相似度 0.5039 · 数据集标签 负面 · 821 词**

- 当前判断：**相关**
- 当前理由：通篇比较舞台版与影片的表演和情感效果，属于对演技的讨论
- 原文摘录：Funny that I find myself forced to review this movie, but here I am. I am reviewing it, because just recently, I have had the chance to witness the revival of R.C. Sheriff's play "Journey's End" on stage in New York, at the Belasco Theatre, starring Hugh Darcy, Boyd Gaines, Jefferson Mays and others, as well as being masterfully directed by David Grindley. I left the theater shattered. I am …
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

**#2 · pool-014314 · 相似度 0.4659 · 数据集标签 正面 · 199 词**

- 当前判断：**相关**
- 当前理由：明确评价 Dudley Moore 的表演与 Gielgud 的角色选择
- 原文摘录：Again, it seems totally illogical, to me at least, that "Arthur" merits a mere 6.4 out of 10 possible. Steve Gordon's one-shot masterpiece herein is the totally "unlikely" if not quite "impossible" melding of wildly disparate elements. That he managed to make alcoholism laugh-friendly rather than tearjerking tragic is, in itself, wonderful. That he gave Dudley Moore his finest role, and every other cinematic element herein its optimal impact, including …
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

**#3 · pool-005765 · 相似度 0.4626 · 数据集标签 负面 · 164 词**

- 当前判断：**相关**
- 当前理由：逐一点评 Bening、Cross、Wood 三人的表演水准
- 原文摘录：Not sure why this film was advertised as a wild, quirky, laugh filled comedy. There is not much in this movie that will entertain, nor amuse the moviegoer. Annette Bening (whose acting was touted as being Oscar worthy) comes off here as mannered, with her performance seeming routine. Brian Cox's character is confusing and irritating, and the lead playing Augusten  Joseph Cross  appears to simply not have the …
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

**#4 · pool-010708 · 相似度 0.4596 · 数据集标签 负面 · 243 词**

- 当前判断：**相关**
- 当前理由：讨论演员阵容是否被用好，并点名 Cuba Gooding Jr. 表演糟糕
- 原文摘录：Don't get fooled with all the big names like Burt Reynolds,James Woods and Anne Archer. They are just glorified extra's. Their scenes were probably filmed in one day or so. Whatever their motives for being in this movie, if you have an actor like James Woods you better make good use of him. To me this is a sign of bad direction through and through. The plot itself wasn't that …
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

**#5 · pool-021673 · 相似度 0.4445 · 数据集标签 正面 · 515 词**

- 当前判断：**相关**
- 当前理由：讨论演员只是在演自己、观众误以演技评判影片
- 原文摘录：I've recently went back and watched this movie again from not seeing it in years. When I first seen the movie I was too young to understand what the movie was about. Now that I've seen it again I couldn't believe what I've missed all these years. For me being able to see movies for what they are, I think that this movie was great. Most people feel as though …
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

## Q2 · 剧情

> 查询：The story has an unexpected twist that keeps the audience guessing until the end.

**#1 · pool-009389 · 相似度 0.4973 · 数据集标签 负面 · 114 词**

- 当前判断：**相关**
- 当前理由：明确提到结局反转，并认为反转拙劣、可预料
- 原文摘录：After the opening credits, there's a black screen for about a minute. A minute of nothing, then a girl wakes up and takes a shower.Then her and two college friends are driving to a rock concert, after much padding, they hit something and skid off the road. They awaken in a cabin inhabited by a wheelchair-bound old lady and her offspring.The killings are sadly very tame for a supposed Video …
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

**#2 · pool-007978 · 相似度 0.4746 · 数据集标签 负面 · 130 词**

- 当前判断：**不相关**
- 当前理由：只谈视觉风格与剧情单薄，没有涉及反转或悬念
- 原文摘录：Visually disjointed and full of itself, the director apparently chose to seek faux-depth to expand a 5 minute plot into an 81 minute snore-fest. The moments that work in this film are VERY limited, and the characters don't even feel real. How could you feel invested in a main protagonist who was made so surreal? Substantively AND stylistically, it all feels like a quirky dream sequence. Jarring irregular camera work, …
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

**#3 · pool-016800 · 相似度 0.4620 · 数据集标签 正面 · 167 词**

- 当前判断：**不相关**
- 当前理由：讲人物关系与幽默场景，没有涉及剧情反转
- 原文摘录：Actually I'm surprised there were so many comments about this movie. I saw it as part of a Slavic film festival at a major American University. But nobody in USA has heard of it, which is a real shame! The dynamics between the people are what makes it both funny and sad. They are stuck together on a long bus trip--someplace most of us have been!! But I never had …
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

**#4 · pool-014554 · 相似度 0.4512 · 数据集标签 正面 · 110 词**

- 当前判断：**相关**
- 当前理由：讨论剧情走向是否在意料之中、结局是否被提前看穿
- 原文摘录：OK, first of all, ignore the last person' review. They admit to falling asleep through it so it's no wonder they didn't understand what was going on!!! As thriller/horrors go, this film ain't too bad, it is certainly very watchable. Right from the opening scenes you get a general idea exactly what is going to be the cause of all the craziness that follows, and come the end you are …
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

**#5 · pool-015562 · 相似度 0.4472 · 数据集标签 正面 · 40 词**

- 当前判断：**不相关**
- 当前理由：只称赞群像与叙事，没有涉及反转或悬念
- 原文摘录：This is not the stuff of soap-operas but the sort of conundrums that real people face in real life. A testament to the ensemble and director for the powerful story-telling of fallible characters trying to cope but not quite succeeding.
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

## Q3 · 节奏

> 查询：The pacing is painfully slow and the film drags badly in the middle.

**#1 · pool-010708 · 相似度 0.5434 · 数据集标签 负面 · 243 词**

- 当前判断：**相关**
- 当前理由：明确指出节奏错误，主角半小时后才进入状态
- 原文摘录：Don't get fooled with all the big names like Burt Reynolds,James Woods and Anne Archer. They are just glorified extra's. Their scenes were probably filmed in one day or so. Whatever their motives for being in this movie, if you have an actor like James Woods you better make good use of him. To me this is a sign of bad direction through and through. The plot itself wasn't that …
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

**#2 · pool-000119 · 相似度 0.5429 · 数据集标签 负面 · 143 词**

- 当前判断：**相关**
- 当前理由：提到开演 30 分钟后开始无聊、慢镜头过多
- 原文摘录：6/10 Acting, not great but some good acting. 4/10 Director, makes some stupid decisions for this film. 2/10 Writer, story makes no sense at all and has huge amount of flaws. 4/10 Overall score for this movie. Don't waste your time with this film, it's not worth it. I gave 4 for this movie and it may be too much. Characters are so over exaggerated than they can ever be …
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

**#3 · pool-006375 · 相似度 0.5372 · 数据集标签 负面 · 99 词**

- 当前判断：**不相关**
- 当前理由：主要谈表演差、角色讨厌，没有谈节奏
- 原文摘录：This film looked interesting; I'd read the book a number of years ago and it informed me that the feature followed the plot outline pretty tightly. Started watching it and almost from the outset it failed to live up to expectations. In fact, I didn't bother watching the whole thing... utter drivel - bad performances, bad acting and instantly dislikeable characters - that was the point of the film, I …
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

**#4 · pool-000205 · 相似度 0.5270 · 数据集标签 负面 · 193 词**

- 当前判断：**不相关**
- 当前理由：主要谈胶片与录像混用的画质问题和剧本，没有谈节奏
- 原文摘录：This movie was made-for-TV, so taking that into account, I'm not going to rip into it as hard as I would a feature film. The script is sub-par, but it does succeed in being mildly humorous in spots, whether it means to be or not. The acting is mostly over-the-top, but that is true for many lower-budget movies. The aspect of this movie that I really hated, though, was that …
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

**#5 · pool-007978 · 相似度 0.5194 · 数据集标签 负面 · 130 词**

- 当前判断：**相关**
- 当前理由：称 81 分钟是催眠，动作段落之间存在空洞与冷场
- 原文摘录：Visually disjointed and full of itself, the director apparently chose to seek faux-depth to expand a 5 minute plot into an 81 minute snore-fest. The moments that work in this film are VERY limited, and the characters don't even feel real. How could you feel invested in a main protagonist who was made so surreal? Substantively AND stylistically, it all feels like a quirky dream sequence. Jarring irregular camera work, …
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

## Q4 · 配乐

> 查询：The soundtrack is beautiful and fits the mood of every scene perfectly.

**#1 · pool-015732 · 相似度 0.5139 · 数据集标签 正面 · 61 词**

- 当前判断：**相关**
- 当前理由：直接把 stellar soundtrack 列为影片最美之处
- 原文摘录：Such a film of beauty that it's hard to describe. Maybe it's the absence of superfluous dialogue, or maybe it's the absolutely stellar soundtrack, or maybe it's just Meena Mumari's feet, but it's a joy to watch this movie again and again. I've never seen another Indian movie that comes close to it, and few from any country rival its perfection.
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

**#2 · pool-022929 · 相似度 0.5047 · 数据集标签 正面 · 109 词**

- 当前判断：**不相关**
- 当前理由：通篇谈爱情与演员表现，没有提到配乐
- 原文摘录：the most amazing combination of love and psyche of two young people.presented in the most sublime manner and definitely touches your heart.a rare combination where the sequel surpasses the prequel in both storytelling and intensity of emotions.the movie re affirms your faith in love and pain of separation. the joy of seeing your most beloved is unparalleled and anything can be sacrificed. Ethan and Julie have essayed eternal characters with …
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

**#3 · pool-010955 · 相似度 0.4710 · 数据集标签 负面 · 120 词**

- 当前判断：**相关**
- 当前理由：批评配乐像在某人的笔记本电脑上做出来的
- 原文摘录：The really sad thing is that this was supposedly the highest budget "Halestorm Entertainment" has had to work with. All involved should be fined for littering since all the celluloid they wasted is good for nothing more than filling the trash. Not only is the writing atrocious and the jokes awful, but the camera work and film quality are amateur at best. The soundtrack sounds like it was created on …
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

**#4 · pool-018503 · 相似度 0.4687 · 数据集标签 正面 · 144 词**

- 当前判断：**相关**
- 当前理由：提到片中音乐虽有限但好听，插曲难忘
- 原文摘录：I am very sorry that this charming and whimsical film (which I first saw soon after it was first released in the early fifties) has had such a poor reception more recently. In my opinion it has been greatly underrated - but perhaps it appeals more to the European sense of humour than to (for example) the American: maybe we in Europe can understand and appreciate its subtleties and situations …
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

**#5 · pool-008741 · 相似度 0.4596 · 数据集标签 负面 · 280 词**

- 当前判断：**相关**
- 当前理由：大段批评配乐被滥用、同一首歌重复播放
- 原文摘录：I am completely baffled as to why this film is even liked, let alone held in such high regard, especially by so many critics who are, otherwise, quite sensible. There is one key word which describes this film to its core - irritating. The most easily explained example of this is the director's use - or, more accurately, abuse - of music. In the first half, a really dull reggae …
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

## Q5 · 台词与幽默

> 查询：The dialogue is witty and most of the jokes land surprisingly well.

**#1 · pool-001835 · 相似度 0.5108 · 数据集标签 负面 · 370 词**

- 当前判断：**相关**
- 当前理由：讨论台词刻意荒诞、以讽刺方式讲出并制造笑点
- 原文摘录：This is a low-budget spoof of the espionage genre. To help frame your expectations, you should know that: (1) The acting is wildly heavy-handed. The stars are having great fun delivering their lines with excessive eye movement, frequent hand gestures, and off-key pacing. (2) The script deliberately lacks continuity and plausibility. Oftentimes lines are abruptly jarring and humorous because they have absolutely no relevance to previous plot elements. (3) Shots …
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

**#2 · pool-004246 · 相似度 0.4962 · 数据集标签 负面 · 263 词**

- 当前判断：**相关**
- 当前理由：逐句比较台词与笑点，指出只有一句好笑
- 原文摘录：I will never forget the wit and great comedy of the ORIGINAL Vacation movie! The lines, pacing, and timing of events in that film are outstanding! However, this European Vacation sequel is a major let down. In this sequel, the Griswalds win a European Vacation on a game show. The problem is that many of the jokes in the film are little more than mild, "ha-ha" laughs. For example, a …
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

**#3 · pool-010851 · 相似度 0.4881 · 数据集标签 负面 · 42 词**

- 当前判断：**相关**
- 当前理由：评价这部所谓喜剧并不能让人笑
- 原文摘录：Billy Crystal normally brings the crowd to laughter, but in this movie he and all the rest of them cannot bring any smile on my face.... or perhaps just one. They call it comedy, I say it's a waste of my time.
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

**#4 · pool-020923 · 相似度 0.4541 · 数据集标签 正面 · 162 词**

- 当前判断：**相关**
- 当前理由：提到片中金句多，看的时候会跟着念台词
- 原文摘录：This is one of my all time favorites. It is so simple and sweet - definitely a chick flick romantic comedy. I really like a film full of good quotes and this has it... one of my favorites is when Albert Einstein says to Ed Walters "Are you thinking what I'm thinking" and Ed says "Now what are the odds of that happening!" In my opinion, a film is fabulous …
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

**#5 · pool-022148 · 相似度 0.4382 · 数据集标签 正面 · 58 词**

- 当前判断：**不相关**
- 当前理由：只谈故事轻松有趣，没有涉及台词或笑点
- 原文摘录：I have to tell you, this is a great movie. It surprises me sometimes how good a movie with no pretenses can be. This one is just fabulous. It could be that it isn't TRYING too hard to send any kind of message; it just tells a whimsical, fun story. I gave it a 10 out of 10.
- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________

---

## 改完之后

```bash
# 1) 在 experiments/retrieval_check.csv 里改 relevant 与 reason
# 2) 重算 Precision@5
.venv/Scripts/python scripts/06_retrieval_check.py --score
# 3) 让报告里的 P@5 表格跟着更新（报告正文那句「剧情类 P@5 只有 0.40」需要看一眼是否还对）
.venv/Scripts/python report/build_report.py
```

改完数字若与 `README.md` 里的「检索平均 Precision@5 = 0.7200」不一致，记得同步那一行。

