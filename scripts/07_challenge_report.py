#!/usr/bin/env python
"""阶段三 · 模型挑战结果记录（6 对预置样本）

执行顺序：第 7 步（需先运行 06_retrieval_check.py --score，网页实验页会用到）
用法：
    python scripts/07_challenge_report.py

内容（设计文档 5.3）：原句、改写句、人工情感判断、两个模型的输出、预测变化是否合理。
产物：
    experiments/challenge_results.csv   逐对逐模型的对比记录
    experiments/challenge_results.md    给报告直接引用的表格
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common import config  # noqa: E402
from backend.artifacts import HFSentiment, TfidfSentiment  # noqa: E402

LABEL_CN = {"positive": "正面", "negative": "负面"}


def judge(expected_change: str, changed: bool) -> tuple[bool, str]:
    """返回 (是否合理, 说明)。"""
    if expected_change == "flip":
        if changed:
            return True, "情感本应翻转，模型跟随变化"
        return False, "情感本应翻转，模型没有变化"
    if expected_change == "stable":
        if not changed:
            return True, "只是换说法，模型保持稳定"
        return False, "只是换说法，模型却翻转了"
    return True, "无人工预期"


def main() -> None:
    payload = json.loads((config.DATA_DIR / "challenge_pairs.json").read_text(encoding="utf-8"))
    pairs = payload["pairs"]

    print("加载模型……")
    tfidf = TfidfSentiment()
    hf = HFSentiment()
    models = [("tfidf", "TF-IDF + 逻辑回归", tfidf), ("distilbert", "DistilBERT SST-2", hf)]

    rows = []
    for pair in pairs:
        for key, display, model in models:
            left = model.predict(pair["original"])
            right = model.predict(pair["rewritten"])
            changed = left["label"] != right["label"]
            reasonable, note = judge(pair["expected_change"], changed)
            rows.append({
                "id": pair["id"],
                "category": pair["category_cn"],
                "model": display,
                "original": pair["original"],
                "rewritten": pair["rewritten"],
                "human_label_original": pair["human_label_original"],
                "human_label_rewritten": pair["human_label_rewritten"],
                "expected_change": pair["expected_change"],
                "pred_original": left["label_name"],
                "pred_original_score": left["score"],
                "pred_rewritten": right["label_name"],
                "pred_rewritten_score": right["score"],
                "prediction_changed": changed,
                "change_reasonable": reasonable,
                "note": note,
            })

    config.EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = config.EXPERIMENTS_DIR / "challenge_results.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    # 汇总：每个模型在 6 对样本上是否合理
    summary = {}
    for key, display, _ in models:
        subset = [r for r in rows if r["model"] == display]
        summary[display] = {
            "pairs": len(subset),
            "changed_on_flip_expected": sum(
                1 for r in subset if r["expected_change"] == "flip" and r["prediction_changed"]
            ),
            "flip_pairs": sum(1 for r in subset if r["expected_change"] == "flip"),
            "stable_on_stable_expected": sum(
                1 for r in subset if r["expected_change"] == "stable" and not r["prediction_changed"]
            ),
            "stable_pairs": sum(1 for r in subset if r["expected_change"] == "stable"),
            "reasonable": sum(1 for r in subset if r["change_reasonable"]),
        }

    lines = [
        "# 模型挑战结果（6 对预置样本）",
        "",
        "由 `scripts/07_challenge_report.py` 生成。expected_change 为人工判断的情感走向：",
        "`flip` 表示改写句的情感应当翻转，`stable` 表示只是换说法、情感应当保持。",
        "",
    ]
    current = None
    for row in rows:
        if row["id"] != current:
            current = row["id"]
            lines += [
                f"## {row['id']} · {row['category']}（{'应翻转' if row['expected_change'] == 'flip' else '应保持'}）",
                "",
                f"- 原句：{row['original']}",
                f"- 改写：{row['rewritten']}",
                f"- 人工判断：{LABEL_CN[row['human_label_original']]} → {LABEL_CN[row['human_label_rewritten']]}",
                "",
                "| 模型 | 原句预测 | 分数 | 改写句预测 | 分数 | 是否翻转 | 是否合理 |",
                "|---|---|---|---|---|---|---|",
            ]
        lines.append(
            f"| {row['model']} | {LABEL_CN[row['pred_original']]} | {row['pred_original_score']:.4f} | "
            f"{LABEL_CN[row['pred_rewritten']]} | {row['pred_rewritten_score']:.4f} | "
            f"{'是' if row['prediction_changed'] else '否'} | {row['note']} |"
        )
    lines += ["", "## 汇总", ""]
    for display, item in summary.items():
        lines.append(
            f"- {display}：应翻转的 {item['flip_pairs']} 对中翻转了 {item['changed_on_flip_expected']} 对；"
            f"应保持的 {item['stable_pairs']} 对中保持了 {item['stable_on_stable_expected']} 对；"
            f"合计 {item['reasonable']}/{item['pairs']} 对合理。"
        )
    (config.EXPERIMENTS_DIR / "challenge_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\n{'编号':<6}{'模型':<22}{'原句':<8}{'改写':<8}{'翻转':<6}合理")
    for row in rows:
        print(
            f"{row['id']:<6}{row['model']:<22}"
            f"{LABEL_CN[row['pred_original']]:<8}{LABEL_CN[row['pred_rewritten']]:<8}"
            f"{'是' if row['prediction_changed'] else '否':<6}{'✓' if row['change_reasonable'] else '✗'}"
        )
    print()
    for display, item in summary.items():
        print(f"{display}：{item['reasonable']}/{item['pairs']} 对判断合理")
    print(f"\n已写入 {csv_path}")
    print(f"已写入 {config.EXPERIMENTS_DIR / 'challenge_results.md'}")


if __name__ == "__main__":
    main()
