"""模型与数据产物的加载与复用。

设计文档 4.2 / 5.1.5 / B4 的要求：
  * 后端启动时加载一次模型，后续请求复用，不再重复加载；
  * 向量在离线阶段生成并保存，重启后直接加载，查询时只编码新输入。

所有重型对象都放在模块级单例 `artifacts` 里，路由只调用方法，不自己加载。
"""
from __future__ import annotations

import csv
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

from common import config

log = logging.getLogger(__name__)


# ------------------------------------------------------------------ 模型封装
class TfidfSentiment:
    """传统模型：TF-IDF + 逻辑回归。加载已保存的 Pipeline，输出标签与分类分数。"""

    name = "tfidf"
    display_name = "TF-IDF + 逻辑回归"

    def __init__(self, model_path: Path = config.MODELS_DIR / "tfidf_lr.joblib") -> None:
        import joblib

        started = time.perf_counter()
        self.pipeline = joblib.load(model_path)
        self.load_seconds = round(time.perf_counter() - started, 3)
        self.model_path = model_path

    def predict(self, text: str) -> dict[str, Any]:
        started = time.perf_counter()
        probabilities = self.pipeline.predict_proba([text])[0]
        label = int(self.pipeline.predict([text])[0])
        elapsed_ms = (time.perf_counter() - started) * 1000
        return {
            "label": label,
            "label_name": config.LABEL_NAMES[label],
            "label_cn": config.LABEL_CN[label],
            # 这是分类分数，不是"判断正确的概率"
            "score": round(float(probabilities[label]), 6),
            "scores": {
                "negative": round(float(probabilities[0]), 6),
                "positive": round(float(probabilities[1]), 6),
            },
            "elapsed_ms": round(elapsed_ms, 3),
        }

    def explain(self, text: str, top_n: int = 12) -> dict[str, Any]:
        """解释这个线性模型为什么给出这个判断。

        做法完全是模型自身的算术，不是事后编的理由：
          * 用训练好的 TfidfVectorizer 把输入变成稀疏向量；
          * 逻辑回归的每个特征权重 coef_[0] 表示「该词出现时把结果往正面推多少」；
          * 两者的乘积就是该词对这条样本的**贡献值**，按绝对值排序取前 top_n 个。

        贡献值为正 = 推向正面，为负 = 推向负面；它是权重与词频的乘积，
        不是概率，也不能跨样本直接比较大小。
        """
        import numpy as np

        vectorizer = self.pipeline.named_steps["tfidf"]
        classifier = self.pipeline.named_steps["classifier"]
        matrix = vectorizer.transform([text]).tocoo()
        feature_names = vectorizer.get_feature_names_out()
        coef = classifier.coef_[0]

        contributions = np.asarray(matrix.data, dtype=float) * coef[matrix.col]
        order = np.argsort(-np.abs(contributions))[: max(1, top_n)]

        terms = []
        for position in order:
            index = int(matrix.col[position])
            contribution = float(contributions[position])
            terms.append(
                {
                    "token": str(feature_names[index]),
                    "tfidf": round(float(matrix.data[position]), 6),
                    "weight": round(float(coef[index]), 6),
                    "contribution": round(contribution, 6),
                    "direction": "positive" if contribution > 0 else "negative",
                }
            )

        return {
            "terms": terms,
            "intercept": round(float(classifier.intercept_[0]), 6),
            "known_tokens": int(matrix.nnz),
            "input_tokens": len(text.split()),
            "note": (
                "以上是 TF-IDF + 逻辑回归的线性贡献值：正数把结果推向正面，负数推向负面，"
                "数值是「TF-IDF 权重 × 回归系数」的乘积，不是概率，也不能跨样本直接比大小。"
                "DistilBERT 是黑盒分类器，本项目不对它做词级归因。"
            ),
        }


class HFSentiment:
    """预训练模型：DistilBERT SST-2。显式 CPU 推理，标签映射到 0/1。"""

    name = "distilbert"
    display_name = "DistilBERT SST-2"

    def __init__(
        self,
        model_id: str = config.SENTIMENT_MODEL_ID,
        max_length: int = config.SENTIMENT_MAX_LENGTH,
    ) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.model_id = model_id
        self.max_length = max_length
        started = time.perf_counter()
        # 显式加载到 CPU（不使用任何 CUDA 设备）
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_id)
        self.model.to("cpu")
        self.model.eval()
        self._torch = torch
        self.load_seconds = round(time.perf_counter() - started, 3)

        # id2label 形如 {0: 'NEGATIVE', 1: 'POSITIVE'}，在这里就映射成本项目的 0/1
        self.id2label = {
            int(index): str(name).upper()
            for index, name in self.model.config.id2label.items()
        }
        mapped = {
            config.HF_LABEL_TO_INT[name]
            for name in self.id2label.values()
            if name in config.HF_LABEL_TO_INT
        }
        if mapped != {0, 1}:
            raise RuntimeError(f"模型标签无法映射到负面/正面：{self.id2label}")

    def count_tokens(self, text: str) -> int | None:
        """统计原始 token 数，用于告诉前端这条输入是否被截断。"""
        try:
            # 临时放开 model_max_length，避免仅为计数而触发超长告警
            saved = self.tokenizer.model_max_length
            self.tokenizer.model_max_length = 10**9
            try:
                encoded = self.tokenizer(text, truncation=False, add_special_tokens=True)
            finally:
                self.tokenizer.model_max_length = saved
            return len(encoded["input_ids"])
        except Exception:  # noqa: BLE001 - 计数失败不应影响推理
            return None

    def predict(self, text: str) -> dict[str, Any]:
        torch = self._torch
        started = time.perf_counter()
        # 截断策略：只使用前 max_length 个 token（max_length 默认 256）
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=self.max_length,
        )
        used_tokens = int(inputs["input_ids"].shape[1])
        with torch.no_grad():
            logits = self.model(**inputs).logits
        probabilities = torch.softmax(logits, dim=-1)[0].tolist()
        elapsed_ms = (time.perf_counter() - started) * 1000

        scores: dict[str, float] = {}
        for index, probability in enumerate(probabilities):
            name = self.id2label.get(index)
            int_label = config.HF_LABEL_TO_INT.get(name) if name else None
            if int_label is None:
                raise RuntimeError(f"未识别的模型输出标签：index={index} name={name}")
            scores[config.LABEL_NAMES[int_label]] = round(float(probability), 6)

        label = 1 if scores["positive"] >= scores["negative"] else 0
        original_tokens = self.count_tokens(text)
        return {
            "label": label,
            "label_name": config.LABEL_NAMES[label],
            "label_cn": config.LABEL_CN[label],
            "score": round(float(scores["positive" if label == 1 else "negative"]), 6),
            "scores": scores,
            "elapsed_ms": round(elapsed_ms, 3),
            "input_tokens": original_tokens,
            "used_tokens": used_tokens,
            "max_length": self.max_length,
            "truncated": bool(original_tokens is not None and original_tokens > self.max_length),
        }


class Embedder:
    """向量模型：all-MiniLM-L6-v2，CPU 编码，输出已归一化向量。"""

    display_name = "MiniLM-L6-v2"

    def __init__(self, model_id: str = config.EMBEDDING_MODEL_ID) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_id = model_id
        started = time.perf_counter()
        self.model = SentenceTransformer(model_id, device="cpu")
        self.load_seconds = round(time.perf_counter() - started, 3)
        self.max_seq_length = getattr(self.model, "max_seq_length", config.EMBEDDING_MAX_TOKENS)
        # sentence-transformers 5.x 改名为 get_embedding_dimension，这里兼容新旧版本
        if hasattr(self.model, "get_embedding_dimension"):
            self.dimension = int(self.model.get_embedding_dimension())
        else:
            self.dimension = int(self.model.get_sentence_embedding_dimension())

    def encode(self, texts: list[str], batch_size: int = 32) -> Any:
        return self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )


# ------------------------------------------------------------------ 数据产物
def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        for key in ("label", "char_len", "word_len"):
            if key in row and row[key] != "":
                row[key] = int(row[key])
        if "original_index" in row and row["original_index"] != "":
            row["original_index"] = int(row["original_index"])
    return rows


class Artifacts:
    """进程级单例：启动时加载一次，之后所有请求共享。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.ready = False
        self.status: dict[str, dict[str, Any]] = {}
        self.load_report: dict[str, Any] = {}

        self.stats: dict[str, Any] = {}
        self.reviews: list[dict] = []
        self.pool: list[dict] = []
        self.embeddings: Any = None
        self.pool_ids: list[str] = []
        self.challenge_pairs: list[dict] = []
        self.retrieval_queries: list[dict] = []
        self.experiments: dict[str, Any] = {}
        # 测试集逐条预测与「两模型分歧」样本（离线脚本产出，网页只读）
        self.predictions: list[dict] = []
        self.divergence: list[dict] = []

        self.tfidf: TfidfSentiment | None = None
        self.hf: HFSentiment | None = None
        self.embedder: Embedder | None = None

    # -------------------------------------------------------------- 加载
    def load(self) -> None:
        """加载全部产物。任一组件失败不影响其它组件，状态里记录原因。"""
        started = time.perf_counter()
        self._load_static()
        self._load_models()
        self.ready = all(
            item["state"] == "ready" for item in self.status.values()
        )
        self.load_report = {
            "total_seconds": round(time.perf_counter() - started, 3),
            "components": self.status,
        }
        for name, item in self.status.items():
            if item["state"] == "ready":
                log.info("[ready] %-12s %.2fs  %s", name, item.get("load_seconds", 0), item.get("detail", ""))
            else:
                log.error("[failed] %-11s %s", name, item.get("error", ""))

    def _load_static(self) -> None:
        try:
            self.stats = json.loads((config.DATA_DIR / "stats.json").read_text(encoding="utf-8"))
            self.status["dataset"] = {
                "state": "ready",
                "detail": f"{self.stats['totals']['reviews']} 条影评",
            }
        except Exception as exc:  # noqa: BLE001
            self.stats = {}
            self.status["dataset"] = {"state": "unavailable", "error": str(exc)}

        try:
            self.reviews = _read_csv(config.DATA_DIR / "reviews.csv")
            self.pool = _read_csv(config.DATA_DIR / "retrieval_pool.csv")
        except Exception as exc:  # noqa: BLE001
            log.error("读取数据文件失败：%s", exc)
            self.reviews, self.pool = [], []

        try:
            self.challenge_pairs = json.loads(
                (config.DATA_DIR / "challenge_pairs.json").read_text(encoding="utf-8")
            )["pairs"]
        except Exception:  # noqa: BLE001
            self.challenge_pairs = []

        try:
            self.retrieval_queries = json.loads(
                (config.DATA_DIR / "retrieval_queries.json").read_text(encoding="utf-8")
            )["queries"]
        except Exception:  # noqa: BLE001
            self.retrieval_queries = []

        try:
            self.experiments = json.loads(
                (config.EXPERIMENTS_DIR / "metrics.json").read_text(encoding="utf-8")
            )
        except Exception:  # noqa: BLE001
            self.experiments = {}

        # 测试集逐条预测：用于「分歧样本浏览器」。文本从 reviews.csv 按 sample_id 取回，
        # 这样页面展示的就是同一条影评，不需要另存一份语料。
        try:
            rows = _read_csv(config.EXPERIMENTS_DIR / "predictions_test.csv")
            text_by_id = {row["sample_id"]: row["text"] for row in self.reviews}
            items = [
                {
                    "sample_id": row["sample_id"],
                    "true_label": int(row["true_label"]),
                    "tfidf_label": int(row["tfidf_label"]),
                    "tfidf_score": float(row["tfidf_score"]),
                    "distilbert_label": int(row["distilbert_label"]),
                    "distilbert_score": float(row["distilbert_score"]),
                    "word_len": int(row["word_len"]) if row.get("word_len") else None,
                    "text": text_by_id.get(row["sample_id"], ""),
                }
                for row in rows
            ]
            self.predictions = items
            self.divergence = [
                item for item in items if item["tfidf_label"] != item["distilbert_label"]
            ]
        except Exception as exc:  # noqa: BLE001
            log.error("读取逐条预测失败：%s", exc)
            self.predictions, self.divergence = [], []

    def _load_models(self) -> None:
        import numpy as np

        # 1) 传统模型
        try:
            self.tfidf = TfidfSentiment()
            self.status["tfidf"] = {
                "state": "ready",
                "load_seconds": self.tfidf.load_seconds,
                "detail": self.tfidf.model_path.name,
            }
        except Exception as exc:  # noqa: BLE001
            self.tfidf = None
            self.status["tfidf"] = {"state": "unavailable", "error": f"{type(exc).__name__}: {exc}"}

        # 2) 预训练情感模型
        try:
            self.hf = HFSentiment()
            self.status["distilbert"] = {
                "state": "ready",
                "load_seconds": self.hf.load_seconds,
                "detail": config.SENTIMENT_MODEL_ID,
            }
        except Exception as exc:  # noqa: BLE001
            self.hf = None
            self.status["distilbert"] = {"state": "unavailable", "error": f"{type(exc).__name__}: {exc}"}

        # 3) 向量模型 + 预生成向量
        try:
            self.embedder = Embedder()
            self.embeddings = np.load(config.DATA_DIR / "embeddings.npy")
            ids_payload = json.loads(
                (config.DATA_DIR / "embeddings_ids.json").read_text(encoding="utf-8")
            )
            self.pool_ids = ids_payload["pool_ids"]
            if self.embeddings.shape[0] != len(self.pool_ids):
                raise ValueError(
                    f"向量条数 {self.embeddings.shape[0]} 与 ID 数 {len(self.pool_ids)} 不一致"
                )
            self.status["embedder"] = {
                "state": "ready",
                "load_seconds": self.embedder.load_seconds,
                "detail": f"{self.embeddings.shape[0]}×{self.embeddings.shape[1]} 向量已加载",
            }
        except Exception as exc:  # noqa: BLE001
            self.embedder = None
            self.embeddings = None
            self.status["embedder"] = {"state": "unavailable", "error": f"{type(exc).__name__}: {exc}"}

    # -------------------------------------------------------------- 推理
    def predict_both(self, text: str) -> dict[str, Any]:
        """两个模型各跑一次，分别计时。任一模型未就绪会抛 ModelUnavailable。"""
        results: dict[str, Any] = {}
        missing = []
        if self.tfidf is not None:
            results["tfidf"] = {
                "model": self.tfidf.display_name,
                "model_id": "sklearn Pipeline(tfidf, LogisticRegression)",
                "max_length_note": "不截断（TF-IDF 使用全文词表）",
                **self.tfidf.predict(text),
            }
        else:
            missing.append("tfidf")
        if self.hf is not None:
            results["distilbert"] = {
                "model": self.hf.display_name,
                "model_id": self.hf.model_id,
                **self.hf.predict(text),
            }
        else:
            missing.append("distilbert")
        if missing:
            raise ModelUnavailable(missing)
        return results

    def search(self, query: str, top_k: int = config.TOP_K) -> list[dict[str, Any]]:
        """余弦相似度检索。向量已归一化，点积即余弦。"""
        import numpy as np

        if self.embedder is None or self.embeddings is None:
            raise ModelUnavailable(["embedder"])
        if not self.pool:
            raise ModelUnavailable(["retrieval_pool"])

        query_vector = self.embedder.encode([query])[0]
        scores = self.embeddings @ query_vector
        k = min(top_k, len(scores))
        top_indices = np.argsort(-scores)[:k]

        pool_by_id = {row["sample_id"]: row for row in self.pool}
        results = []
        for rank, index in enumerate(top_indices, start=1):
            sample_id = self.pool_ids[int(index)]
            row = pool_by_id.get(sample_id, {})
            results.append(
                {
                    "rank": rank,
                    "pool_id": row.get("pool_id"),
                    "sample_id": sample_id,
                    "similarity": round(float(scores[int(index)]), 6),
                    "dataset_label": row.get("label"),
                    "dataset_label_name": row.get("label_name"),
                    # 原始标签与模型预测是两个概念，字段名上就区分开
                    "text": row.get("text", ""),
                    "word_len": row.get("word_len"),
                    "char_len": row.get("char_len"),
                }
            )
        return results


class ModelUnavailable(RuntimeError):
    """模型或资源未就绪。路由层据此返回 503 与明确提示。"""

    def __init__(self, components: list[str]) -> None:
        self.components = components
        super().__init__(f"模型未就绪：{', '.join(components)}")


artifacts = Artifacts()
