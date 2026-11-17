"""请求 / 响应模型与公共校验。

所有用户可见的提示都用中文，且明确指出是哪一项输入不合要求
（任务书 6.2.5：空输入、超长输入、缺少 text 列、空文件、模型未就绪，都要有明确提示）。
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from common import config
from common.text_clean import clean_user_input, is_blank


class PredictRequest(BaseModel):
    text: str = Field(default="", description="英文影评文本")


class SearchRequest(BaseModel):
    query: str = Field(default="", description="英文查询文本")
    top_k: int = Field(default=config.TOP_K, ge=1, le=20, description="返回条数")


class ChallengeRequest(BaseModel):
    original: str = Field(default="", description="原句（英文）")
    rewritten: str = Field(default="", description="改写句（英文）")


def validate_text(raw: str, field_label: str = "文本") -> str:
    """统一校验：空输入与超长输入。返回清洗后的文本，失败抛 ValueError。"""
    text = clean_user_input(raw)
    if is_blank(text):
        raise ValueError(f"{field_label}为空，请填写英文影评后再试")
    if len(text) > config.MAX_INPUT_CHARS:
        raise ValueError(
            f"{field_label}超过 {config.MAX_INPUT_CHARS} 字符上限（当前 {len(text)} 个字符），请截短后再试"
        )
    return text
