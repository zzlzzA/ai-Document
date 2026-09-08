# -*- coding: utf-8 -*-
"""智能切片（PRD 3.2）：按文档长度自适应 256/512/768 字窗口，带重叠。"""
import re

from . import config


def pick_rule(text_len: int):
    if text_len < config.CHUNK_SHORT_THRESHOLD:
        return config.CHUNK_RULES["short"]
    if text_len > config.CHUNK_LONG_THRESHOLD:
        return config.CHUNK_RULES["long"]
    return config.CHUNK_RULES["default"]


def _normalize(text: str) -> str:
    """清洗：保留段落结构，压缩多余空白。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, rule: dict = None):
    """按字符滑窗切片，返回 [{text, start}]。start 为原文档中的字符偏移，用于溯源定位。"""
    text = _normalize(text)
    if not text:
        return []
    if rule is None:
        rule = pick_rule(len(text))
    size, overlap = rule["size"], rule["overlap"]
    step = max(size - overlap, 1)

    # 优先在段落边界附近切，避免生硬切断句子
    chunks, start = [], 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            # 向前找最近的换行（段落边界），窗口后 20%~40% 范围内
            search_from = start + int(size * 0.6)
            nl = text.rfind("\n", search_from, end)
            if nl != -1 and (end - nl) < size * 0.5:
                end = nl + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append({"text": piece, "start": start})
        if end >= n:
            break
        start = end - overlap if end > overlap else end
    return chunks
