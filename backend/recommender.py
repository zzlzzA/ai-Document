# -*- coding: utf-8 -*-
"""最佳文档 AI 智能推荐（PRD 3.6）：六维权重算法。
semantic(语义价值) / time(时间) / visit(访问) / cite(引用) / feedback(反馈) / quality(完整度)
"""
import math
import threading
import time

from . import config, db, embedder, vector_store

_lock = threading.Lock()
_doc_vecs = {"version": -1, "vecs": {}}


def _load_doc_vectors():
    """文档向量 = 该文档全部切片向量的平均（惰性计算，按向量库版本缓存）。"""
    version = vector_store.count()
    with _lock:
        if _doc_vecs["version"] == version and _doc_vecs["vecs"]:
            return _doc_vecs["vecs"]
        col = vector_store._get_collection()
        res = col.get(include=["embeddings", "metadatas"])
        agg = {}
        for i, meta in enumerate(res["metadatas"]):
            did = meta["doc_id"]
            emb = res["embeddings"][i] if res["embeddings"] else None
            if emb is None:
                continue
            a = agg.setdefault(did, [])
            a.append(emb)
        vecs = {}
        for did, arr in agg.items():
            n = len(arr)
            vecs[did] = [sum(x[j] for x in arr) / n for j in range(len(arr[0]))]
        _doc_vecs.update(version=version, vecs=vecs)
        return vecs


def _cos(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def _time_score(ts: float) -> float:
    if not ts:
        return 0.0
    days = max(0.0, (time.time() - ts) / 86400.0)
    return math.exp(-math.log(2) * days / config.TIME_DECAY_DAYS)


def recommend(limit: int = None, exclude_ids: list = None):
    """计算六维加权总分，返回 TopN 文档。"""
    limit = limit or config.RECOMMEND_LIMIT
    docs = db.all_documents()
    if not docs:
        return []
    exclude = set(exclude_ids or [])

    # 语义价值：与知识库整体（全局平均向量）的关联度
    semantic = {}
    if embedder.is_available():
        try:
            vecs = _load_doc_vectors()
            if vecs:
                dim = len(next(iter(vecs.values())))
                gmean = [sum(v[j] for v in vecs.values()) / len(vecs) for j in range(dim)]
                semantic = {did: _cos(v, gmean) for did, v in vecs.items()}
        except Exception:
            semantic = {}

    # 各维度归一化基准
    max_visit = max((d["visit_count"] for d in docs), default=0)
    max_cite = max((d["cite_count"] for d in docs), default=0)
    max_fb = max((abs(d["fb_score"]) for d in docs), default=0)

    results = []
    for d in docs:
        if d["id"] in exclude:
            continue
        w = config.W_WEIGHTS

        sem = semantic.get(d["id"], 0.0)
        t = max(_time_score(d.get("modified_at") or 0), _time_score(d.get("created_at") or 0))
        vis = d["visit_count"] / max_visit if max_visit else 0.0
        cite = d["cite_count"] / max_cite if max_cite else 0.0
        fb = (d["fb_score"] / max_fb) if max_fb else 0.0
        qlt = (1.0 if d["parse_ok"] else 0.0) * min(1.0, (d["text_len"] or 0) / 3000.0)

        score = (
            w["semantic"] * sem
            + w["time"] * t
            + w["visit"] * vis
            + w["cite"] * cite
            + w["feedback"] * max(0.0, fb)
            + w["quality"] * qlt
        )
        results.append({
            "doc_id": d["id"], "name": d["name"], "category": d["category"],
            "size": d["size"], "text_len": d["text_len"], "source": d["source"],
            "created_at": d["created_at"], "visit_count": d["visit_count"],
            "cite_count": d["cite_count"], "fb_score": d["fb_score"],
            "summary": (d["summary"] or "")[:160],
            "score": round(score, 4),
            "dims": {"semantic": round(sem, 3), "time": round(t, 3), "visit": round(vis, 3),
                     "cite": round(cite, 3), "feedback": round(fb, 3), "quality": round(qlt, 3)},
        })
    results.sort(key=lambda x: -x["score"])
    return results[:limit]
