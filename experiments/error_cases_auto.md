# 错误与分歧样本清单（自动生成）

本文件由 `scripts/04_evaluate.py` 自动生成，只提供事实数据；
**逐条的原因解释见 `experiments/error_cases.md`（人工撰写）**。

- 生成时间：2026-11-17T18:11:04+08:00
- 测试集：200 条
- TF-IDF + LR：Acc 0.8150 / Macro-F1 0.8150
- DistilBERT：Acc 0.9150 / Macro-F1 0.9150
- 两模型一致率：0.8100

## 一、两模型都判错的样本

| # | 样本 ID | 真实 | TF-IDF | DistilBERT | 词数 |
|---|---|---|---|---|---|
| 1 | test-002958 | negative | positive | positive | 199 |
| 2 | test-003788 | negative | positive | positive | 127 |
| 3 | test-006225 | negative | positive | positive | 154 |
| 4 | test-007579 | negative | positive | positive | 108 |
| 5 | test-008504 | negative | positive | positive | 430 |
| 6 | test-016153 | positive | negative | negative | 268 |
| 7 | test-023647 | positive | negative | negative | 129 |
| 8 | test-023872 | positive | negative | negative | 159 |

## 二、两模型意见不一致的样本

| # | 样本 ID | 真实 | TF-IDF | DistilBERT | 谁对 | 词数 |
|---|---|---|---|---|---|---|
| 1 | test-001521 | negative | positive | negative | DistilBERT | 76 |
| 2 | test-001628 | negative | positive | negative | DistilBERT | 132 |
| 3 | test-001809 | negative | negative | positive | TF-IDF | 40 |
| 4 | test-002690 | negative | positive | negative | DistilBERT | 101 |
| 5 | test-002803 | negative | positive | negative | DistilBERT | 81 |
| 6 | test-003105 | negative | positive | negative | DistilBERT | 130 |
| 7 | test-003191 | negative | positive | negative | DistilBERT | 104 |
| 8 | test-003386 | negative | negative | positive | TF-IDF | 127 |
| 9 | test-004366 | negative | negative | positive | TF-IDF | 876 |
| 10 | test-004370 | negative | negative | positive | TF-IDF | 290 |
| 11 | test-004574 | negative | positive | negative | DistilBERT | 448 |
| 12 | test-005050 | negative | positive | negative | DistilBERT | 136 |
| 13 | test-006217 | negative | positive | negative | DistilBERT | 119 |
| 14 | test-007698 | negative | positive | negative | DistilBERT | 264 |
| 15 | test-007861 | negative | positive | negative | DistilBERT | 183 |

## 三、超长样本（超过 256 token 会被截断）

| 样本 ID | token 数 | 真实 | TF-IDF | DistilBERT |
|---|---|---|---|---|
| test-000338 | 400 | negative | negative | negative |
| test-000450 | 551 | negative | negative | negative |
| test-000658 | 765 | negative | negative | negative |
| test-000746 | 280 | negative | negative | negative |
| test-001431 | 259 | negative | negative | negative |
| test-002694 | 298 | negative | negative | negative |
| test-003609 | 297 | negative | negative | negative |
| test-004277 | 489 | negative | negative | negative |
| test-004366 | 1099 | negative | negative | positive |
| test-004370 | 380 | negative | negative | positive |
| test-004574 | 586 | negative | positive | negative |
| test-004711 | 387 | negative | negative | negative |
| test-004837 | 377 | negative | negative | negative |
| test-005023 | 268 | negative | negative | negative |
| test-005111 | 417 | negative | negative | negative |
| test-005360 | 262 | negative | negative | negative |
| test-005488 | 258 | negative | negative | negative |
| test-005509 | 683 | negative | negative | negative |
| test-005793 | 315 | negative | negative | negative |
| test-006172 | 289 | negative | negative | negative |
| test-006346 | 583 | negative | negative | negative |
| test-006954 | 359 | negative | negative | negative |
| test-007698 | 359 | negative | positive | negative |
| test-007892 | 385 | negative | positive | negative |
| test-007955 | 491 | negative | negative | negative |
| test-008146 | 397 | negative | negative | negative |
| test-008504 | 548 | negative | positive | positive |
| test-008674 | 480 | negative | negative | negative |
| test-009472 | 767 | negative | negative | negative |
| test-009812 | 375 | negative | negative | negative |
| test-010447 | 488 | negative | negative | negative |
| test-011136 | 357 | negative | negative | negative |
| test-011487 | 356 | negative | negative | negative |
| test-011957 | 531 | negative | negative | negative |
| test-013275 | 607 | positive | positive | positive |
| test-014125 | 370 | positive | positive | positive |
| test-014799 | 543 | positive | positive | positive |
| test-014812 | 646 | positive | positive | positive |
| test-014889 | 310 | positive | positive | positive |
| test-015845 | 579 | positive | positive | positive |
| test-016043 | 258 | positive | positive | positive |
| test-016153 | 351 | positive | negative | negative |
| test-016614 | 266 | positive | positive | positive |
| test-016655 | 378 | positive | positive | positive |
| test-016781 | 597 | positive | positive | positive |
| test-017761 | 544 | positive | positive | positive |
| test-018504 | 269 | positive | positive | positive |
| test-019411 | 709 | positive | positive | positive |
| test-019629 | 273 | positive | positive | positive |
| test-019987 | 683 | positive | positive | positive |
| test-020352 | 560 | positive | positive | positive |
| test-020651 | 377 | positive | positive | positive |
| test-020871 | 1202 | positive | positive | positive |
| test-020999 | 323 | positive | positive | positive |
| test-021147 | 270 | positive | positive | positive |
| test-021194 | 749 | positive | positive | positive |
| test-021442 | 382 | positive | positive | positive |
| test-021547 | 469 | positive | positive | positive |
| test-021756 | 705 | positive | positive | positive |
| test-021877 | 757 | positive | negative | positive |
| test-022084 | 268 | positive | negative | positive |
| test-022149 | 257 | positive | positive | positive |
| test-022237 | 275 | positive | negative | positive |
| test-022448 | 516 | positive | positive | positive |
| test-022551 | 613 | positive | positive | positive |
| test-024109 | 380 | positive | positive | negative |
| test-024245 | 536 | positive | positive | positive |
| test-024865 | 546 | positive | negative | positive |
| test-024942 | 468 | positive | positive | positive |
