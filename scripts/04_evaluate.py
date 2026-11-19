#!/usr/bin/env python
"""阶段二 · 统一评测：两个分类模型在同一份 200 条测试集上的比较

执行顺序：第 4 步（需先运行 01、02；若还没跑 03 也可直接跑本脚本）
用法：
    python scripts/04_evaluate.py

评测口径（设计文档 4.3）：
  * 同一份 200 条测试集（data/reviews.csv 中 split=test）；
  * 指标：Accuracy、Macro-F1、混淆矩阵；
  * 耗时：推理总耗时与平均每条耗时，且**模型加载时间单独记录**；
  * 记录 CPU、批大小、输入长度设置；
  * 逐条保存真实标签与两个模型的预测标签。

产物：
    experiments/metrics.json            指标、混淆矩阵、耗时、运行环境
    experiments/predictions_test.csv    200 条逐条预测
    experiments/confusion_matrix.png    混淆矩阵图
    experiments/error_cases_auto.md     错误样本清单（供人工写分析）
"""
from __future__ import annotations

import csv
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common import config  # noqa: E402
from backend.artifacts import HFSentiment, TfidfSentiment  # noqa: E402

LABELS = [0, 1]
LABEL_LABELS = ["negative", "positive"]


def load_test_split() -> list[dict]:
    path = config.DATA_DIR / "reviews.csv"
    if not path.exists():
        raise SystemExit(f"缺少 {path}，请先运行 scripts/01_build_dataset.py")
    rows = []
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["split"] != "test":
                continue
            rows.append(
                {
                    "sample_id": row["sample_id"],
                    "original_index": int(row["original_index"]),
                    "text": row["text"],
                    "label": int(row["label"]),
                    "label_name": row["label_name"],
                    "word_len": int(row["word_len"]),
                    "char_len": int(row["char_len"]),
                }
            )
    if len(rows) != 200:
        raise SystemExit(f"测试集应为 200 条，实际 {len(rows)} 条")
    return rows


def cpu_description() -> dict:
    return {
        "processor_identifier": os.environ.get("PROCESSOR_IDENTIFIER", "unknown"),
        "platform_processor": platform.processor() or "unknown",
        "machine": platform.machine(),
        "logical_cores": os.cpu_count(),
        "python": sys.version.split()[0],
        "torch_device": "cpu (device=-1)",
    }


def run_model(model, texts: list[str], name: str) -> dict:
    """顺序推理（批大小 = 1），逐条记录预测与耗时。"""
    predictions = []
    started = time.perf_counter()
    for index, text in enumerate(texts, start=1):
        result = model.predict(text)
        predictions.append(result)
        if index % 50 == 0:
            print(f"  {name}: {index}/{len(texts)}")
    total_seconds = time.perf_counter() - started
    return {
        "predictions": predictions,
        "total_seconds": round(total_seconds, 3),
        "per_item_ms": round(total_seconds * 1000 / len(texts), 3),
        "load_seconds": model.load_seconds,
    }


def compute_metrics(y_true: list[int], y_pred: list[int]) -> dict:
    from sklearn.metrics import (
        accuracy_score,
        confusion_matrix,
        f1_score,
        precision_recall_fscore_support,
    )

    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=LABELS, average=None, zero_division=0
    )
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
        "macro_f1": round(float(f1_score(y_true, y_pred, average="macro")), 6),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=LABELS).tolist(),
        "per_class": {
            LABEL_LABELS[i]: {
                "precision": round(float(precision[i]), 6),
                "recall": round(float(recall[i]), 6),
                "f1": round(float(f1[i]), 6),
                "support": int(support[i]),
            }
            for i in range(len(LABELS))
        },
        "confusion_matrix_axes": {
            "rows": "真实标签 [negative, positive]",
            "columns": "预测标签 [negative, positive]",
        },
    }


def plot_confusion(results: dict, path: Path, dark: bool = False) -> None:
    """画混淆矩阵。

    dark=False 输出白底图（放进项目报告，打印与 Word 里更清楚）；
    dark=True  输出深色图（给网页用，和「胶片放映厅」的界面配色一致）。
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    # 中文标签需要中文字体，否则图上会出现方块
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    if dark:
        # 深色版用「暗褐 → 暖金」的渐变，避免白底格子在暗色界面上刺眼
        from matplotlib.colors import LinearSegmentedColormap

        bg = "#131110"
        ink = "#f4eee2"
        muted = "#948a79"
        cmap = LinearSegmentedColormap.from_list(
            "film_gold", ["#17130f", "#4a3a1e", "#a8802f", "#f3d493"]
        )
    else:
        bg = None
        ink = "#111827"
        muted = "#4b5563"
        cmap = "Blues"

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8), dpi=150)
    if dark:
        fig.patch.set_facecolor(bg)
    for ax, key in zip(axes, ["tfidf", "distilbert"]):
        matrix = np.array(results[key]["metrics"]["confusion_matrix"])
        image = ax.imshow(matrix, cmap=cmap)
        ax.set_title(
            f"{results[key]['display_name']}\n"
            f"Acc={results[key]['metrics']['accuracy']:.4f}  "
            f"Macro-F1={results[key]['metrics']['macro_f1']:.4f}",
            color=ink,
        )
        ax.set_xticks([0, 1], [f"预测负面", f"预测正面"])
        ax.set_yticks([0, 1], [f"真实负面", f"真实正面"])
        if dark:
            ax.set_facecolor(bg)
            ax.tick_params(colors=muted)
            for spine in ax.spines.values():
                spine.set_color("#3a3128")
        maximum = float(matrix.max()) if matrix.size and matrix.max() else 1.0
        for i in range(2):
            for j in range(2):
                ratio = float(matrix[i, j]) / maximum
                if dark:
                    # 格子越亮，字越深，保证每个数字都看得清
                    text_color = "#1b1206" if ratio > 0.55 else ink
                else:
                    text_color = "white" if ratio > 0.5 else "black"
                ax.text(j, i, str(matrix[i, j]), ha="center", va="center",
                        color=text_color, fontsize=13)
        colorbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
        if dark:
            colorbar.ax.tick_params(colors=muted)
            colorbar.outline.set_edgecolor("#3a3128")
    fig.suptitle("测试集混淆矩阵（200 条，CPU 推理）", fontsize=12, color=ink if dark else "black")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor=bg if dark else "white")
    plt.close(fig)


def replot_from_metrics() -> None:
    """只重画混淆矩阵，不重新跑模型、不改动 metrics.json。

    用途：改了配色之后重新生成图片，指标文件保持原样（避免「为了好看而重跑评测」）。
    """
    import json

    metrics = json.loads((config.EXPERIMENTS_DIR / "metrics.json").read_text(encoding="utf-8"))
    results = {
        key: {
            "display_name": metrics["models"][key]["display_name"],
            "metrics": {
                "confusion_matrix": metrics["models"][key]["confusion_matrix"],
                "accuracy": metrics["models"][key]["accuracy"],
                "macro_f1": metrics["models"][key]["macro_f1"],
            },
        }
        for key in ("tfidf", "distilbert")
    }
    plot_confusion(results, config.EXPERIMENTS_DIR / "confusion_matrix.png")
    plot_confusion(results, config.EXPERIMENTS_DIR / "confusion_matrix_dark.png", dark=True)
    print("已重画混淆矩阵：experiments/confusion_matrix.png（报告用）、"
          "experiments/confusion_matrix_dark.png（网页用）")


def main() -> None:
    config.EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    test_rows = load_test_split()
    texts = [row["text"] for row in test_rows]
    y_true = [row["label"] for row in test_rows]
    print(f"测试集：{len(test_rows)} 条（负面 {y_true.count(0)} / 正面 {y_true.count(1)}）")

    print("加载传统模型……")
    tfidf = TfidfSentiment()
    print(f"  加载耗时 {tfidf.load_seconds:.2f}s")

    print("加载预训练情感模型（首次会下载权重）……")
    hf = HFSentiment()
    print(f"  加载耗时 {hf.load_seconds:.2f}s")

    print("推理中（顺序执行，批大小 = 1）……")
    tfidf_run = run_model(tfidf, texts, "TF-IDF + LR")
    hf_run = run_model(hf, texts, "DistilBERT")

    y_pred_tfidf = [item["label"] for item in tfidf_run["predictions"]]
    y_pred_hf = [item["label"] for item in hf_run["predictions"]]

    agreement = sum(1 for a, b in zip(y_pred_tfidf, y_pred_hf) if a == b) / len(y_true)

    results = {
        "tfidf": {
            "display_name": "TF-IDF + 逻辑回归",
            "model_id": "sklearn Pipeline(TfidfVectorizer, LogisticRegression)",
            "metrics": compute_metrics(y_true, y_pred_tfidf),
            "timing": {
                "model_load_seconds": tfidf_run["load_seconds"],
                "inference_total_seconds": tfidf_run["total_seconds"],
                "per_item_ms": tfidf_run["per_item_ms"],
            },
            "predictions": tfidf_run["predictions"],
        },
        "distilbert": {
            "display_name": "DistilBERT SST-2",
            "model_id": config.SENTIMENT_MODEL_ID,
            "metrics": compute_metrics(y_true, y_pred_hf),
            "timing": {
                "model_load_seconds": hf_run["load_seconds"],
                "inference_total_seconds": hf_run["total_seconds"],
                "per_item_ms": hf_run["per_item_ms"],
            },
            "predictions": hf_run["predictions"],
        },
    }

    tokens = [p.get("input_tokens") for p in hf_run["predictions"]]
    truncated_count = sum(1 for p in hf_run["predictions"] if p.get("truncated"))

    metrics = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "evaluated_on": {
            "split": "test",
            "samples": len(test_rows),
            "label_counts": {"negative": y_true.count(0), "positive": y_true.count(1)},
            "source": "data/reviews.csv (split=test)",
        },
        "run_config": {
            "cpu": cpu_description(),
            "batch_size": 1,
            "execution": "顺序执行，逐条推理",
            "tfidf": {
                "truncation": "无（TF-IDF 使用全文）",
                "feature_settings": "max_features=10000, ngram_range=(1,2), min_df=2, sublinear_tf=True",
            },
            "distilbert": {
                "truncation": f"truncation=True, max_length={config.SENTIMENT_MAX_LENGTH}",
                "device": "cpu",
                "token_count": {
                    "mean": round(sum(t for t in tokens if t) / max(len([t for t in tokens if t]), 1), 1),
                    "max": max([t for t in tokens if t], default=None),
                    "truncated_samples": truncated_count,
                },
            },
        },
        "models": {
            "tfidf": {
                "display_name": results["tfidf"]["display_name"],
                "model_id": results["tfidf"]["model_id"],
                **results["tfidf"]["metrics"],
                "timing": results["tfidf"]["timing"],
            },
            "distilbert": {
                "display_name": results["distilbert"]["display_name"],
                "model_id": results["distilbert"]["model_id"],
                **results["distilbert"]["metrics"],
                "timing": results["distilbert"]["timing"],
            },
        },
        "agreement_rate": round(agreement, 6),
        "notes": [
            "分类分数是模型输出，不代表判断正确的概率。",
            "模型加载时间与推理时间分开记录。",
            "同一份测试集只用于评测，未参与任何参数选择。",
            "截断策略：DistilBERT 只使用前 256 个 token，超出部分未参与判断。",
        ],
    }
    (config.EXPERIMENTS_DIR / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ---- 逐条预测 ----
    with (config.EXPERIMENTS_DIR / "predictions_test.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow([
            "sample_id", "original_index", "true_label", "true_label_name",
            "tfidf_label", "tfidf_label_name", "tfidf_score",
            "distilbert_label", "distilbert_label_name", "distilbert_score",
            "tfidf_correct", "distilbert_correct", "models_agree",
            "word_len", "char_len",
        ])
        for row, tfidf_pred, hf_pred in zip(test_rows, results["tfidf"]["predictions"], results["distilbert"]["predictions"]):
            writer.writerow([
                row["sample_id"], row["original_index"], row["label"], row["label_name"],
                tfidf_pred["label"], tfidf_pred["label_name"], tfidf_pred["score"],
                hf_pred["label"], hf_pred["label_name"], hf_pred["score"],
                int(tfidf_pred["label"] == row["label"]),
                int(hf_pred["label"] == row["label"]),
                int(tfidf_pred["label"] == hf_pred["label"]),
                row["word_len"], row["char_len"],
            ])

    plot_confusion(results, config.EXPERIMENTS_DIR / "confusion_matrix.png")
    plot_confusion(results, config.EXPERIMENTS_DIR / "confusion_matrix_dark.png", dark=True)

    # ---- 错误样本清单（供人工写分析）----
    lines = [
        "# 错误与分歧样本清单（自动生成）",
        "",
        "本文件由 `scripts/04_evaluate.py` 自动生成，只提供事实数据；",
        "**逐条的原因解释见 `experiments/error_cases.md`（人工撰写）**。",
        "",
        f"- 生成时间：{metrics['generated_at']}",
        f"- 测试集：200 条",
        f"- TF-IDF + LR：Acc {results['tfidf']['metrics']['accuracy']:.4f} / Macro-F1 {results['tfidf']['metrics']['macro_f1']:.4f}",
        f"- DistilBERT：Acc {results['distilbert']['metrics']['accuracy']:.4f} / Macro-F1 {results['distilbert']['metrics']['macro_f1']:.4f}",
        f"- 两模型一致率：{agreement:.4f}",
        "",
        "## 一、两模型都判错的样本",
        "",
        "| # | 样本 ID | 真实 | TF-IDF | DistilBERT | 词数 |",
        "|---|---|---|---|---|---|",
    ]
    both_wrong = [
        (row, t, h) for row, t, h in zip(test_rows, results["tfidf"]["predictions"], results["distilbert"]["predictions"])
        if t["label"] != row["label"] and h["label"] != row["label"]
    ]
    for i, (row, t, h) in enumerate(both_wrong[:15], start=1):
        lines.append(
            f"| {i} | {row['sample_id']} | {row['label_name']} | {t['label_name']} | {h['label_name']} | {row['word_len']} |"
        )
    lines += ["", "## 二、两模型意见不一致的样本", "",
              "| # | 样本 ID | 真实 | TF-IDF | DistilBERT | 谁对 | 词数 |",
              "|---|---|---|---|---|---|---|"]
    disagree = [
        (row, t, h) for row, t, h in zip(test_rows, results["tfidf"]["predictions"], results["distilbert"]["predictions"])
        if t["label"] != h["label"]
    ]
    for i, (row, t, h) in enumerate(disagree[:15], start=1):
        winner = "TF-IDF" if t["label"] == row["label"] else ("DistilBERT" if h["label"] == row["label"] else "都错")
        lines.append(
            f"| {i} | {row['sample_id']} | {row['label_name']} | {t['label_name']} | {h['label_name']} | {winner} | {row['word_len']} |"
        )
    lines += ["", "## 三、超长样本（超过 256 token 会被截断）", "",
              "| 样本 ID | token 数 | 真实 | TF-IDF | DistilBERT |", "|---|---|---|---|---|"]
    for row, t, h, tk in zip(test_rows, results["tfidf"]["predictions"], results["distilbert"]["predictions"], tokens):
        if tk and tk > config.SENTIMENT_MAX_LENGTH:
            lines.append(f"| {row['sample_id']} | {tk} | {row['label_name']} | {t['label_name']} | {h['label_name']} |")
    (config.EXPERIMENTS_DIR / "error_cases_auto.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("=" * 64)
    for key in ("tfidf", "distilbert"):
        m = results[key]["metrics"]
        t = results[key]["timing"]
        print(f"{results[key]['display_name']:<20} Acc {m['accuracy']:.4f}  Macro-F1 {m['macro_f1']:.4f}  "
              f"加载 {t['model_load_seconds']:.2f}s  推理 {t['inference_total_seconds']:.2f}s  "
              f"每条 {t['per_item_ms']:.2f}ms")
    print(f"两模型一致率 {agreement:.4f}")
    print(f"都判错 {len(both_wrong)} 条；意见不一致 {len(disagree)} 条；超 256 token {truncated_count} 条")
    print(f"产物目录 {config.EXPERIMENTS_DIR}")


if __name__ == "__main__":
    import sys

    if "--replot" in sys.argv:
        # 只重画图片（改配色时用），不重新推理、不改 metrics.json
        replot_from_metrics()
    else:
        main()
