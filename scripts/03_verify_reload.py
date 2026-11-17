#!/usr/bin/env python
"""阶段二 · 传统模型重新加载验证（对应评分点 B2）

执行顺序：第 3 步（需先运行 02_train_tfidf.py）
用法：
    python scripts/03_verify_reload.py

验证内容：
  1. 模型文件存在且能加载；
  2. Pipeline 中特征转换器（tfidf）与分类器（classifier）都在；
  3. 加载后对同一批文本能输出标签与分类分数；
  4. 连续两次加载的预测结果完全一致（可复现）。

这不参与最终指标计算，只证明"保存下来的模型可以重新加载并直接预测"。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common import config  # noqa: E402

MODEL_PATH = config.MODELS_DIR / "tfidf_lr.joblib"

# 覆盖正负、否定、转折、长短文本的固定验证集
CASES = [
    ("正面明确", "A wonderful film with a warm, generous heart."),
    ("负面明确", "A dull, joyless mess that wastes a great cast."),
    ("否定句", "The movie was not good at all."),
    ("转折句", "The acting was excellent, but the story was boring."),
    ("短文本", "Loved it."),
    ("长文本", " ".join(["The cinematography was stunning and the performances were superb."] * 20)),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_model():
    import joblib

    return joblib.load(MODEL_PATH)


def predict_all(model) -> list[dict]:
    outputs = []
    for label, text in CASES:
        probabilities = model.predict_proba([text])[0]
        predicted = int(model.predict([text])[0])
        outputs.append(
            {
                "case": label,
                "text": text if len(text) <= 80 else text[:77] + "...",
                "label": predicted,
                "label_name": config.LABEL_NAMES[predicted],
                "scores": {
                    "negative": round(float(probabilities[0]), 6),
                    "positive": round(float(probabilities[1]), 6),
                },
            }
        )
    return outputs


def main() -> None:
    if not MODEL_PATH.exists():
        raise SystemExit(f"缺少模型文件 {MODEL_PATH}，请先运行 scripts/02_train_tfidf.py")

    print(f"模型文件：{MODEL_PATH}")
    print(f"文件大小：{MODEL_PATH.stat().st_size / 1024:.0f} KB")
    print(f"SHA256  ：{sha256(MODEL_PATH)}")

    print("\n第一次加载……")
    model_a = load_model()
    steps = list(model_a.named_steps)
    print(f"  Pipeline 步骤：{steps}")
    if "tfidf" not in model_a.named_steps or "classifier" not in model_a.named_steps:
        raise SystemExit("Pipeline 缺少 tfidf 或 classifier，模型文件不完整")
    vectorizer = model_a.named_steps["tfidf"]
    print(f"  词表规模：{len(vectorizer.vocabulary_)}，特征维度：{len(vectorizer.get_feature_names_out())}")
    outputs_a = predict_all(model_a)

    print("\n第二次加载（验证可复现）……")
    model_b = load_model()
    outputs_b = predict_all(model_b)

    print(f"\n{'用例':<10}{'预测':<12}{'负面分数':<14}{'正面分数':<14}预测文本")
    for item in outputs_a:
        print(
            f"{item['case']:<10}{item['label_name']:<12}"
            f"{item['scores']['negative']:<14}{item['scores']['positive']:<14}{item['text']}"
        )

    identical = outputs_a == outputs_b
    print(f"\n两次加载预测完全一致：{identical}")

    report = {
        "model_path": str(MODEL_PATH.relative_to(ROOT)),
        "model_bytes": MODEL_PATH.stat().st_size,
        "model_sha256": sha256(MODEL_PATH),
        "pipeline_steps": steps,
        "vocabulary_size": len(vectorizer.vocabulary_),
        "feature_dimension": len(vectorizer.get_feature_names_out()),
        "cases": outputs_a,
        "reload_identical": identical,
    }
    out = config.EXPERIMENTS_DIR / "reload_check.json"
    config.EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"验证结果已写入：{out}")

    if not identical:
        raise SystemExit("两次加载的预测结果不一致，模型不可复现")
    print("\n结论：模型可重新加载，输出标签与分类分数正常，结果可复现。")


if __name__ == "__main__":
    main()
