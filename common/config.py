"""集中配置：路径、随机种子、抽样配额、模型标识。

所有口径常量集中在此，保证脚本、后端、报告三者引用同一套取值。
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MODELS_DIR = ROOT / "models"
EXPERIMENTS_DIR = ROOT / "experiments"
FRONTEND_DIST = ROOT / "frontend" / "dist"


def _load_dotenv(path: Path) -> None:
    """极简 .env 读取，避免引入 python-dotenv 依赖；不覆盖已存在的环境变量。"""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(ROOT / ".env")

# Hugging Face 端点。国内网络下 huggingface.co 不可达，必须指向镜像。
# 必须在 import datasets / transformers 之前写入环境变量，因此放在模块顶部。
HF_ENDPOINT = os.getenv("HF_ENDPOINT", "").strip()
if HF_ENDPOINT:
    os.environ["HF_ENDPOINT"] = HF_ENDPOINT

# ---------------------------------------------------------------- 数据抽样口径
SEED = 42
SPLIT_QUOTAS = {
    "train": {"negative": 500, "positive": 500},
    "test": {"negative": 100, "positive": 100},
}
# 检索库字段与数量；来源见 RETRIEVAL_POOL_SOURCE
RETRIEVAL_POOL_SIZE = 500
# split_excluded : 从 IMDB train 中排除已抽作训练/测试的 1200 条后再抽（默认，与训练/测试完全不重叠）
# from_train_1000: 直接从 1000 条训练样本中取 500 条（若教师另行要求时改用此值）
RETRIEVAL_POOL_SOURCE = os.getenv("RETRIEVAL_POOL_SOURCE", "split_excluded").strip()

# ---------------------------------------------------------------- 模型与资源标识
DATASET_ID = "stanfordnlp/imdb"
SENTIMENT_MODEL_ID = "distilbert/distilbert-base-uncased-finetuned-sst-2-english"
EMBEDDING_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"

# 两个模型的截断上限，评测报告与前端提示必须与此一致
SENTIMENT_MAX_LENGTH = 256
EMBEDDING_MAX_TOKENS = 256  # all-MiniLM-L6-v2 的 max_seq_length

# ---------------------------------------------------------------- 标签口径
LABEL_NAMES = {0: "negative", 1: "positive"}
LABEL_CN = {0: "负面", 1: "正面"}
# DistilBERT SST-2 的输出标签 -> 与本项目一致的整数标签
HF_LABEL_TO_INT = {"NEGATIVE": 0, "LABEL_0": 0, "POSITIVE": 1, "LABEL_1": 1}

# ---------------------------------------------------------------- 接口约束
MAX_INPUT_CHARS = 5000
BATCH_MIN_ROWS = 1
BATCH_MAX_ROWS = 20
TOP_K = 5
