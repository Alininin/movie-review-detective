#!/usr/bin/env python
"""阶段三 · 相似影评检索的人工检查与 Precision@5 计算

执行顺序：第 6 步（需先运行 01、05）
用法：
    # 1) 生成 5 条查询的 Top-5 结果与待标注模板
    python scripts/06_retrieval_check.py --emit
    # 2) 人工在 experiments/retrieval_check.csv 里逐条填 relevant / reason（共 25 条）
    # 3) 计算 Precision@5
    python scripts/06_retrieval_check.py --score

判据（设计文档 5.2）：
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
REVIEW_MD = config.EXPERIMENTS_DIR / "retrieval_review.md"
EXCERPT_WORDS = 70


def load_pool_rows() -> dict[str, dict]:
    """按 sample_id 取回检索库原文，供复核单摘录使用。"""
    path = config.DATA_DIR / "retrieval_pool.csv"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as fh:
        return {row["sample_id"]: row for row in csv.DictReader(fh)}


def excerpt(text: str, words: int = EXCERPT_WORDS) -> str:
    tokens = str(text or "").split()
    if len(tokens) <= words:
        return " ".join(tokens)
    return " ".join(tokens[:words]) + " …"


def review() -> None:
    """把 25 条判断整理成一页复核单：查询、当前判断、理由、原文摘录、勾选位。

    复核的人不需要同时开 CSV 和原文文件：一页里既能看到「现在判的是什么」，
    也能看到「这条影评到底在说什么」，改完再回 CSV 里填即可。
    """
    if not CHECK_CSV.exists():
        raise SystemExit(f"缺少 {CHECK_CSV}，请先运行 --emit 生成待标注模板")

    with CHECK_CSV.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    pool = load_pool_rows()
    queries = {q["id"]: q for q in load_queries()}

    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["query_id"], []).append(row)
    for items in grouped.values():
        items.sort(key=lambda r: int(r["rank"]))

    def is_relevant(value: str) -> bool:
        return value.strip() in {"相关", "1", "yes", "true", "相关（1）"}

    lines = [
        "# 25 条检索相关性复核单",
        "",
        "判据：**相关性以是否表达查询的主要观点为依据，不能只看有没有相同单词**；",
        "话题相关即算相关，情感正负都算（夸演技和骂演技都算「演技相关」）。",
        "",
        "怎么用：逐条读摘录（或点开对应 ID 看全文），在心里给出判断，",
        "和「当前判断」不一致时，记下要说的话；改完 `experiments/retrieval_check.csv` 里",
        "的 `relevant`（相关 / 不相关）与 `reason` 两列，再跑 `--score` 重算。",
        "",
        "## 一眼看全：当前 25 条判断",
        "",
        "| 查询 | 主题 | 相关 / 5 | P@5 |",
        "|---|---|---|---|",
    ]

    summary = []
    for query_id in sorted(grouped):
        items = grouped[query_id]
        hit = sum(1 for item in items if is_relevant(item["relevant"]))
        summary.append((query_id, items[0]["topic"], hit))
        lines.append(f"| {query_id} | {items[0]['topic']} | {hit}/5 | {hit / 5:.2f} |")
    total = sum(hit for _, _, hit in summary)
    lines += [
        f"| **平均** | — | {total}/25 | {total / 25:.4f} |",
        "",
    ]

    for query_id in sorted(grouped):
        topic = grouped[query_id][0]["topic"]
        query_text = queries.get(query_id, {}).get("text", "（缺少查询原文）")
        lines += [f"## {query_id} · {topic}", "", f"> 查询：{query_text}", ""]

        for item in grouped[query_id]:
            sample_id = item["sample_id"]
            row = pool.get(sample_id, {})
            label = {"1": "正面", "0": "负面"}.get(str(row.get("label", "")), "未知")
            current = "相关" if is_relevant(item["relevant"]) else "不相关"
            lines += [
                f"**#{item['rank']} · {sample_id} · 相似度 {float(item['similarity']):.4f} · "
                f"数据集标签 {label} · {row.get('word_len', '?')} 词**",
                "",
                f"- 当前判断：**{current}**",
                f"- 当前理由：{item.get('reason', '').strip() or '（空）'}",
                f"- 原文摘录：{excerpt(row.get('text', ''))}",
                f"- 复核：☐ 保持　☐ 改为相关　☐ 改为不相关　备注：________",
                "",
            ]

    lines += [
        "---",
        "",
        "## 改完之后",
        "",
        "```bash",
        "# 1) 在 experiments/retrieval_check.csv 里改 relevant 与 reason",
        "# 2) 重算 Precision@5",
        ".venv/Scripts/python scripts/06_retrieval_check.py --score",
        "# 3) 结果写回 experiments/retrieval_metrics.json；若有文档引用了 P@5，记得同步",
        ".venv/Scripts/python scripts/06_retrieval_check.py --score",
        "```",
        "",
        "改完数字若与 `README.md` 里的「检索平均 Precision@5 = 0.7200」不一致，记得同步那一行。",
        "",
    ]

    REVIEW_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"{'查询':<6}{'主题':<10}{'相关/5':<8}{'P@5'}")
    for query_id, topic, hit in summary:
        print(f"{query_id:<6}{topic:<10}{hit}/5      {hit / 5:.2f}")
    print(f"{'平均':<16}{'':<8}{total / 25:.4f}")
    print(f"复核单已写入 {REVIEW_MD}")
    print("逐条勾选后，改 experiments/retrieval_check.csv 的 relevant / reason 两列，再跑 --score")



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
    group.add_argument("--review", action="store_true", help="生成一页式复核单（查询 + 当前判断 + 摘录）")
    args = parser.parse_args()
    if args.emit:
        emit()
    elif args.review:
        review()
    else:
        score()


if __name__ == "__main__":
    main()
