# -*- coding: utf-8 -*-
"""Chroma 本地向量库：持久化于 data/chroma，无服务依赖。
存切片向量 + 元数据；文档更新/删除时同步。"""
import threading

import chromadb

from . import config

_client = None
_collection = None
_lock = threading.Lock()


def _get_collection():
    global _client, _collection
    if _collection is not None:
        return _collection
    with _lock:
        if _collection is not None:
            return _collection
        _client = chromadb.PersistentClient(path=config.CHROMA_DIR)
        _collection = _client.get_or_create_collection(
            name="doc_chunks",
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def count():
    try:
        return _get_collection().count()
    except Exception:
        return 0


def add_chunks(doc_id: int, name: str, category: str, chunks: list, vectors: list):
    """chunks: [{text, start}]；vectors 与 chunks 等长。"""
    if not chunks or not vectors:
        return
    col = _get_collection()
    ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
    metas = [{
        "doc_id": doc_id,
        "name": name,
        "category": category,
        "start": c["start"],
        "idx": i,
    } for i, c in enumerate(chunks)]
    with _lock:
        # 分批 upsert，避免单次过大
        step = 200
        for i in range(0, len(chunks), step):
            col.upsert(
                ids=ids[i:i + step],
                documents=[c["text"] for c in chunks[i:i + step]],
                embeddings=vectors[i:i + step],
                metadatas=metas[i:i + step],
            )


def query_by_vector(vector, n_results=8, where=None):
    """按向量检索，返回命中列表（含相似度）。"""
    col = _get_collection()
    where_filter = None
    if where:
        where_filter = {k: v for k, v in where.items()}
    res = col.query(
        query_embeddings=[vector],
        n_results=n_results,
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )
    out = []
    if not res["ids"]:
        return out
    for i, cid in enumerate(res["ids"][0]):
        meta = res["metadatas"][0][i]
        dist = res["distances"][0][i]
        out.append({
            "chunk_id": cid,
            "doc_id": meta.get("doc_id"),
            "name": meta.get("name", ""),
            "category": meta.get("category", ""),
            "start": meta.get("start", 0),
            "text": res["documents"][0][i],
            "score": float(1.0 - dist),  # cosine 相似度 ≈ 1 - distance
        })
    return out


def get_all_chunks_meta():
    """全量遍历（供 BM25 建索引 / 统计引用），返回 [{chunk_id, doc_id, text, start}]。"""
    col = _get_collection()
    out = []
    offset = 0
    limit = 500
    while True:
        res = col.get(limit=limit, offset=offset, include=["documents", "metadatas"])
        ids = res["ids"]
        if not ids:
            break
        for i, cid in enumerate(ids):
            meta = res["metadatas"][i]
            out.append({
                "chunk_id": cid,
                "doc_id": meta.get("doc_id"),
                "start": meta.get("start", 0),
                "text": res["documents"][i],
            })
        if len(ids) < limit:
            break
        offset += limit
    return out


def delete_document(doc_id: int):
    col = _get_collection()
    with _lock:
        res = col.get(where={"doc_id": doc_id}, include=[])
        if res["ids"]:
            col.delete(ids=res["ids"])


def delete_all():
    global _collection
    with _lock:
        _get_collection().delete(where={})  # where={} 会触发全量删除
        _collection = None
