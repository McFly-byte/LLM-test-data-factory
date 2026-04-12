"""安全解析模型返回的 JSON（清洗 Markdown 包裹与前后噪声）。"""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

T = TypeVar("T")


class JSONParseError(ValueError):
    """当无法从模型输出中提取合法 JSON 时抛出。"""


def strip_code_fences(text: str) -> str:
    """移除 ```json ... ``` 等围栏。"""
    t = text.strip()
    # 去掉开头的 ```json 或 ```
    t = re.sub(r"^```(?:json|JSON)?\s*", "", t, flags=re.MULTILINE)
    t = re.sub(r"\s*```$", "", t, flags=re.MULTILINE)
    return t.strip()


def extract_json_block(text: str) -> str:
    """从文本中截取第一个完整 JSON 对象或数组子串（启发式）。"""
    t = strip_code_fences(text)
    # 优先找数组
    for open_ch, close_ch in (("[", "]"), ("{", "}")):
        start = t.find(open_ch)
        if start == -1:
            continue
        depth = 0
        in_str = False
        esc = False
        quote = ""
        for i in range(start, len(t)):
            ch = t[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == quote:
                    in_str = False
                continue
            if ch in "\"'":
                in_str = True
                quote = ch
                continue
            if ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    return t[start : i + 1]
    raise JSONParseError("未找到可解析的 JSON 对象或数组")


def parse_json_loose(text: str) -> Any:
    """清洗后解析 JSON，失败抛出 JSONParseError。"""
    if not text or not str(text).strip():
        raise JSONParseError("模型输出为空")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    block = extract_json_block(text)
    try:
        return json.loads(block)
    except json.JSONDecodeError as e:
        raise JSONParseError(f"JSON 解析失败: {e}") from e


def parse_json_object(text: str) -> dict[str, Any]:
    """解析为 JSON 对象。"""
    data = parse_json_loose(text)
    if not isinstance(data, dict):
        raise JSONParseError(f"期望 JSON 对象，实际为: {type(data).__name__}")
    return data


def parse_json_array(text: str) -> list[Any]:
    """解析为 JSON 数组。"""
    data = parse_json_loose(text)
    if not isinstance(data, list):
        raise JSONParseError(f"期望 JSON 数组，实际为: {type(data).__name__}")
    return data
