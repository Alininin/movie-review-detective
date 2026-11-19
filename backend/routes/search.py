"""相似影评检索接口。

设计文档 5.1：
  * 向量在离线阶段已生成，接口只编码新输入；
  * 余弦相似度排序，返回 Top-5，不需要专门向量数据库；
  * 返回结果是「数据集原始标签」，与模型预测是两个概念。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.artifacts import ModelUnavailable, artifacts
from backend.schemas import SearchRequest, validate_text

router = APIRouter(tags=["相似影评检索"])


@router.post("/api/search", summary="按相似度检索 Top-5 影评")
def search(payload: SearchRequest) -> dict:
    try:
        query = validate_text(payload.query, "查询文本")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        results = artifacts.search(query, top_k=payload.top_k)
    except ModelUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail=f"{exc}。请先运行 scripts/05_build_embeddings.py 生成向量，或稍后重试。",
        ) from exc

    return {
        "query": query,
        "top_k": payload.top_k,
        "results": results,
        "note": "similarity 为余弦相似度，只表示向量夹角接近程度，不是准确率，也不代表影评观点一致。",
        "label_note": "dataset_label 是影评在 IMDB 数据集中的原始标签，不是模型对本次查询的预测。",
        "pool_size": len(artifacts.pool),
    }


@router.get("/api/search/queries", summary="预设的 5 条检索查询")
def preset_queries() -> dict:
    return {
        "queries": artifacts.retrieval_queries,
        "note": "这 5 条查询用于人工检查检索效果（Top-5 逐条判断相关/不相关）。",
    }
