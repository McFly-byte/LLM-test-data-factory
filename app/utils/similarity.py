"""简单文本相似度：用于高度重复 query 检测。"""

from __future__ import annotations

import re
from difflib import SequenceMatcher


def normalize_text(s: str) -> str:
    """轻量归一化：小写、压缩空白、去标点。"""
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\s\u4e00-\u9fff]", "", s)
    return s


def similarity_ratio(a: str, b: str) -> float:
    """返回 [0,1] 的相似度，基于 SequenceMatcher。"""
    na, nb = normalize_text(a), normalize_text(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def is_near_duplicate(query: str, others: list[str], threshold: float) -> bool:
    """若与任一已有 query 相似度 >= threshold，视为近重复。"""
    for o in others:
        if similarity_ratio(query, o) >= threshold:
            return True
    return False
