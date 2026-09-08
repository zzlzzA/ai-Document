# -*- coding: utf-8 -*-
"""本地 Embedding：fastembed(ONNX) + bge-small-zh-v1.5，全程离线推理。
模型首次使用从国内镜像(hf-mirror)下载约 40MB，缓存于 data/models。
不可用时抛出 EmbeddingUnavailable，上层降级为纯 BM25 检索。"""
import threading
import time

from . import config

_lock = threading.Lock()
_model = None
_available = None  # None=未探测 True/False
_failed_at = 0.0   # 上次失败时间；超过重试窗口后重新尝试加载（模型下载可断点续传）
RETRY_WINDOW = 30.0


class EmbeddingUnavailable(Exception):
    pass


def _get_model():
    global _model, _available, _failed_at
    if _available is False and (time.time() - _failed_at) < RETRY_WINDOW:
        raise EmbeddingUnavailable("Embedding 模型不可用（重试窗口内）")
    if _model is not None:
        return _model
    with _lock:
        if _model is not None:
            return _model
        try:
            from fastembed import TextEmbedding
            _model = TextEmbedding(
                model_name=config.EMBED_MODEL,
                cache_dir=config.MODEL_DIR,
                threads=4,
            )
            _available = True
        except Exception as e:
            _available = False
            _failed_at = time.time()
            raise EmbeddingUnavailable(f"Embedding 模型加载失败: {e}")
    return _model


def is_available() -> bool:
    try:
        _get_model()
        return True
    except EmbeddingUnavailable:
        return False


def embed_texts(texts, batch_size=None):
    """批量文本向量化，返回 list[list[float]]。"""
    model = _get_model()
    bs = batch_size or config.EMBED_BATCH
    out = []
    with _lock:
        for i in range(0, len(texts), bs):
            batch = texts[i:i + bs]
            for vec in model.embed(batch):
                out.append([float(x) for x in vec])
    return out


def embed_query(query: str):
    """查询侧向量：bge 中文模型需加指令前缀。"""
    model = _get_model()
    with _lock:
        vec = next(model.query_embed(config.EMBED_QUERY_PREFIX + query))
        return [float(x) for x in vec]


def embed_one(text: str):
    return embed_texts([text])[0]
