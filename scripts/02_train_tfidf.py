#!/usr/bin/env python
"""阶段二 · 传统模型：TF-IDF + 逻辑回归训练

执行顺序：第 2 步（需先运行 01_build_dataset.py）
用法：
    python scripts/02_train_tfidf.py

关键约束（设计文档 4.1）：
  * TF-IDF **只在训练集上 fit**，测试集不参与词表与权重学习；
  * 特征转换器与分类器一并保存，可重新加载；
  * 输出标签与分类分数。

产物：
    models/tfidf_lr.joblib    完整 Pipeline（TfidfVectorizer + LogisticRegression）
    models/tfidf_meta.json    训练配置、词表规模、耗时、版本
"""
from __future__ import annotations

import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common import config  # noqa: E402

MODEL_PATH = config.MODELS_DIR / "tfidf_lr.joblib"
META_PATH = config.MODELS_DIR / "tfidf_meta.json"

# 超参数固定写在这里，并在写入 meta 时记录；不得用测试集反复挑选
TFIDF_PARAMS = {
    "max_features": 10000,
    "ngram_range": (1, 2),
    "min_df": 2,
    "sublinear_tf": True,
}
LR_PARAMS = {
    "max_iter": 1000,
    "random_state": config.SEED,
    "solver": "lbfgs",
    "C": 1.0,
}


def load_train_split() -> tuple[list[str], list[int]]:
    """只读取 train 集合。测试集在这个脚本里不会被打开，从流程上杜绝数据泄露。"""
    path = config.DATA_DIR / "reviews.csv"
    if not path.exists():
        raise SystemExit(f"缺少 {path}，请先运行 scripts/01_build_dataset.py")
    texts: list[str] = []
    labels: list[int] = []
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["split"] != "train":
                continue
            texts.append(row["text"])
            labels.append(int(row["label"]))
    if not texts:
        raise SystemExit("reviews.csv 中没有 train 集合的样本")
    return texts, labels


def main() -> None:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    import joblib
    import sklearn

    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    texts, labels = load_train_split()
    positive = sum(labels)
    print(f"训练集：{len(texts)} 条（正面 {positive} / 负面 {len(labels) - positive}）")

    pipeline = Pipeline(
        [
            ("tfidf", TfidfVectorizer(**TFIDF_PARAMS)),
            ("classifier", LogisticRegression(**LR_PARAMS)),
        ]
    )

    started = time.perf_counter()
    pipeline.fit(texts, labels)
    train_seconds = time.perf_counter() - started

    vectorizer: TfidfVectorizer = pipeline.named_steps["tfidf"]
    vocab_size = len(vectorizer.vocabulary_)
    feature_dim = len(vectorizer.get_feature_names_out())

    # 训练集自评——仅用于确认模型没退化，不作为最终指标（最终指标见 04_evaluate.py）
    train_pred = pipeline.predict(texts)
    train_acc = sum(int(p == y) for p, y in zip(train_pred, labels)) / len(labels)

    joblib.dump(pipeline, MODEL_PATH, compress=3)

    meta = {
        "trained_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "artifact": str(MODEL_PATH.relative_to(ROOT)),
        "artifact_bytes": MODEL_PATH.stat().st_size,
        "training_samples": len(texts),
        "label_counts": {"negative": len(labels) - positive, "positive": positive},
        "tfidf_params": {**TFIDF_PARAMS, "ngram_range": list(TFIDF_PARAMS["ngram_range"])},
        "logreg_params": LR_PARAMS,
        "vocabulary_size": vocab_size,
        "feature_dimension": feature_dim,
        "train_seconds": round(train_seconds, 2),
        "train_accuracy": round(train_acc, 4),
        "data_leakage_note": "TfidfVectorizer 仅在 1000 条训练样本上 fit；测试集只做 transform",
        "versions": {
            "python": sys.version.split()[0],
            "scikit-learn": sklearn.__version__,
            "joblib": joblib.__version__,
        },
    }
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"词表规模：{vocab_size}   特征维度：{feature_dim}")
    print(f"训练耗时：{train_seconds:.2f} s   训练集准确率（仅供参考）：{train_acc:.4f}")
    print(f"模型已保存：{MODEL_PATH}（{MODEL_PATH.stat().st_size / 1024:.0f} KB）")
    print(f"配置已保存：{META_PATH}")


if __name__ == "__main__":
    main()
