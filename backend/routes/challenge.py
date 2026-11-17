"""模型挑战接口：原句与改写句并排比较两个模型。

任务书 5.3：6 对预置样本可查看或选择；也支持现场输入新句子对。
判断「预测变化是否合理」时，要以人工情感判断为准，
不能把所有预测变化都当成模型出错。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.artifacts import ModelUnavailable, artifacts
from backend.schemas import ChallengeRequest, validate_text

router = APIRouter(tags=["模型挑战"])


def _judge(expected: str | None, changed: bool) -> str:
    """按人工预期判断预测变化是否合理。"""
    if expected == "flip":
        return "合理（情感本应翻转，模型跟随变化）" if changed else "可疑（情感本应翻转，模型没有变化）"
    if expected == "stable":
        return "合理（只是换说法，模型保持稳定）" if not changed else "可疑（只是换说法，模型却翻转了）"
    return "无人工预期，仅供参考"


@router.get("/api/challenge/presets", summary="6 对预置样本")
def presets() -> dict:
    if not artifacts.challenge_pairs:
        raise HTTPException(status_code=503, detail="预置样本未加载：缺少 data/challenge_pairs.json")
    return {
        "pairs": artifacts.challenge_pairs,
        "categories": [
            {"key": "negation", "label": "否定表达"},
            {"key": "contrast", "label": "转折表达"},
            {"key": "paraphrase", "label": "保持含义的改写"},
        ],
        "note": "expected_change 是人工判断的情感走向：flip 表示应当翻转，stable 表示应当保持不变。",
    }


@router.post("/api/challenge", summary="比较一对句子在两个模型下的输出")
def challenge(payload: ChallengeRequest) -> dict:
    try:
        original = validate_text(payload.original, "原句")
        rewritten = validate_text(payload.rewritten, "改写句")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        left = artifacts.predict_both(original)
        right = artifacts.predict_both(rewritten)
    except ModelUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"{exc}。请稍后重试。") from exc

    preset = next(
        (
            pair
            for pair in artifacts.challenge_pairs
            if pair["original"].strip() == original and pair["rewritten"].strip() == rewritten
        ),
        None,
    )

    comparison = {}
    for key in ("tfidf", "distilbert"):
        changed = left[key]["label"] != right[key]["label"]
        comparison[key] = {
            "model": left[key]["model"],
            "original": left[key],
            "rewritten": right[key],
            "changed": changed,
            "delta_score": round(right[key]["score"] - left[key]["score"], 6),
            "judgement": _judge(preset["expected_change"] if preset else None, changed),
        }

    return {
        "original": original,
        "rewritten": rewritten,
        "preset_id": preset["id"] if preset else None,
        "match_note": "与预置样本一致，已按人工判断评估" if preset else "现场输入的句子对，无人工预期，只展示模型输出与变化",
        "comparison": comparison,
        "score_note": "score 为分类分数，不是判断正确的概率；边界句子上两个模型给出不同结果属于正常现象。",
    }
