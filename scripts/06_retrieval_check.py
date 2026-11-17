#!/usr/bin/env python
"""阶段三 · 相似影评检索的人工检查与 Precision@5 计算

执行顺序：第 6 步（需先运行 01、05）
用法：
    # 1) 生成 5 条查询的 Top-5 结果与待标注模板
    python scripts/06_retrieval_check.py --emit
    # 2) 人工在 experiments/retrieval_check.csv 里逐条填 relevant / reason（共 25 条）
    # 3) 计算 Precision@5
    python scripts/06_retrieval_check.py --score

判据（任务书 5.2）：
    相关性以「是否表达查询的主要观点」为依据，不能只看是否出现相同单词。
    每条查询的 Precision@5 = 前 5 条中相关结果数 / 5，再对 5 条查询取平均。

产物：
    experiments/retrieval_results.csv    自动生成的 Top-5（含相似度与 ID）
    experiments/retrieval_check.csv      人工判断记录（25 条）
    experiments/retrieval_top5.md        完整原文，供人工阅读判断
    experiments/retrieval_metrics.json   Precision@5 计算结果
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common import config  # noqa: E402

RESULTS_CSV = config.EXPERIMENTS_DIR / "retrieval_results.csv"
CHECK_CSV = config.EXPERIMENTS_DIR / "retrieval_check.csv"
TOP5_MD = config.EXPERIMENTS_DIR / "retrieval_top5.md"
METRICS_JSON = config.EXPERIMENTS_DIR / "retrieval_metrics.json"


def load_queries() -> list[dict]:
    path = config.DATA_DIR / "retrieval_queries.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["queries"]


def emit() -> None:
    """跑 5 条查询，输出 Top-5 与待标注模板。"""
    from backend.artifacts import Artifacts

    config.EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    art = Artifacts()
    art.load()
    if art.embedder is None or art.embeddings is None:
        raise SystemExit(f"向量资源未就绪：{art.status.get('embedder')}")

    queries = load_queries()
    rows = []
    md = [
        "# 5 条查询的 Top-5 结果（完整原文，供人工判断相关性）",
        "",
        "判断依据：这条影评是否在谈论查询所指的那个方面（演技 / 剧情 / 节奏 / 配乐 / 台词），",
        "并且观点与查询一致或相反都算「相关」——相关指的是**话题相关**，不是情感相同。",
        "",
    ]
    for query in queries:
        results = art.search(query["text"], top_k=config.TOP_K)
        md += [
            f"## {query['id']} · {query['topic']}",
            "",
            f"> 查询：{query['text']}",
            "",
        ]
        for item in results:
            rows.append({
                "query_id": query["id"],
                "topic": query["topic"],
                "rank": item["rank"],
                "pool_id": item["pool_id"],
                "sample_id": item["sample_id"],
                "similarity": item["similarity"],
                "dataset_label": item["dataset_label_name"],
            })
            preview = " ".join(item["text"].split())
            md += [
                f"**#{item['rank']} {item['sample_id']}（相似度 {item['similarity']:.4f}，"
                f"数据集标签 {item['dataset_label_name']}，{item['word_len']} 词）**",
                "",
                preview[:1500] + ("……" if len(preview) > 1500 else ""),
                "",
            ]

    with RESULTS_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    with CHECK_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(["query_id", "topic", "rank", "sample_id", "similarity", "relevant", "reason"])
        for row in rows:
            writer.writerow([
                row["query_id"], row["topic"], row["rank"], row["sample_id"],
                row["similarity"], "", "",
            ])

    TOP5_MD.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"已生成 {RESULTS_CSV}")
    print(f"待标注模板 {CHECK_CSV}（共 {len(rows)} 行，请填写 relevant 列：相关/不相关，并写 reason）")
    print(f"完整原文 {TOP5_MD}")
    print()
    print("相似度与 ID 对应（可直接核对）：")
    for row in rows:
        print(f"  {row['query_id']} #{row['rank']}  {row['sample_id']}  {row['similarity']:.4f}  {row['dataset_label']}")


def score() -> None:
    """读取人工标注，计算 Precision@5。"""
    if not CHECK_CSV.exists():
        raise SystemExit(f"缺少 {CHECK_CSV}，请先运行 --emit 并完成人工标注")

    with CHECK_CSV.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    # 与自动结果比对，确认排序和 ID 没有被改错
    auto = {}
    if RESULTS_CSV.exists():
        with RESULTS_CSV.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                auto[(row["query_id"], row["rank"])] = (row["sample_id"], float(row["similarity"]))

    per_query: dict[str, dict] = {}
    errors: list[str] = []
    for row in rows:
        query_id = row["query_id"]
        try:
            relevant = row["relevant"].strip()
        except AttributeError:
            relevant = ""
        if relevant in {"相关", "1", "yes", "true", "相关（1）"}:
            is_relevant = True
        elif relevant in {"不相关", "0", "no", "false"}:
            is_relevant = False
        else:
            errors.append(f"{query_id} #{row['rank']} 的 relevant 未填写或无法识别：{relevant!r}")
            continue

        key = (query_id, row["rank"])
        if auto and key in auto:
            auto_id, auto_sim = auto[key]
            if auto_id != row["sample_id"]:
                errors.append(f"{query_id} #{row['rank']} 的 sample_id 与自动结果不一致")
            if abs(float(row["similarity"]) - auto_sim) > 1e-5:
                errors.append(f"{query_id} #{row['rank']} 的 similarity 与自动结果不一致")

        bucket = per_query.setdefault(
            query_id, {"query_id": query_id, "topic": row["topic"], "relevant": 0, "judged": 0, "items": []}
        )
        bucket["judged"] += 1
        bucket["relevant"] += int(is_relevant)
        bucket["items"].append({
            "rank": int(row["rank"]),
            "sample_id": row["sample_id"],
            "similarity": float(row["similarity"]),
            "relevant": is_relevant,
            "reason": row.get("reason", "").strip(),
        })

    if errors:
        raise SystemExit("标注校验未通过：\n  - " + "\n  - ".join(errors))

    if len(per_query) != 5:
        raise SystemExit(f"应有 5 条查询，实际 {len(per_query)} 条")
    for query_id, bucket in per_query.items():
        if bucket["judged"] != 5:
            raise SystemExit(f"{query_id} 应有 5 条判断，实际 {bucket['judged']} 条")
        bucket["precision_at_5"] = round(bucket["relevant"] / 5, 4)
        bucket["items"].sort(key=lambda x: x["rank"])

    average = round(sum(b["precision_at_5"] for b in per_query.values()) / len(per_query), 4)
    payload = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "judging_rule": "相关性以是否表达查询的主要观点为依据，不只看是否有相同单词；话题相关即算相关，不论情感正负",
        "top_k": 5,
        "queries": sorted(per_query.values(), key=lambda b: b["query_id"]),
        "mean_precision_at_5": average,
        "total_judgements": sum(b["judged"] for b in per_query.values()),
        "scope_note": "该结果只反映这 25 条人工判断，不代表完整检索能力。",
    }
    METRICS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{'查询':<6}{'主题':<10}{'相关/5':<8}{'P@5'}")
    for bucket in payload["queries"]:
        print(f"{bucket['query_id']:<6}{bucket['topic']:<10}{bucket['relevant']}/5      {bucket['precision_at_5']:.2f}")
    print(f"{'平均':<16}{'':<8}{average:.4f}")
    print(f"已写入 {METRICS_JSON}")


def main() -> None:
    parser = argparse.ArgumentParser(description="检索效果人工检查与 Precision@5")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--emit", action="store_true", help="生成 Top-5 结果与待标注模板")
    group.add_argument("--score", action="store_true", help="读取人工标注并计算 Precision@5")
    args = parser.parse_args()
    if args.emit:
        emit()
    else:
        score()


if __name__ == "__main__":
    main()
