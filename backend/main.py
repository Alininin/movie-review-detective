"""FastAPI 应用入口。

启动方式（见 README）：
    python -m backend.main
或：
    uvicorn backend.main:app --host 127.0.0.1 --port 8000

启动时一次性加载：影评数据、统计结果、TF-IDF 模型、DistilBERT、MiniLM 与预生成向量。
前端构建产物存在时由本服务托管，因此只跑这一条命令就能打开完整网站。
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend import db
from backend.artifacts import artifacts
from backend.routes import challenge, dataset, experiments, insight, predict, search
from common import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("movie-review-detective")

MISSING_FRONTEND_HTML = """
<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>影评侦探 · 后端已启动</title>
<style>body{font-family:system-ui,"Microsoft YaHei",sans-serif;max-width:720px;margin:64px auto;line-height:1.8;color:#1f2937}
code{background:#f3f4f6;padding:2px 6px;border-radius:4px}</style></head>
<body>
<h1>后端已启动，但没找到前端构建产物</h1>
<p>接口文档可访问 <a href="/docs">/docs</a>。</p>
<p>请先构建前端：</p>
<pre><code>cd frontend
npm install
npm run build</code></pre>
<p>然后刷新本页。若你正在开发前端，也可以单独运行 <code>npm run dev</code>，通过
<code>http://127.0.0.1:5173</code> 访问。</p>
</body></html>
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("正在加载数据与模型（首次启动需要下载权重，请耐心等待）……")
    artifacts.load()
    db.init_store()
    report = artifacts.load_report
    log.info("加载完成，共 %.2fs；组件状态：%s", report["total_seconds"],
             {k: v["state"] for k, v in report["components"].items()})
    if not artifacts.ready:
        log.warning("有组件未就绪，相关接口会返回 503 并说明原因")
    yield
    db.get_store().close()


app = FastAPI(
    title="影评侦探 API",
    description=(
        "基于 Hugging Face 的情感分析与相似影评检索网站。\n\n"
        "- 两个分类模型：TF-IDF + 逻辑回归（Sklearn 自训）与 DistilBERT SST-2（CPU 推理）\n"
        "- 相似检索：MiniLM 向量 + 余弦相似度，向量离线预生成\n"
        "- 数值口径：score 是分类分数，不是判断正确的概率；余弦相似度不是准确率"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# 允许前端开发服务器（Vite 默认 5173）跨域调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dataset.router)
app.include_router(predict.router)
app.include_router(search.router)
app.include_router(challenge.router)
app.include_router(experiments.router)
app.include_router(insight.router)


@app.get("/api/health", tags=["系统"], summary="模型与资源就绪状态")
def health() -> JSONResponse:
    payload = {
        "ready": artifacts.ready,
        "components": artifacts.status,
        "load_report": artifacts.load_report,
        "models": {
            "tfidf": "sklearn Pipeline(TfidfVectorizer, LogisticRegression)",
            "sentiment": config.SENTIMENT_MODEL_ID,
            "embedding": config.EMBEDDING_MODEL_ID,
        },
        "limits": {
            "max_input_chars": config.MAX_INPUT_CHARS,
            "batch_max_rows": config.BATCH_MAX_ROWS,
            "top_k": config.TOP_K,
            "sentiment_max_length": config.SENTIMENT_MAX_LENGTH,
            "embedding_max_tokens": config.EMBEDDING_MAX_TOKENS,
        },
        "hf_endpoint": config.HF_ENDPOINT or "https://huggingface.co",
    }
    return JSONResponse(payload, status_code=200 if artifacts.ready else 503)


# ---------------------------------------------------------------- 静态前端
if config.FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(config.FRONTEND_DIST), html=True), name="frontend")
else:

    @app.get("/", include_in_schema=False)
    def frontend_missing() -> HTMLResponse:
        return HTMLResponse(MISSING_FRONTEND_HTML, status_code=200)


def _lan_ip() -> str | None:
    """探测本机内网地址，用于 HOST=0.0.0.0 时提示「同网段的人用哪个地址访问」。"""
    import socket

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))  # 不发包，只让系统选一张网卡
            return probe.getsockname()[0]
    except OSError:
        return None


def main() -> None:
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    log.info("服务地址 http://%s:%s  （接口文档 /docs）", host, port)
    if host == "0.0.0.0":
        lan = _lan_ip()
        if lan:
            log.info("已对局域网开放：http://%s:%s  （同一 WiFi 下的设备可直接打开）", lan, port)
        log.info("首次监听非本机地址时 Windows 可能弹出防火墙提示，允许访问局域网即可")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
