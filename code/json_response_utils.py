"""
结构化 JSON 输出辅助工具。

目标：
- 尽量从 LLM 的非严格 JSON 输出中提取合法 JSON；
- 为高温度场景提供更强的本地解析兜底；
- 尽量避免额外模型调用。
"""

from __future__ import annotations

import ast
import json
import re
from typing import Any, List


_CODE_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.S | re.I)
_TRAILING_COMMA_PATTERN = re.compile(r",(\s*[}\]])")


def strip_code_fence(text: str) -> str:
    match = _CODE_BLOCK_PATTERN.search(text or "")
    if match:
        return match.group(1).strip()
    return str(text or "").strip()


def _normalize_candidate(text: str) -> str:
    candidate = strip_code_fence(text).strip()
    if candidate.lower().startswith("json"):
        candidate = candidate[4:].lstrip(": \n")
    candidate = candidate.replace("\ufeff", "").strip()
    candidate = _TRAILING_COMMA_PATTERN.sub(r"\1", candidate)
    return candidate


def _extract_balanced_segments(text: str) -> List[str]:
    text = str(text or "")
    segments: List[str] = []
    stack: List[str] = []
    start_index = -1
    in_string = False
    quote_char = ""
    escape = False

    for index, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == quote_char:
                in_string = False
            continue

        if char in {'"', "'"}:
            in_string = True
            quote_char = char
            continue

        if char in "{[":
            if not stack:
                start_index = index
            stack.append(char)
            continue

        if char in "}]":
            if not stack:
                continue
            opener = stack[-1]
            if (opener, char) not in {("{", "}"), ("[", "]")}:
                continue
            stack.pop()
            if not stack and start_index >= 0:
                segments.append(text[start_index:index + 1])
                start_index = -1

    return segments


def _loads_with_fallbacks(candidate: str) -> Any:
    normalized = _normalize_candidate(candidate)
    if not normalized:
        raise ValueError("empty json candidate")

    try:
        return json.loads(normalized)
    except Exception:
        pass

    try:
        return ast.literal_eval(normalized)
    except Exception:
        pass

    # 常见情况：最外层有多余文字，尝试再次抽取平衡括号片段。
    for segment in _extract_balanced_segments(normalized):
        if segment == normalized:
            continue
        try:
            return json.loads(_normalize_candidate(segment))
        except Exception:
            try:
                return ast.literal_eval(_normalize_candidate(segment))
            except Exception:
                continue

    raise ValueError("unable to parse json candidate")


def parse_json_response_loose(text: str) -> Any:
    """尽量宽松地解析 LLM 输出中的 JSON。"""
    raw_text = str(text or "").strip()
    candidates: List[str] = []

    if raw_text:
        candidates.append(raw_text)

    stripped = strip_code_fence(raw_text)
    if stripped and stripped not in candidates:
        candidates.append(stripped)

    for segment in _extract_balanced_segments(raw_text):
        if segment not in candidates:
            candidates.append(segment)

    errors: List[str] = []
    for candidate in candidates:
        try:
            parsed = _loads_with_fallbacks(candidate)
            if isinstance(parsed, (dict, list)):
                return parsed
        except Exception as error:
            errors.append(str(error))

    raise ValueError("; ".join(errors) or "unable to parse json response")
