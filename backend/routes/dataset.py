"""影评资料库接口：统计、分页浏览、按标签筛选。

数据全部来自 data/reviews.csv 与 data/stats.json，与离线脚本同源，
保证「网页统计与文件一致」（任务书 3.1 验收）。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.artifacts import artifacts
from common import config

router = APIRouter(tags=["影评资料库"])


@router.get("/api/dataset/stats", summary="数据集统计")
def dataset_stats() -> dict:
    if not artifacts.stats:
        raise HTTPException(status_code=503, detail="统计文件未加载：请先运行 scripts/01_build_dataset.py")
    return {
        **artifacts.stats,
        "source_file": "data/stats.json",
        "length_note": "长度以词（按空白切分）为主口径，同时给出字符数",
        "models": artifacts.status,
        "max_input_chars": config.MAX_INPUT_CHARS,
    }


@router.get("/api/reviews", summary="分页浏览影评，支持标签筛选、关键词搜索与长度区间")
def list_reviews(
    split: str = Query(default="all", description="train / test / all"),
    label: str = Query(default="all", description="all / 0 / 1"),
    keyword: str = Query(default="", max_length=200, description="文本关键词"),
    min_words: int = Query(default=0, ge=0, description="词数下限（含），用于长度分布图联动筛选"),
    max_words: int = Query(default=0, ge=0, description="词数上限（不含），0 表示不限"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
) -> dict:
    if not artifacts.reviews:
        raise HTTPException(status_code=503, detail="影评数据未加载：请先运行 scripts/01_build_dataset.py")
    if split not in {"all", "train", "test"}:
        raise HTTPException(status_code=400, detail="split 只能是 train、test 或 all")
    if label not in {"all", "0", "1"}:
        raise HTTPException(status_code=400, detail="label 只能是 all、0（负面）或 1（正面）")
    if max_words and min_words and max_words <= min_words:
        raise HTTPException(status_code=400, detail=f"词数区间不成立：下限 {min_words} 不小于上限 {max_words}")

    rows = artifacts.reviews
    if split != "all":
        rows = [row for row in rows if row["split"] == split]
    if label != "all":
        target = int(label)
        rows = [row for row in rows if row["label"] == target]
    if min_words:
        rows = [row for row in rows if row["word_len"] >= min_words]
    if max_words:
        rows = [row for row in rows if row["word_len"] < max_words]
    if keyword:
        needle = keyword.casefold()
        rows = [row for row in rows if needle in row["text"].casefold()]

    total = len(rows)
    pages = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    items = rows[start : start + page_size]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
        "filters": {
            "split": split,
            "label": label,
            "keyword": keyword,
            "min_words": min_words,
            "max_words": max_words,
        },
        "items": [
            {
                "sample_id": row["sample_id"],
                "split": row["split"],
                "original_index": row["original_index"],
                "label": row["label"],
                "label_name": row["label_name"],
                "label_cn": config.LABEL_CN[row["label"]],
                "word_len": row["word_len"],
                "char_len": row["char_len"],
                "text": row["text"],
            }
            for row in items
        ],
    }
