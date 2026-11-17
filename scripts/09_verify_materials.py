"""材料一致性自检：把「交付物里的每个数字」和「原始数据」对一遍账。

为什么需要它（对应任务书 A3 / C1 / D3 与 八）：
  * 网页统计、指标、混淆矩阵、Precision@5 都来自 data/ 与 experiments/ 下的文件，
    老师现场抽查任何一个数字，都应该能从 CSV 重新算出来；
  * 本项目声称「重跑脚本可得到一致划分」，那么抽样清单、样本 ID 与原始行号必须对得上；
  * 声称「两个模型在同一份 200 条测试集上评测」，那么逐条预测的 ID 必须与测试集完全一致。

本脚本只读，不修改任何文件，不需要启动后端。用法：

    .venv/Scripts/python scripts/09_verify_materials.py

退出码 0 表示全部一致，1 表示有对不上的地方。
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
EXP = ROOT / "experiments"

_failed: list[str] = []
_passed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global _passed
    if ok:
        _passed += 1
        print(f"  [OK]   {name}")
    else:
        _failed.append(name)
        print(f"  [FAIL] {name}" + (f" —— {detail}" if detail else ""))


def section(title: str) -> None:
    print(f"\n{title}")


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def accuracy(truth: list[int], guess: list[int]) -> float:
    return sum(1 for t, g in zip(truth, guess) if t == g) / len(truth)


def macro_f1(truth: list[int], guess: list[int]) -> float:
    scores = []
    for label in (0, 1):
        tp = sum(1 for t, g in zip(truth, guess) if t == label and g == label)
        fp = sum(1 for t, g in zip(truth, guess) if t != label and g == label)
        fn = sum(1 for t, g in zip(truth, guess) if t == label and g != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return sum(scores) / len(scores)


def main() -> int:
    section("[1] 抽样结果 reviews.csv")
    rows = read_csv(DATA / "reviews.csv")
    check("共 1200 行", len(rows) == 1200, str(len(rows)))
    splits: dict[str, list[dict]] = {}
    for row in rows:
        splits.setdefault(row["split"], []).append(row)
    check("训练 1000 / 测试 200",
          len(splits.get("train", [])) == 1000 and len(splits.get("test", [])) == 200,
          str({k: len(v) for k, v in splits.items()}))
    for split, items in splits.items():
        positive = sum(1 for row in items if row["label"] == "1")
        check(f"{split} 正负各半", positive == len(items) - positive, f"正面 {positive} / 共 {len(items)}")
    texts = [row["text"] for row in rows]
    check("无重复文本", len(set(texts)) == len(texts), f"{len(texts)} 行，去重后 {len(set(texts))}")
    train_texts = {row["text"] for row in splits["train"]}
    test_texts = {row["text"] for row in splits["test"]}
    check("训练集与测试集无重叠", not (train_texts & test_texts), f"重叠 {len(train_texts & test_texts)} 条")
    check("sample_id 唯一", len({row["sample_id"] for row in rows}) == len(rows))
    bad_id = [row["sample_id"] for row in rows
              if row["sample_id"] != f"{row['split']}-{int(row['original_index']):06d}"]
    check("sample_id 可回溯到原始行号", not bad_id, f"异常 {bad_id[:3]}")
    check("每条都带清洗后文本、标签与所属集合",
          all(row["text"] and row["label"] in ("0", "1") and row["split"] in ("train", "test")
              for row in rows))

    section("[2] 抽样清单 sampling_manifest.json")
    manifest = read_json(DATA / "sampling_manifest.json")
    check("记录固定随机种子 42", manifest.get("seed") == 42, str(manifest.get("seed")))
    check("记录数据集标识", bool(manifest.get("dataset")), str(manifest.get("dataset"))[:80])
    check("记录抽样规则", bool(manifest.get("sampling_rule")), str(manifest.get("sampling_rule"))[:80])

    section("[3] 检索库 retrieval_pool.csv")
    pool = read_csv(DATA / "retrieval_pool.csv")
    check("共 500 条", len(pool) == 500, str(len(pool)))
    pool_positive = sum(1 for row in pool if row["label"] == "1")
    check("正负各 250", pool_positive == 250, f"正面 {pool_positive}")
    check("检索库与训练集/测试集不重叠",
          not ({row["text"] for row in pool} & (train_texts | test_texts)),
          f"重叠 {len({row['text'] for row in pool} & (train_texts | test_texts))} 条")

    section("[4] 向量文件 embeddings.npy / embeddings_ids.json")
    import numpy as np

    embeddings = np.load(DATA / "embeddings.npy")
    ids_payload = read_json(DATA / "embeddings_ids.json")
    check("向量形状 500×384", embeddings.shape == (500, 384), str(embeddings.shape))
    norms = np.linalg.norm(embeddings, axis=1)
    check("向量已 L2 归一化（点积即余弦）", bool(np.allclose(norms, 1.0, atol=1e-4)),
          f"范数 {norms.min():.4f}~{norms.max():.4f}")
    check("ID 数量与向量条数一致", len(ids_payload["pool_ids"]) == 500, str(len(ids_payload["pool_ids"])))
    check("ID 顺序与检索库一致（按行号对应）",
          ids_payload["pool_ids"] == [row["sample_id"] for row in pool])

    section("[5] 逐条预测 predictions_test.csv")
    predictions = read_csv(EXP / "predictions_test.csv")
    check("共 200 行", len(predictions) == 200, str(len(predictions)))
    test_ids = [row["sample_id"] for row in splits["test"]]
    check("预测样本与测试集 ID 完全对应", [row["sample_id"] for row in predictions] == test_ids)
    label_by_id = {row["sample_id"]: int(row["label"]) for row in rows}
    mismatched = [row["sample_id"] for row in predictions
                  if label_by_id.get(row["sample_id"]) != int(row["true_label"])]
    check("逐条真实标签与 reviews.csv 一致", not mismatched, str(mismatched[:3]))

    section("[6] 指标文件 metrics.json（全部重新计算）")
    metrics = read_json(EXP / "metrics.json")
    truth = [int(row["true_label"]) for row in predictions]
    for key, column in (("tfidf", "tfidf_label"), ("distilbert", "distilbert_label")):
        guess = [int(row[column]) for row in predictions]
        recorded = metrics["models"][key]
        recomputed_acc = accuracy(truth, guess)
        recomputed_f1 = macro_f1(truth, guess)
        check(f"{key} Accuracy 可复算",
              abs(recomputed_acc - recorded["accuracy"]) < 1e-6,
              f"复算 {recomputed_acc:.6f} vs 记录 {recorded['accuracy']}")
        check(f"{key} Macro-F1 可复算",
              abs(recomputed_f1 - recorded["macro_f1"]) < 1e-4,
              f"复算 {recomputed_f1:.6f} vs 记录 {recorded['macro_f1']}")
        matrix = [[0, 0], [0, 0]]
        for t, g in zip(truth, guess):
            matrix[t][g] += 1
        check(f"{key} 混淆矩阵可复算", matrix == recorded["confusion_matrix"],
              f"{matrix} vs {recorded['confusion_matrix']}")
        check(f"{key} 加载与推理耗时分开记录",
              "model_load_seconds" in recorded.get("timing", {})
              and "inference_total_seconds" in recorded.get("timing", {}),
              str(recorded.get("timing")))
    agree = sum(1 for row in predictions if row["tfidf_label"] == row["distilbert_label"]) / len(predictions)
    check("两模型一致率可复算", abs(agree - metrics["agreement_rate"]) < 1e-6,
          f"{agree:.4f} vs {metrics['agreement_rate']}")
    check("记录 CPU、批大小与输入长度设置", bool(metrics.get("run_config")),
          str(metrics.get("run_config"))[:100])
    check("评测只用 200 条测试集",
          (metrics.get("evaluated_on") or {}).get("samples") == 200,
          str(metrics.get("evaluated_on")))

    section("[7] 统计文件 stats.json（与网页同源）")
    stats = read_json(DATA / "stats.json")
    totals = stats["totals"]
    check("总数与 reviews.csv 一致",
          totals["reviews"] == len(rows) and totals["train"] == 1000 and totals["test"] == 200,
          str(totals))
    word_lengths = [int(row["word_len"]) for row in rows]
    mean_words = sum(word_lengths) / len(word_lengths)
    check("平均长度可复算（按词）",
          abs(stats["length"]["all"]["word"]["mean"] - mean_words) < 0.05,
          f"{stats['length']['all']['word']['mean']} vs {mean_words:.2f}")
    check("统计里注明长度口径", bool(stats.get("length_unit")), str(stats.get("length_unit")))

    section("[8] 检索人工判断 retrieval_check.csv")
    judgments = read_csv(EXP / "retrieval_check.csv")
    check("共 25 条判断（5 条查询 × Top-5）", len(judgments) == 25, str(len(judgments)))
    check("relevant 列已填写（相关 / 不相关）",
          all(row["relevant"] in ("相关", "不相关") for row in judgments))
    check("每条判断都写了理由", all(row["reason"].strip() for row in judgments))
    per_query: dict[str, list[int]] = {}
    for row in judgments:
        per_query.setdefault(row["query_id"], []).append(1 if row["relevant"] == "相关" else 0)
    check("5 条查询各有 5 条判断", len(per_query) == 5 and all(len(v) == 5 for v in per_query.values()),
          str({k: len(v) for k, v in per_query.items()}))
    mean_p5 = sum(sum(v) / len(v) for v in per_query.values()) / len(per_query)
    retrieval = read_json(EXP / "retrieval_metrics.json")
    check("平均 Precision@5 可复算",
          abs(mean_p5 - retrieval["mean_precision_at_5"]) < 1e-4,
          f"{mean_p5:.4f} vs {retrieval['mean_precision_at_5']}")
    pool_ids = {row["sample_id"] for row in pool}
    unknown = [row["sample_id"] for row in judgments if row["sample_id"] not in pool_ids]
    check("判断的样本都来自检索库", not unknown, str(unknown[:3]))

    section("[9] 模型挑战 challenge_results.csv")
    challenge = read_csv(EXP / "challenge_results.csv")
    pairs = {row["id"] for row in challenge}
    check("6 对样本 × 2 个模型 = 12 行", len(challenge) == 12 and len(pairs) == 6,
          f"{len(challenge)} 行 / {len(pairs)} 对")
    categories = {row["category"] for row in challenge}
    check("覆盖否定、转折、同义改写三类",
          {"否定表达", "转折表达", "保持含义的改写"} <= categories
          or {"negation", "contrast", "paraphrase"} <= categories,
          str(sorted(categories)))
    presets = read_json(DATA / "challenge_pairs.json")["pairs"]
    check("与预置样本 ID 一致", {p["id"] for p in presets} == pairs, str(sorted({p["id"] for p in presets})))

    section("[10] 错误案例分析 error_cases.md")
    case_text = (EXP / "error_cases.md").read_text(encoding="utf-8")
    case_count = case_text.count("## 案例")
    check("至少 5 条案例（实际 7 条）", case_count >= 5, f"{case_count} 条")
    predicted_ids = {row["sample_id"] for row in predictions}
    cited = {token for token in case_text.split() if token.startswith("test-")}
    missing = [token.strip("，。、）") for token in cited if token.strip("，。、）") not in predicted_ids]
    check("案例引用的样本 ID 都出自测试集", not missing, str(missing[:3]))

    total = _passed + len(_failed)
    print("\n" + "=" * 60)
    if _failed:
        print(f"材料一致性自检未通过：{_passed}/{total} 项通过，以下对不上：")
        for name in _failed:
            print(f"  - {name}")
        return 1
    print(f"材料一致性自检全部通过：{total}/{total} 项")
    print("交付物里的每个数字都能从原始数据重新算出来。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
