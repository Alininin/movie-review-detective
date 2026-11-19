#!/usr/bin/env python
"""阶段一 · 数据获取、抽样、清洗、统计（影评资料库）

执行顺序：第 1 步（见 README「执行顺序」）
用法：
    python scripts/01_build_dataset.py
    python scripts/01_build_dataset.py --pool-source from_train_1000

设计要点（对应设计文档 3.1）：
  1. 用 Hugging Face Datasets 加载 stanfordnlp/imdb，确认 text 为影评、label=0 负面 / 1 正面。
  2. 训练集抽 1000 条（正负各 500），官方测试集抽 200 条（正负各 100）。
     抽样用固定随机种子 + 打乱候选索引后顺序扫描，**不取前若干条**。
  3. 清洗 HTML 换行标记与多余空白；检查空文本、重复文本、训练/测试重叠；
     被剔除的样本从同一来源继续向后补齐，处理数量全部记录。
  4. 保存样本 ID、原始行号、清洗后文本、真实标签、所属集合。
  5. 计算总数、类别数、平均长度与长度分布，注明长度口径（默认按词）。

产物（data/）：
    reviews.csv              1200 条（train 1000 + test 200）
    retrieval_pool.csv       500 条检索库
    sampling_list.csv        抽样清单（逐条：集合、样本 ID、原始行号、标签、是否采用）
    sampling_manifest.json   抽样口径与随机种子等元信息
    cleaning_report.json     清洗与重叠检查记录
    stats.json               统计结果（前端资料库页面直接读取本文件）
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import platform
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common import config  # noqa: E402
from common.text_clean import (  # noqa: E402
    clean_review_text,
    count_chars,
    count_words,
    dedup_key,
    is_blank,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("build_dataset")

# 长度分布的直方图分箱（单位：词）
HIST_BINS = [0, 25, 50, 75, 100, 150, 200, 250, 300, 350, 400, 500, 750, 1000, 2000]
REVIEWS_FIELDS = [
    "split",
    "sample_id",
    "original_index",
    "label",
    "label_name",
    "text",
    "char_len",
    "word_len",
]
POOL_FIELDS = [
    "pool_id",
    "sample_id",
    "original_index",
    "label",
    "label_name",
    "text",
    "char_len",
    "word_len",
]


# --------------------------------------------------------------------- 工具函数
def _percentile(sorted_values: list[float], q: float) -> float:
    """线性插值分位数，q 取 0~100。数据量小，不引入 numpy。"""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    pos = (len(sorted_values) - 1) * q / 100.0
    low = int(pos)
    high = min(low + 1, len(sorted_values) - 1)
    frac = pos - low
    return float(sorted_values[low]) * (1 - frac) + float(sorted_values[high]) * frac


def describe(values: list[int]) -> dict:
    """一组长度的描述统计。"""
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "mean": round(statistics.fmean(ordered), 2),
        "median": round(statistics.median(ordered), 2),
        "std": round(statistics.pstdev(ordered), 2),
        "min": ordered[0],
        "max": ordered[-1],
        "p25": round(_percentile(ordered, 25), 2),
        "p75": round(_percentile(ordered, 75), 2),
        "p90": round(_percentile(ordered, 90), 2),
        "p95": round(_percentile(ordered, 95), 2),
        "p99": round(_percentile(ordered, 99), 2),
    }


def histogram(values: list[int], bins: list[int]) -> dict:
    """按词数分箱统计。最后一箱向上开口。"""
    counts = [0] * (len(bins))
    labels = []
    for i in range(len(bins) - 1):
        for v in values:
            if bins[i] <= v < bins[i + 1]:
                counts[i] += 1
        labels.append(f"{bins[i]}-{bins[i + 1]}")
    overflow = sum(1 for v in values if v >= bins[-1])
    counts[-1] = overflow
    labels.append(f"{bins[-1]}+")
    return {"bin_edges": bins, "bin_labels": labels, "counts": counts}


def make_sample_id(split: str, original_index: int) -> str:
    """样本 ID = 集合前缀 + 原始行号，保证可追溯到 IMDB 原始数据。"""
    return f"{split}-{original_index:06d}"


def shuffled_candidates(indices: list[int], seed: str) -> list[int]:
    """按分组专属种子打乱候选索引。

    种子取 "总种子:集合:标签"，好处是某一组配额变化不会影响其它组的抽样结果。
    """
    import random

    order = list(indices)
    random.Random(seed).shuffle(order)
    return order


# --------------------------------------------------------------------- 主流程
def load_imdb():
    """加载数据集并校验字段与标签含义。"""
    from datasets import load_dataset

    endpoint = config.HF_ENDPOINT or "https://huggingface.co（默认官方站）"
    log.info("加载数据集 %s，镜像端点：%s", config.DATASET_ID, endpoint)
    ds = load_dataset(config.DATASET_ID)
    log.info("可用集合：%s", {k: v.num_rows for k, v in ds.items()})

    features = ds["train"].features
    if "text" not in features or "label" not in features:
        raise SystemExit(f"字段不符合预期：{list(features)}")

    label_feature = features["label"]
    names = list(getattr(label_feature, "names", []))
    log.info("label 取值含义：names=%s", names)
    if len(names) < 2:
        raise SystemExit(f"label 不是二分类 ClassLabel：{label_feature}")
    # IMDB: 0 = neg, 1 = pos；与本项目 LABEL_NAMES 一致
    if names[0] in {"neg", "negative"} and names[1] in {"pos", "positive"}:
        mapping_note = f"{names[0]} -> 0 -> negative，{names[1]} -> 1 -> positive（与设计文档一致）"
    else:
        raise SystemExit(f"标签顺序与预期不符，需人工确认：{names}")
    log.info("标签映射校验通过：%s", mapping_note)

    return ds, names, mapping_note


def draw_samples(
    rows,
    indices_by_label: dict[int, list[int]],
    quota: dict[str, int],
    split_name: str,
    seen: dict[str, tuple[str, str]],
    id_prefix: str,
) -> tuple[list[dict], list[dict], dict[str, int], dict[str, int]]:
    """从候选索引里扫描抽取样本，自动跨过空文本与重复样本。

    返回 (接受的样本, 被剔除记录, 各原因剔除计数, 各组实际扫描条数)。
    """
    accepted: list[dict] = []
    rejects: list[dict] = []
    reason_counts: dict[str, int] = {}
    scanned: dict[str, int] = {}

    for label_int, target in ((0, quota["negative"]), (1, quota["positive"])):
        label_name = config.LABEL_NAMES[label_int]
        group = f"{split_name}/{label_name}"
        candidates = shuffled_candidates(indices_by_label[label_int], f"{config.SEED}:{split_name}:{label_int}")

        taken = 0
        visited = 0
        for idx in candidates:
            if taken >= target:
                break
            visited += 1
            raw = rows[idx]["text"]
            cleaned = clean_review_text(raw)
            sample_id = make_sample_id(id_prefix, idx)

            if is_blank(cleaned):
                rejects.append(
                    {"split": split_name, "original_index": idx, "reason": "empty_text",
                     "detail": f"清洗后无可见字符（原始长度 {len(str(raw))}）"}
                )
                reason_counts["empty_text"] = reason_counts.get("empty_text", 0) + 1
                continue

            key = dedup_key(cleaned)
            if key in seen:
                prev_split, prev_id = seen[key]
                reason = "duplicate_within_split" if prev_split == split_name else "cross_split_overlap"
                rejects.append(
                    {"split": split_name, "original_index": idx, "reason": reason,
                     "detail": f"与 {prev_id} 文本相同"}
                )
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
                continue

            seen[key] = (split_name, sample_id)
            accepted.append(
                {
                    "split": split_name,
                    "sample_id": sample_id,
                    "original_index": idx,
                    "label": label_int,
                    "label_name": label_name,
                    "text": cleaned,
                    "char_len": count_chars(cleaned),
                    "word_len": count_words(cleaned),
                }
            )
            taken += 1

        scanned[group] = visited
        if taken < target:
            raise SystemExit(f"{group} 只抽到 {taken} 条，未达配额 {target}")
        log.info("%-16s 目标 %4d 条，扫描 %5d 条，剔除 %d 条", group, target, visited, visited - taken)

    return accepted, rejects, reason_counts, scanned


def build(args: argparse.Namespace) -> None:
    data_dir = config.DATA_DIR
    data_dir.mkdir(parents=True, exist_ok=True)

    ds, label_names, mapping_note = load_imdb()
    train_rows = ds["train"]
    test_rows = ds["test"]

    # 原始行数，写进清单便于核对
    raw_counts = {"train": train_rows.num_rows, "test": test_rows.num_rows}

    def indices_by_label(dataset_split) -> dict[int, list[int]]:
        """枚举每个类别在原始数据中的行号（与 CSV 行序一一对应）。"""
        buckets: dict[int, list[int]] = {0: [], 1: []}
        for i, label in enumerate(dataset_split["label"]):
            buckets[label].append(i)
        return buckets

    seen: dict[str, tuple[str, str]] = {}
    all_rejects: list[dict] = []
    reason_counts: dict[str, dict[str, int]] = {}
    scanned_all: dict[str, int] = {}

    # ---- 训练集 1000 条 ----
    train_acc, rej, rc, sc = draw_samples(
        train_rows, indices_by_label(train_rows), config.SPLIT_QUOTAS["train"],
        "train", seen, "train",
    )
    all_rejects += rej
    reason_counts["train"] = rc
    scanned_all.update(sc)

    # ---- 官方测试集 200 条（seen 里已含训练集，因此跨集合重复会自动剔除并从同一来源补齐）----
    test_acc, rej, rc, sc = draw_samples(
        test_rows, indices_by_label(test_rows), config.SPLIT_QUOTAS["test"],
        "test", seen, "test",
    )
    all_rejects += rej
    reason_counts["test"] = rc
    scanned_all.update(sc)

    train_rows_out = sorted(train_acc, key=lambda r: (r["label"], r["original_index"]))
    test_rows_out = sorted(test_acc, key=lambda r: (r["label"], r["original_index"]))
    reviews = train_rows_out + test_rows_out

    # ---- 检索库 500 条 ----
    used_train = [r["original_index"] for r in train_rows_out]
    used_test = [r["original_index"] for r in test_rows_out]
    pool_source = args.pool_source or config.RETRIEVAL_POOL_SOURCE
    if pool_source == "from_train_1000":
        pool_candidates = {label: [r["original_index"] for r in train_rows_out if r["label"] == label] for label in (0, 1)}
        pool_rows_source = train_rows
        pool_desc = "从 1000 条训练样本中固定选取（与训练集重叠，设计文档 5.1.1 的另一种读法）"
    elif pool_source == "split_excluded":
        buckets = indices_by_label(train_rows)
        exclude = set(used_train)
        pool_candidates = {label: [i for i in buckets[label] if i not in exclude] for label in (0, 1)}
        pool_rows_source = train_rows
        pool_desc = "从 IMDB train 中排除已抽作训练/测试的 1200 条后固定选取（与训练集、测试集均不重叠）"
    else:
        raise SystemExit(f"未知的 --pool-source：{pool_source}")

    pool_quota = {"negative": config.RETRIEVAL_POOL_SIZE // 2, "positive": config.RETRIEVAL_POOL_SIZE // 2}
    pool_acc, rej, rc, sc = draw_samples(
        pool_rows_source, pool_candidates, pool_quota, "pool", seen, "pool",
    )
    all_rejects += rej
    reason_counts["pool"] = rc
    scanned_all.update(sc)
    pool = sorted(pool_acc, key=lambda r: (r["label"], r["original_index"]))
    for i, row in enumerate(pool, start=1):
        row["pool_id"] = f"P{i:03d}"

    # ---- 写 reviews.csv ----
    with (data_dir / "reviews.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=REVIEWS_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in reviews:
            writer.writerow({k: row[k] for k in REVIEWS_FIELDS})

    # ---- 写 retrieval_pool.csv ----
    with (data_dir / "retrieval_pool.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=POOL_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in pool:
            writer.writerow({k: row[k] for k in POOL_FIELDS})

    # ---- 写 sampling_list.csv（抽样清单：采用与剔除都在里面）----
    with (data_dir / "sampling_list.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["split", "status", "sample_id", "original_index", "label", "label_name", "note"],
            lineterminator="\n",
        )
        writer.writeheader()
        for row in reviews:
            writer.writerow({
                "split": row["split"], "status": "used", "sample_id": row["sample_id"],
                "original_index": row["original_index"], "label": row["label"],
                "label_name": row["label_name"], "note": "",
            })
        for row in pool:
            writer.writerow({
                "split": "pool", "status": "used", "sample_id": row["sample_id"],
                "original_index": row["original_index"], "label": row["label"],
                "label_name": row["label_name"], "note": f"检索库 {row['pool_id']}",
            })
        for rej in all_rejects:
            writer.writerow({
                "split": rej["split"], "status": "rejected", "sample_id": "",
                "original_index": rej["original_index"], "label": "",
                "label_name": "", "note": f"{rej['reason']}: {rej['detail']}",
            })

    # 统计（剔除原因补齐为 0，便于报告直接引用「该项检查为 0 条」）
    REASONS = ("empty_text", "duplicate_within_split", "cross_split_overlap")
    reason_counts = {
        split: {reason: counts.get(reason, 0) for reason in REASONS}
        for split, counts in reason_counts.items()
    }

    def label_counts(rows: list[dict]) -> dict:
        out = {"negative": 0, "positive": 0}
        for row in rows:
            out[row["label_name"]] += 1
        return out

    words_all = [r["word_len"] for r in reviews]
    chars_all = [r["char_len"] for r in reviews]
    length_stats = {
        "train": {
            "word": describe([r["word_len"] for r in train_rows_out]),
            "char": describe([r["char_len"] for r in train_rows_out]),
        },
        "test": {
            "word": describe([r["word_len"] for r in test_rows_out]),
            "char": describe([r["char_len"] for r in test_rows_out]),
        },
        "retrieval_pool": {
            "word": describe([r["word_len"] for r in pool]),
            "char": describe([r["char_len"] for r in pool]),
        },
        "all": {"word": describe(words_all), "char": describe(chars_all)},
    }

    removed_total = {
        split: sum(v.values()) for split, v in reason_counts.items()
    }

    stats = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "dataset": {
            "id": config.DATASET_ID,
            "raw_split_sizes": raw_counts,
            "label_names": label_names,
            "label_mapping": {"0": "negative", "1": "positive"},
            "label_mapping_note": mapping_note,
        },
        "versions": versions(),
        "seed": config.SEED,
        "sampling_rule": "按 (集合, 标签) 各用一个独立随机种子打乱候选行号后顺序扫描，接受至配额满；剔除样本自动从同一来源继续补齐",
        "length_unit": {
            "primary": "word",
            "definition": "word = 按空白切分得到的词数；char = 字符数（换行按空格计）",
        },
        "totals": {
            "reviews": len(reviews),
            "train": len(train_rows_out),
            "test": len(test_rows_out),
            "retrieval_pool": len(pool),
        },
        "label_counts": {
            "train": label_counts(train_rows_out),
            "test": label_counts(test_rows_out),
            "retrieval_pool": label_counts(pool),
        },
        "length": length_stats,
        "histogram": {
            "unit": "word",
            "train": histogram([r["word_len"] for r in train_rows_out], HIST_BINS),
            "test": histogram([r["word_len"] for r in test_rows_out], HIST_BINS),
            "retrieval_pool": histogram([r["word_len"] for r in pool], HIST_BINS),
        },
        "cleaning": {
            "removed_by_reason": reason_counts,
            "removed_total": removed_total,
            "scanned_candidates": scanned_all,
        },
        "retrieval_pool_source": pool_source,
        "retrieval_pool_rule": pool_desc,
    }
    (data_dir / "stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ---- 抽样清单（元信息）----
    manifest = {
        "generated_at": stats["generated_at"],
        "dataset": config.DATASET_ID,
        "seed": config.SEED,
        "raw_split_sizes": raw_counts,
        "quotas": config.SPLIT_QUOTAS,
        "retrieval_pool": {
            "size": config.RETRIEVAL_POOL_SIZE,
            "source": pool_source,
            "rule": pool_desc,
            "quota": pool_quota,
        },
        "sampling_rule": stats["sampling_rule"],
        "id_rule": "sample_id = 集合前缀 + 下划线前的原始行号，例如 train-012345 表示 IMDB train 第 12345 行；pool-P123 表示检索库第 123 条",
        "samples": {
            "train": [{"sample_id": r["sample_id"], "original_index": r["original_index"], "label": r["label"]} for r in train_rows_out],
            "test": [{"sample_id": r["sample_id"], "original_index": r["original_index"], "label": r["label"]} for r in test_rows_out],
            "retrieval_pool": [{"pool_id": r["pool_id"], "sample_id": r["sample_id"], "original_index": r["original_index"], "label": r["label"]} for r in pool],
        },
        "requested_indices": {
            "train_excluded_from_pool": sorted(used_train),
            "test": sorted(used_test),
        },
        "rejected": all_rejects,
        "versions": stats["versions"],
    }
    (data_dir / "sampling_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ---- 清洗记录 ----
    cleaning_report = {
        "generated_at": stats["generated_at"],
        "what_was_cleaned": [
            "<br /> / <br> 换行标记 -> 换行符",
            "其它残留 HTML 标签 -> 空格",
            "多余空白（连续空格、制表符、不换行空格）压成单个空格",
            "每行首尾空白去除，空行丢弃",
            "控制字符与 BOM 去除，Unicode 统一为 NFKC 形式",
        ],
        "checks": {
            "empty_text": "清洗后无可见字符即判为空文本，剔除并从同一来源补齐",
            "duplicate_text": "去除全部空白并忽略大小写后比较，重复则剔除并补齐",
            "train_test_overlap": "训练集与测试集共用同一张已见文本表，测试集中与之重复的样本会记为 cross_split_overlap 并剔除补齐",
        },
        "removed_by_reason": reason_counts,
        "removed_total": removed_total,
        "scanned_candidates": scanned_all,
        "final_counts": {
            "train": len(train_rows_out),
            "test": len(test_rows_out),
            "retrieval_pool": len(pool),
        },
        "rejected_detail": all_rejects,
        "notes": [
            "IMDB 官方 train/test 本身不重叠；这里仍做一次实测，并把结果写入本文件。",
            f"检索库来源：{pool_desc}",
        ],
    }
    (data_dir / "cleaning_report.json").write_text(
        json.dumps(cleaning_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ---- 控制台小结 ----
    log.info("=" * 64)
    log.info("reviews.csv            %d 条（train %d / test %d）",
             len(reviews), len(train_rows_out), len(test_rows_out))
    log.info("retrieval_pool.csv     %d 条", len(pool))
    log.info("词数（train）         均值 %.1f，中位数 %.1f，最大 %d",
             length_stats["train"]["word"]["mean"],
             length_stats["train"]["word"]["median"],
             length_stats["train"]["word"]["max"])
    log.info("剔除样本              %s", removed_total)
    log.info("产物目录              %s", data_dir)
    log.info("=" * 64)


def versions() -> dict:
    """记录实际使用的软件版本，满足设计文档「保存版本或提交号」的要求。"""
    result = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }
    for module_name in ("datasets", "huggingface_hub", "numpy", "scikit_learn", "torch", "transformers"):
        try:
            module = __import__(module_name)
            result[module_name] = getattr(module, "__version__", "unknown")
        except Exception:  # noqa: BLE001 - 版本记录不应让脚本失败
            result[module_name] = "not installed"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="构建影评资料库（抽样、清洗、统计）")
    parser.add_argument(
        "--pool-source",
        choices=["split_excluded", "from_train_1000"],
        default=None,
        help="检索库来源：split_excluded（默认，与训练/测试不重叠）或 from_train_1000",
    )
    build(parser.parse_args())


if __name__ == "__main__":
    main()
