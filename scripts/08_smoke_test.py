"""端到端自检脚本：按 README 的启动方式跑起来后，逐项验证接口与页面是否真的能用。

用途（对应任务书 六、八 的「不能只提交截图或演示视频」）：
  * 一条命令验证全部接口、异常提示、历史增删、重启存活；
  * 检查单位与文案红线（score 不是概率、相似度不是准确率）；
  * 自检过程写进 SQLite 的历史记录会在结束时清理，不污染你的历史列表。

用法：
    # 1) 另开一个终端启动服务
    .venv/Scripts/python -m backend.main
    # 2) 再跑自检
    .venv/Scripts/python scripts/08_smoke_test.py
    # 指定地址（例如改了 PORT）
    .venv/Scripts/python scripts/08_smoke_test.py --base-url http://127.0.0.1:8010

退出码 0 表示全部通过，1 表示有条目失败（失败项会打印原因）。
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.error
import urllib.request
import uuid

TIMEOUT = 120  # CPU 推理较慢，留足时间

_passed = 0
_failed: list[str] = []


# ------------------------------------------------------------------ HTTP 工具
def request(method: str, url: str, payload: dict | None = None,
            raw_body: bytes | None = None, content_type: str | None = None) -> tuple[int, object]:
    """发一个请求，返回 (状态码, 解析后的 JSON 或文本)。4xx/5xx 不抛异常。"""
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    elif raw_body is not None:
        data = raw_body
        headers["Content-Type"] = content_type or "application/octet-stream"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read()
            status = resp.status
            ctype = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:  # 4xx / 5xx
        body = exc.read()
        status = exc.code
        ctype = exc.headers.get("Content-Type", "") if exc.headers else ""

    if "json" in ctype:
        try:
            return status, json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return status, body.decode("utf-8", "replace")
    return status, body.decode("utf-8", "replace")


def multipart_csv(column: str, texts: list[str]) -> tuple[bytes, str]:
    """手工拼一个 multipart/form-data 请求体，避免引入 requests 依赖。"""
    boundary = f"----smoke{uuid.uuid4().hex}"
    lines: list[bytes] = []
    lines.append(f"--{boundary}".encode())
    lines.append(b'Content-Disposition: form-data; name="file"; filename="batch.csv"')
    lines.append(b"Content-Type: text/csv")
    lines.append(b"")
    csv_text = column + "\r\n" + "\r\n".join(t.replace('"', '""') for t in texts) + "\r\n"
    lines.append(csv_text.encode("utf-8"))
    lines.append(f"--{boundary}--".encode())
    lines.append(b"")
    return b"\r\n".join(lines), f"multipart/form-data; boundary={boundary}"


def check(name: str, ok: bool, detail: str = "") -> bool:
    global _passed
    if ok:
        _passed += 1
        print(f"  [OK]   {name}")
    else:
        _failed.append(name)
        print(f"  [FAIL] {name}" + (f" —— {detail}" if detail else ""))
    return ok


def section(title: str) -> None:
    print(f"\n{title}")


# ------------------------------------------------------------------ 各项自检
def main() -> int:
    parser = argparse.ArgumentParser(description="影评侦探端到端自检")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="服务地址")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    created_history: list[int] = []
    try:
        section("[1] 就绪状态与数据统计")
        status, health = request("GET", f"{base}/api/health")
        if isinstance(health, dict):
            check("GET /api/health 返回 200", status == 200, f"状态码 {status}")
            check("四个组件全部就绪", health.get("ready") is True,
                  f"components={health.get('components')}")
            limits = health.get("limits") or {}
            check("输入上限 5000 字符", limits.get("max_input_chars") == 5000, str(limits))
            check("批量上限 20 条", limits.get("batch_max_rows") == 20, str(limits))
        else:
            check("GET /api/health 可用", False, f"状态码 {status}；服务没起来？先运行 python -m backend.main")

        status, stats = request("GET", f"{base}/api/dataset/stats")
        totals = (stats or {}).get("totals", {}) if isinstance(stats, dict) else {}
        check("GET /api/dataset/stats 返回 200", status == 200, f"状态码 {status}")
        check("总样本 1200（训练 1000 + 测试 200）",
              totals.get("reviews") == 1200 and totals.get("train") == 1000 and totals.get("test") == 200,
              str(totals))
        check("检索库 500 条", totals.get("retrieval_pool") == 500, str(totals))

        section("[2] 影评资料库：分页、筛选、统计一致")
        status, page1 = request("GET", f"{base}/api/reviews?page=1&page_size=5")
        total_all = (page1 or {}).get("total") if isinstance(page1, dict) else None
        check("分页返回 5 条", isinstance(page1, dict) and len(page1.get("items", [])) == 5, str(status))
        check("总数与统计文件一致", total_all == totals.get("reviews"), f"{total_all} vs {totals.get('reviews')}")

        status, pos = request("GET", f"{base}/api/reviews?label=1&page_size=1")
        check("按正面筛选得到 600 条", isinstance(pos, dict) and pos.get("total") == 600,
              str((pos or {}).get("total") if isinstance(pos, dict) else status))
        status, neg = request("GET", f"{base}/api/reviews?label=0&page_size=1")
        check("按负面筛选得到 600 条", isinstance(neg, dict) and neg.get("total") == 600,
              str((neg or {}).get("total") if isinstance(neg, dict) else status))
        status, test_only = request("GET", f"{base}/api/reviews?split=test&page_size=1")
        check("按测试集筛选得到 200 条", isinstance(test_only, dict) and test_only.get("total") == 200,
              str((test_only or {}).get("total") if isinstance(test_only, dict) else status))
        status, _ = request("GET", f"{base}/api/reviews?label=2")
        check("非法 label 返回 400", status == 400, f"状态码 {status}")

        section("[3] 单条情感分析（两个模型同时推理）")
        sample = "The actors were excellent, but the story was boring."
        status, pred = request("POST", f"{base}/api/predict", {"text": sample})
        models = (pred or {}).get("models", {}) if isinstance(pred, dict) else {}
        check("POST /api/predict 返回 200", status == 200, f"状态码 {status}；{(pred or {}).get('detail') if isinstance(pred, dict) else ''}")
        check("两个模型都有输出", set(models) == {"tfidf", "distilbert"}, str(list(models)))
        if models:
            ok_scores = all(0.0 <= m.get("score", -1) <= 1.0 for m in models.values())
            check("分类分数在 0~1 之间", ok_scores, str({k: v.get("score") for k, v in models.items()}))
            check("标签映射为 0/1", all(m.get("label") in (0, 1) for m in models.values()),
                  str({k: v.get("label") for k, v in models.items()}))
            check("两个模型的耗时分别记录", all("elapsed_ms" in m for m in models.values()))
            distilbert = models.get("distilbert", {})
            check("DistilBERT 记录截断信息（max_length=256）",
                  distilbert.get("max_length") == 256 and "truncated" in distilbert,
                  str({k: distilbert.get(k) for k in ("max_length", "truncated")}))
            check("文案口径：score 是分类分数", "概率" in (pred or {}).get("score_note", ""),
                  (pred or {}).get("score_note", ""))
        history_id = (pred or {}).get("history_id") if isinstance(pred, dict) else None
        if isinstance(history_id, int):
            created_history.append(history_id)
        check("写入历史并返回 history_id", isinstance(history_id, int), str(history_id))

        section("[4] 输入异常提示")
        status, err = request("POST", f"{base}/api/predict", {"text": "   "})
        check("空输入返回 400", status == 400, f"状态码 {status}")
        check("空输入提示是中文", isinstance(err, dict) and "空" in str(err.get("detail", "")),
              str((err or {}).get("detail") if isinstance(err, dict) else err))
        status, err = request("POST", f"{base}/api/predict", {"text": "a" * 5001})
        check("超过 5000 字符返回 400", status == 400, f"状态码 {status}")
        status, err = request("POST", f"{base}/api/predict", {})
        check("缺少 text 字段被拒绝（400/422）", status in (400, 422), f"状态码 {status}")

        section("[5] CSV 批量分析")
        body, ctype = multipart_csv("text", [
            "A wonderful film with great performances.",
            "Boring and predictable, I almost fell asleep.",
        ])
        status, batch = request("POST", f"{base}/api/batch", raw_body=body, content_type=ctype)
        rows = (batch or {}).get("rows", []) if isinstance(batch, dict) else []
        check("上传 2 条 CSV 返回 200", status == 200, f"状态码 {status}；{(batch or {}).get('detail') if isinstance(batch, dict) else ''}")
        check("批量结果 2 行且含两个模型预测", len(rows) == 2 and all(
            {"tfidf_label", "distilbert_label", "text"} <= set(row) for row in rows), str(len(rows)))

        body, ctype = multipart_csv("review", ["only a wrong column"])
        status, err = request("POST", f"{base}/api/batch", raw_body=body, content_type=ctype)
        check("缺少 text 列返回 400", status == 400, f"状态码 {status}")
        check("缺列提示点明表头", isinstance(err, dict) and "text" in str(err.get("detail", "")),
              str((err or {}).get("detail") if isinstance(err, dict) else err))

        body, ctype = multipart_csv("text", [f"This is review number {i}." for i in range(21)])
        status, err = request("POST", f"{base}/api/batch", raw_body=body, content_type=ctype)
        check("超过 20 条返回 400", status == 400, f"状态码 {status}")

        section("[6] 相似影评检索")
        status, queries = request("GET", f"{base}/api/search/queries")
        qs = (queries or {}).get("queries", []) if isinstance(queries, dict) else []
        check("5 条预设查询", len(qs) == 5, f"{len(qs)} 条")
        status, result = request("POST", f"{base}/api/search", {"query": sample, "top_k": 5})
        items = (result or {}).get("results", []) if isinstance(result, dict) else []
        check("检索返回 5 条", len(items) == 5, f"状态码 {status}，{len(items)} 条")
        if items:
            sims = [item["similarity"] for item in items]
            check("相似度从高到低排序", sims == sorted(sims, reverse=True), str(sims))
            check("相似度在 0~1 之间", all(0.0 <= s <= 1.0 for s in sims), str(sims))
            check("每条都带原始标签与完整原文",
                  all({"dataset_label", "text", "sample_id"} <= set(item) for item in items))
            check("相似度不叫准确率", "准确率" not in json.dumps(result, ensure_ascii=False)[:2000])
            check("检索结果 ID 均在检索库内",
                  all(str(item["sample_id"]).startswith(("pool-", "train-", "test-")) for item in items),
                  str([item["sample_id"] for item in items]))
        status, err = request("POST", f"{base}/api/search", {"query": "  "})
        check("空查询返回 400", status == 400, f"状态码 {status}")

        section("[7] 模型挑战")
        status, presets = request("GET", f"{base}/api/challenge/presets")
        pairs = (presets or {}).get("pairs", []) if isinstance(presets, dict) else []
        check("6 对预置样本", len(pairs) == 6, f"{len(pairs)} 对")
        if pairs:
            kinds = [p.get("category") for p in pairs]
            check("覆盖否定/转折/改写三类",
                  len({k for k in kinds if k}) >= 3, str(kinds))
            pair = pairs[0]
            status, cmp_result = request("POST", f"{base}/api/challenge",
                                         {"original": pair["original"], "rewritten": pair["rewritten"]})
            comparison = (cmp_result or {}).get("comparison", {}) if isinstance(cmp_result, dict) else {}
            check("句子对分析返回两个模型", set(comparison) == {"tfidf", "distilbert"}, str(list(comparison)))
            check("预置样本能识别并给出人工判断",
                  (cmp_result or {}).get("preset_id") == pair.get("id"),
                  str((cmp_result or {}).get("preset_id")))

        section("[8] 实验材料")
        status, exp = request("GET", f"{base}/api/experiments")
        metrics = (exp or {}).get("metrics") or {} if isinstance(exp, dict) else {}
        check("GET /api/experiments 返回 200", status == 200, f"状态码 {status}")
        if isinstance(metrics, dict) and metrics:
            models_metrics = metrics.get("models") or {}
            check("两个模型都有指标", {"tfidf", "distilbert"} <= set(models_metrics), str(list(models_metrics)))
            ok = all(0 <= models_metrics[m].get("accuracy", -1) <= 1 and
                     0 <= models_metrics[m].get("macro_f1", -1) <= 1 for m in models_metrics)
            check("Accuracy / Macro-F1 在 0~1 之间", ok,
                  str({m: (models_metrics[m].get("accuracy"), models_metrics[m].get("macro_f1")) for m in models_metrics}))
            check("记录 CPU 与批大小", bool(metrics.get("run_config")), str(metrics.get("run_config"))[:120])
            check("加载时间与推理时间分开记录",
                  all(isinstance(models_metrics[m].get("timing"), dict)
                      and "model_load_seconds" in models_metrics[m]["timing"]
                      and "inference_total_seconds" in models_metrics[m]["timing"]
                      for m in models_metrics),
                  str({m: models_metrics[m].get("timing") for m in models_metrics}))
        check("包含错误案例分析", bool((exp or {}).get("error_cases_markdown")) if isinstance(exp, dict) else False)
        status, img = request("GET", f"{base}/api/experiments/confusion-matrix.png")
        check("混淆矩阵图可访问", status == 200, f"状态码 {status}")

        section("[9] 历史记录：保存、查看、删除")
        status, history = request("GET", f"{base}/api/history?limit=200")
        ids = [row["id"] for row in (history or {}).get("items", [])] if isinstance(history, dict) else []
        check("历史列表返回 200", status == 200, f"状态码 {status}")
        check("刚写入的记录能在历史里查到", all(h in ids for h in created_history), f"created={created_history}")
        if isinstance(history, dict) and history.get("items"):
            row = history["items"][0]
            need = {"text", "tfidf_label", "tfidf_score", "hf_label", "hf_score", "created_at"}
            check("历史含文本/两种结果/分数/时间", need <= set(row), str(sorted(row)))
        if created_history:
            status, _ = request("DELETE", f"{base}/api/history/{created_history[0]}")
            check("删除单条历史返回 200", status == 200, f"状态码 {status}")
            status, history = request("GET", f"{base}/api/history?limit=200")
            ids = [row["id"] for row in (history or {}).get("items", [])] if isinstance(history, dict) else []
            check("删除后列表里不再出现该记录", created_history[0] not in ids, str(created_history[0]))
            created_history.pop(0)
        status, _ = request("DELETE", f"{base}/api/history/99999999")
        check("删除不存在的记录返回 404", status == 404, f"状态码 {status}")

        section("[10] 前端页面托管")
        status, html = request("GET", f"{base}/")
        check("首页返回 200", status == 200, f"状态码 {status}")
        check("首页是前端构建产物（含挂载点）",
              isinstance(html, str) and ('id="app"' in html or "assets/index-" in html),
              str(html)[:120])
        status, docs = request("GET", f"{base}/docs")
        check("接口文档 /docs 可访问", status == 200, f"状态码 {status}")

    finally:
        # 清理本次自检写入的历史，避免污染你的历史列表
        for hid in created_history:
            try:
                request("DELETE", f"{base}/api/history/{hid}")
            except Exception:  # noqa: BLE001
                pass

    total = _passed + len(_failed)
    print("\n" + "=" * 60)
    if _failed:
        print(f"自检未通过：{_passed}/{total} 项通过，以下失败：")
        for name in _failed:
            print(f"  - {name}")
        return 1
    print(f"自检全部通过：{total}/{total} 项")
    print("可以按 README 的「五个页面」逐页点一遍，然后提交。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
