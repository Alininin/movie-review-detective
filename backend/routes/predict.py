"""情感分析接口：单条预测与 CSV 批量预测。

两条红线（任务书 6.2.1 / 6.2.6）：
  * 结果必须由后端真实推理产生，前端不得预写；
  * 返回的 score 是分类分数，不是「判断正确的概率」。
"""
from __future__ import annotations

import csv
import io
import time

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend import db
from backend.artifacts import ModelUnavailable, artifacts
from backend.schemas import PredictRequest, validate_text
from common import config
from common.text_clean import count_chars, count_words

router = APIRouter(tags=["情感分析"])


def _run_and_save(text: str, source: str = "single") -> dict:
    started = time.perf_counter()
    results = artifacts.predict_both(text)
    total_ms = round((time.perf_counter() - started) * 1000, 3)

    tfidf = results["tfidf"]
    distilbert = results["distilbert"]
    history_id = db.get_store().add(
        text=text,
        char_len=count_chars(text),
        word_len=count_words(text),
        tfidf_label=tfidf["label"],
        tfidf_label_name=tfidf["label_name"],
        tfidf_score=tfidf["score"],
        hf_label=distilbert["label"],
        hf_label_name=distilbert["label_name"],
        hf_score=distilbert["score"],
        elapsed_ms=total_ms,
        source=source,
    )
    return {
        "text": text,
        "char_len": count_chars(text),
        "word_len": count_words(text),
        "models": results,
        "total_ms": total_ms,
        "history_id": history_id,
        "score_note": "score 为模型输出的分类分数，不能解释为「判断正确的概率」。",
        "agreement": tfidf["label"] == distilbert["label"],
    }


@router.post("/api/predict", summary="单条影评：两个模型同时分析")
def predict(payload: PredictRequest) -> dict:
    try:
        text = validate_text(payload.text, "影评文本")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return _run_and_save(text)
    except ModelUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail=f"{exc}。请先确认模型文件存在并完成初始化，稍后重试。",
        ) from exc


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=400, detail="CSV 文件编码无法识别，请另存为 UTF-8 后重试")


@router.post("/api/batch", summary="CSV 批量分析（字段 text，1~20 条）")
async def batch(file: UploadFile = File(..., description="包含 text 列的 CSV 文件")) -> dict:
    raw = await file.read()
    if not raw or not raw.strip():
        raise HTTPException(status_code=400, detail="CSV 文件为空，请上传包含 text 列的文件")
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="CSV 文件超过 5 MB，请拆分后再上传")

    content = _decode(raw)
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        raise HTTPException(status_code=400, detail="CSV 缺少表头，第一行应为字段名")
    normalized = [name.strip().lower() for name in reader.fieldnames]
    if "text" not in normalized:
        raise HTTPException(
            status_code=400,
            detail=f"CSV 缺少 text 列。当前表头：{', '.join(reader.fieldnames)}；批量上传要求字段统一为 text",
        )
    text_key = reader.fieldnames[normalized.index("text")]

    texts: list[tuple[int, str]] = []
    skipped: list[dict] = []
    for row_number, row in enumerate(reader, start=2):
        value = (row.get(text_key) or "").strip()
        if not value:
            skipped.append({"row": row_number, "reason": "text 为空"})
            continue
        if len(value) > config.MAX_INPUT_CHARS:
            skipped.append({"row": row_number, "reason": f"超过 {config.MAX_INPUT_CHARS} 字符上限"})
            continue
        texts.append((row_number, value))

    if not texts:
        raise HTTPException(status_code=400, detail="CSV 中没有可分析的有效 text 行")
    if len(texts) > config.BATCH_MAX_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"一次最多 {config.BATCH_MAX_ROWS} 条，当前有效行 {len(texts)} 条，请拆分后再上传",
        )

    started = time.perf_counter()
    rows = []
    for row_number, value in texts:
        try:
            results = artifacts.predict_both(value)
        except ModelUnavailable as exc:
            raise HTTPException(status_code=503, detail=f"{exc}。请稍后重试。") from exc
        rows.append({
            "row": row_number,
            "text": value,
            "tfidf_label": results["tfidf"]["label"],
            "tfidf_label_name": results["tfidf"]["label_name"],
            "tfidf_label_cn": results["tfidf"]["label_cn"],
            "tfidf_score": results["tfidf"]["score"],
            "distilbert_label": results["distilbert"]["label"],
            "distilbert_label_name": results["distilbert"]["label_name"],
            "distilbert_label_cn": results["distilbert"]["label_cn"],
            "distilbert_score": results["distilbert"]["score"],
            "elapsed_ms": round(results["tfidf"]["elapsed_ms"] + results["distilbert"]["elapsed_ms"], 3),
            "agree": results["tfidf"]["label"] == results["distilbert"]["label"],
        })

    total_ms = round((time.perf_counter() - started) * 1000, 3)
    agree = sum(1 for row in rows if row["agree"])
    return {
        "rows": rows,
        "skipped": skipped,
        "summary": {
            "submitted_rows": len(rows) + len(skipped),
            "analyzed_rows": len(rows),
            "skipped_rows": len(skipped),
            "agree_rows": agree,
            "disagree_rows": len(rows) - agree,
            "total_ms": total_ms,
            "per_row_ms": round(total_ms / len(rows), 3),
        },
        "score_note": "score 为模型输出的分类分数，不能解释为「判断正确的概率」。",
    }
