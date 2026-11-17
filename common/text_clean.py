"""文本清洗与长度统计。

任务书 3.1.3 要求：清理 HTML 换行标记及多余空白，检查空文本、重复文本、训练测试重叠。
这里把"什么算清洗干净"写成可复现的纯函数，数据集构建与后端输入校验共用。
"""
from __future__ import annotations

import re
import unicodedata

# IMDB 原文用 <br /><br /> 分段，个别样本还夹带 <a href=...> 之类标签
_BR_RE = re.compile(r"<\s*br\s*/?\s*>", re.IGNORECASE)
_TAG_RE = re.compile(r"</?[A-Za-z][^<>]{0,300}>")
_SPACE_RE = re.compile(r"[ \t\u00a0\u3000]+")
# 控制字符（保留 \n \t）
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WS_RE = re.compile(r"\s+")


def clean_review_text(raw: str) -> str:
    """清洗一条影评：去 HTML 标签、统一空白、按段落保留换行。

    规则（顺序不可随意调整）：
      1. 统一换行符、去掉控制字符与 BOM；
      2. <br /> 等换行标记 -> 换行符，其余 HTML 标签 -> 空格；
      3. 统一 Unicode 形式（NFKC），把不换行空格换成普通空格；
      4. 每行去首尾空白、丢弃空行，行内多余空白压成一个空格；
      5. 首尾去空白。
    """
    if raw is None:
        return ""
    text = str(raw)
    text = text.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")
    text = _CTRL_RE.sub(" ", text)
    text = _BR_RE.sub("\n", text)
    text = _TAG_RE.sub(" ", text)
    text = unicodedata.normalize("NFKC", text)
    text = _SPACE_RE.sub(" ", text)
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    return "\n".join(lines).strip()


def dedup_key(text: str) -> str:
    """重复/重叠判定用的归一化键：忽略大小写与所有空白差异。"""
    return _WS_RE.sub(" ", text).strip().casefold()


def count_words(text: str) -> int:
    """按空白切分的词数（本项目长度统计的默认口径）。"""
    return len(text.split())


def count_chars(text: str) -> int:
    """字符数（含空格，不含换行符）。"""
    return len(text.replace("\n", " "))


def is_blank(text: str) -> bool:
    """清洗后为空文本（无可见字符）。"""
    return not text.strip()


def clean_user_input(text: str) -> str:
    """后端接收用户输入时的轻量清洗：不删标签内容，只统一空白与去控制字符。"""
    if text is None:
        return ""
    s = str(text).replace("\r\n", "\n").replace("\r", "\n")
    s = _CTRL_RE.sub(" ", s)
    s = _BR_RE.sub("\n", s)
    s = unicodedata.normalize("NFKC", s)
    s = _SPACE_RE.sub(" ", s)
    lines = [ln.strip() for ln in s.split("\n") if ln.strip()]
    return "\n".join(lines).strip()


def to_display_text(text: str) -> str:
    """前端展示用：保留段落换行，其余与 clean_user_input 一致。"""
    return clean_user_input(text)
