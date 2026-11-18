"""可解释性与分歧样本接口（在任务书要求之外自带的两项扩展）。

这两个接口不改变任何评测结论，只是把「模型已经算出来的东西」摊开给人看：

  * `POST /api/explain`   把 TF-IDF + 逻辑回归的线性贡献算出来，说明哪些词把这条影评
                          推向了正面/负面。数值完全来自训练好的模型，不是事后编的理由。
  * `GET  /api/divergence` 把测试集里两个模型意见不一致的样本单独列出来，供案例分析使用。
                          样本与标签来自 `experiments/predictions_test.csv`，文本来自
                          `data/reviews.csv`，两者按 sample_id 对齐。

注意口径：贡献值不是概率；分歧样本也不是「模型出错」的同义词（对错由数据集标签决定，
而数据集标签本身可能有噪声）。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.artifacts import ModelUnavailable, artifacts
from backend.schemas import ExplainRequest, validate_text

router = APIRouter(tags=["可解释性与分歧样本"])


@router.post("/api/explain", summary="TF-IDF + 逻辑回归：哪些词影响了这条判断")
def explain(payload: ExplainRequest) -> dict:
    try:
        text = validate_text(payload.text, "影评文本")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if artifacts.tfidf is None:
        raise HTTPException(
            status_code=503,
            detail="传统模型未就绪，无法给出词级解释。请先运行 scripts/02_train_tfidf.py。",
        )

    try:
        result = artifacts.tfidf.explain(text, top_n=payload.top_n)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"词贡献计算失败：{exc}") from exc

    if not result["terms"]:
        return {
            **result,
            "empty_note": (
                "这条文本里没有任何词出现在训练集词表中（1000 条影评、min_df=2），"
                "所以模型没有可用依据，判断实际上来自截距项。这种现象本身就是一个可分析的案例。"
            ),
        }
    return result


@router.get("/api/divergence", summary="两模型意见不一致的测试样本")
def divergence(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    winner: str = Query(default="all", description="all / tfidf / distilbert：只看哪个模型判对"),
) -> dict:
    if not artifacts.predictions:
        raise HTTPException(
            status_code=503,
            detail="还没有逐条预测结果：请先运行 scripts/04_evaluate.py 生成 experiments/predictions_test.csv",
        )
    if winner not in {"all", "tfidf", "distilbert"}:
        raise HTTPException(status_code=400, detail="winner 只能是 all、tfidf 或 distilbert")

    # 两个模型预测不同时，真实标签只可能等于其中一方，所以每条分歧样本必定「一方对、一方错」，
    # 这里按「谁判对」分组，比按「是否一方错」分组更有信息量。
    items = artifacts.divergence
    tfidf_wins = sum(1 for item in items if item["tfidf_label"] == item["true_label"])
    distilbert_wins = len(items) - tfidf_wins
    if winner == "tfidf":
        items = [item for item in items if item["tfidf_label"] == item["true_label"]]
    elif winner == "distilbert":
        items = [item for item in items if item["distilbert_label"] == item["true_label"]]

    page = items[offset : offset + limit]
    detailed = []
    for item in page:
        detailed.append(
            {
                **item,
                "true_label_cn": "正面" if item["true_label"] == 1 else "负面",
                "tfidf_label_cn": "正面" if item["tfidf_label"] == 1 else "负面",
                "distilbert_label_cn": "正面" if item["distilbert_label"] == 1 else "负面",
                "tfidf_correct": item["tfidf_label"] == item["true_label"],
                "distilbert_correct": item["distilbert_label"] == item["true_label"],
                "text": (item["text"] or "")[:600],
            }
        )

    return {
        "total": len(items),
        "all_total": len(artifacts.divergence),
        "tfidf_wins": tfidf_wins,
        "distilbert_wins": distilbert_wins,
        "winner": winner,
        "offset": offset,
        "limit": limit,
        "items": detailed,
        "test_total": len(artifacts.predictions),
        "note": (
            "分歧样本来自 experiments/predictions_test.csv 的 200 条测试集，"
            "文本与真实标签来自 data/reviews.csv（按 sample_id 对齐）。"
            "两个模型预测不同时，真实标签只可能等于其中一方，所以每条分歧样本必定一方对、一方错；"
            "「不一致」说明的是两者偏差来源不同，不等于其中必有一个模型整体更差。"
        ),
    }
