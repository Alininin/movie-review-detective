"""实验与历史接口。

任务书 6.3 允许「实验指标由离线脚本生成文件后供网页读取」，
因此这里只读 experiments/ 下的产物，不在网页请求里重新评测。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from backend import db
from common import config

router = APIRouter(tags=["实验与历史"])

EXPERIMENT_FILES = {
    "metrics": config.EXPERIMENTS_DIR / "metrics.json",
    "retrieval": config.EXPERIMENTS_DIR / "retrieval_metrics.json",
    "embedding_build": config.EXPERIMENTS_DIR / "embedding_build.json",
    "error_cases": config.EXPERIMENTS_DIR / "error_cases.md",
    "error_cases_auto": config.EXPERIMENTS_DIR / "error_cases_auto.md",
    # 网页用深色版（配色与界面一致）；报告里用白底版 confusion_matrix.png
    "confusion_matrix": config.EXPERIMENTS_DIR / "confusion_matrix_dark.png",
    "confusion_matrix_report": config.EXPERIMENTS_DIR / "confusion_matrix.png",
}


@router.get("/api/experiments", summary="指标、混淆矩阵、案例分析")
def experiments(theme: str = Query(default="dark", description="dark / light：选混淆矩阵配色")) -> dict:
    import json

    if not EXPERIMENT_FILES["metrics"].exists():
        raise HTTPException(
            status_code=503,
            detail="还没有评测结果：请先运行 scripts/04_evaluate.py 生成 experiments/metrics.json",
        )

    def read_json(path):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None

    error_text = ""
    if EXPERIMENT_FILES["error_cases"].exists():
        error_text = EXPERIMENT_FILES["error_cases"].read_text(encoding="utf-8")

    # 界面有明暗两套主题，混淆矩阵也备了两版：浅色主题用白底图，深色主题用暗色图。
    # 地址带上文件修改时间，重新生成图片后浏览器不会继续显示缓存里的旧图。
    matrix_path = (
        EXPERIMENT_FILES["confusion_matrix_report"]
        if theme == "light"
        else EXPERIMENT_FILES["confusion_matrix"]
    )
    version = int(matrix_path.stat().st_mtime) if matrix_path.exists() else 0

    return {
        "metrics": read_json(EXPERIMENT_FILES["metrics"]),
        "retrieval": read_json(EXPERIMENT_FILES["retrieval"]),
        "embedding_build": read_json(EXPERIMENT_FILES["embedding_build"]),
        "error_cases_markdown": error_text,
        "artifacts": {
            "confusion_matrix_url": f"/api/experiments/confusion-matrix.png?theme={theme}&v={version}",
            "predictions_csv": "experiments/predictions_test.csv",
            "retrieval_check_csv": "experiments/retrieval_check.csv",
        },
        "source_note": "以下数字由离线脚本生成并保存在 experiments/ 目录，网页只读取、不重新评测。",
    }


@router.get("/api/experiments/confusion-matrix.png", summary="混淆矩阵图片")
def confusion_matrix_image(theme: str = Query(default="dark")) -> FileResponse:
    path = (
        EXPERIMENT_FILES["confusion_matrix_report"]
        if theme == "light"
        else EXPERIMENT_FILES["confusion_matrix"]
    )
    if not path.exists():
        raise HTTPException(status_code=404, detail="混淆矩阵图不存在，请先运行 scripts/04_evaluate.py")
    return FileResponse(path, media_type="image/png", filename="confusion_matrix.png")


@router.get("/api/history", summary="分析历史列表")
def history_list(
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    payload = db.get_store().list(limit=limit, offset=offset)
    payload["note"] = "历史保存在 SQLite（data/history.db），刷新页面与重启服务后仍然存在。"
    return payload


@router.delete("/api/history/{record_id}", summary="删除一条历史")
def history_delete(record_id: int) -> dict:
    deleted = db.get_store().delete(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"历史记录 {record_id} 不存在")
    return {"deleted": record_id, "ok": True}


@router.delete("/api/history", summary="清空历史")
def history_clear() -> dict:
    return {"deleted": db.get_store().clear(), "ok": True}
