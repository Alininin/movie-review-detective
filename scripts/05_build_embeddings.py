#!/usr/bin/env python
"""阶段三 · 检索向量构建（MiniLM，提前生成并保存）

执行顺序：第 5 步（需先运行 01_build_dataset.py）
用法：
    python scripts/05_build_embeddings.py

关键约束（设计文档 5.1）：
  * 检索库 500 条来自 data/retrieval_pool.csv，保留样本 ID；
  * 使用 all-MiniLM-L6-v2 在 CPU 上**提前**生成向量并保存；
  * 长影评按模型默认截断（max_seq_length = 256 token），本脚本统计被截断的条数；
  * 后端启动时直接加载向量文件，查询时只编码新输入。

产物：
    data/embeddings.npy           500 × 384 的 float32 归一化向量
    data/embeddings_ids.json      向量行序与样本 ID 的对应关系
    experiments/embedding_build.json  构建参数、耗时、截断统计
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
from backend.artifacts import Embedder  # noqa: E402

BATCH_SIZE = 32


def load_pool() -> list[dict]:
    path = config.DATA_DIR / "retrieval_pool.csv"
    if not path.exists():
        raise SystemExit(f"缺少 {path}，请先运行 scripts/01_build_dataset.py")
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) != config.RETRIEVAL_POOL_SIZE:
        raise SystemExit(f"检索库应为 {config.RETRIEVAL_POOL_SIZE} 条，实际 {len(rows)} 条")
    return rows


def main() -> None:
    import numpy as np

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)

    rows = load_pool()
    texts = [row["text"] for row in rows]
    pool_ids = [row["sample_id"] for row in rows]
    print(f"检索库：{len(rows)} 条，最长 {max(len(t.split()) for t in texts)} 词")

    print("加载向量模型（CPU）……")
    embedder = Embedder()
    print(f"  模型 {embedder.model_id}，维度 {embedder.dimension}，max_seq_length={embedder.max_seq_length}，"
          f"加载耗时 {embedder.load_seconds:.2f}s")

    print(f"编码中（batch_size={BATCH_SIZE}）……")
    started = time.perf_counter()
    vectors = embedder.encode(texts, batch_size=BATCH_SIZE)
    encode_seconds = time.perf_counter() - started

    vectors = np.asarray(vectors, dtype="float32")
    norms = np.linalg.norm(vectors, axis=1)
    if not np.allclose(norms, 1.0, atol=1e-4):
        raise SystemExit(f"向量未归一化：范数范围 {norms.min():.4f}~{norms.max():.4f}")

    np.save(config.DATA_DIR / "embeddings.npy", vectors)

    # 统计被截断的影评条数（按模型自身的 tokenizer 计数）
    tokenizer = embedder.model.tokenizer
    token_counts = []
    saved_max = tokenizer.model_max_length
    tokenizer.model_max_length = 10**9  # 计数时放开上限，避免触发超长告警
    try:
        for text in texts:
            try:
                token_counts.append(len(tokenizer(text, truncation=False, add_special_tokens=True)["input_ids"]))
            except Exception:  # noqa: BLE001
                token_counts.append(None)
    finally:
        tokenizer.model_max_length = saved_max
    truncated = sum(1 for n in token_counts if n is not None and n > embedder.max_seq_length)
    valid = [n for n in token_counts if n is not None]

    payload = {
        "model_id": embedder.model_id,
        "dimension": embedder.dimension,
        "count": int(vectors.shape[0]),
        "dtype": "float32",
        "normalized": True,
        "normalization_note": "已归一化，检索时点积即为余弦相似度",
        "order": "行序与 data/retrieval_pool.csv 的数据行顺序一致（pool_id 升序 P001…P500）",
        "max_seq_length": embedder.max_seq_length,
        "truncation_policy": f"超过 {embedder.max_seq_length} token 的影评按模型默认截断，只编码前 {embedder.max_seq_length} 个 token",
        "pool_ids": pool_ids,
        "pool_row_count": len(rows),
        "built_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    (config.DATA_DIR / "embeddings_ids.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 重新加载一次，确认文件可读且行序对得上（D1 验收点）
    reloaded = np.load(config.DATA_DIR / "embeddings.npy")
    reloaded_ids = json.loads((config.DATA_DIR / "embeddings_ids.json").read_text(encoding="utf-8"))["pool_ids"]
    assert reloaded.shape == vectors.shape, "重新加载后形状不一致"
    assert np.allclose(reloaded, vectors), "重新加载后数值不一致"
    assert reloaded_ids == pool_ids, "ID 顺序与检索库不一致"

    build_report = {
        "generated_at": payload["built_at"],
        "model_id": embedder.model_id,
        "model_load_seconds": embedder.load_seconds,
        "encode_seconds": round(encode_seconds, 3),
        "per_item_ms": round(encode_seconds * 1000 / len(texts), 3),
        "batch_size": BATCH_SIZE,
        "device": "cpu",
        "count": int(vectors.shape[0]),
        "dimension": embedder.dimension,
        "embedding_file_bytes": (config.DATA_DIR / "embeddings.npy").stat().st_size,
        "token_stats": {
            "mean": round(sum(valid) / max(len(valid), 1), 1) if valid else None,
            "max": max(valid) if valid else None,
            "truncated_count": truncated,
            "max_seq_length": embedder.max_seq_length,
            "truncated_ratio": round(truncated / len(texts), 4),
        },
        "reload_check": "重新加载向量文件与 ID 文件，形状、数值、顺序三项一致",
        "versions": {"python": sys.version.split()[0]},
    }
    (config.EXPERIMENTS_DIR / "embedding_build.json").write_text(
        json.dumps(build_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("=" * 64)
    print(f"向量矩阵：{vectors.shape}  文件 {(config.DATA_DIR / 'embeddings.npy').stat().st_size / 1024:.0f} KB")
    print(f"编码耗时：{encode_seconds:.2f}s（每条 {encode_seconds * 1000 / len(texts):.2f}ms）")
    print(f"token 均值 {build_report['token_stats']['mean']}，最大 {build_report['token_stats']['max']}，"
          f"超过 {embedder.max_seq_length} token 的 {truncated} 条（{truncated / len(texts):.1%}）")
    print("重新加载校验：通过")


if __name__ == "__main__":
    main()
