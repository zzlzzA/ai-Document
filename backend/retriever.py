# -*- coding: utf-8 -*-
"""混合检索（PRD 3.4）：BM25 关键词 + 向量语义，RRF 融合，用户行为权重修正。"""
import threading

import jieba
from rank_bm25 import BM25Okapi

from . import config, db, embedder, vector_store

_lock = threading.Lock()
_bm25_cache = {"version": -1, "bm25": None, "corpus": []}

# 中文停用词（虚词/标点/问句语气词），避免污染 BM25 关键词检索
STOPWORDS = set(
    "的了是在不也都有和与及或就而但并且之其我你他她它这那有无被把让给对从向以于等"
    "吗呢吧啊么什么怎么怎样如何哪些多少为什么请问请一下一个可以能会要想帮帮忙告诉"
    "介绍简述详细分别以及或者然后因为所以但是如果就是还是不是没有这个那个进行通过"
    "我们你们他们咱们自己大家现在今天明天昨天时候方面部分内容情况问题关于对于"
    "，。：；？！、""''（）《》【】-—_·… "
)


def _tokenize(text: str) -> list:
    return [w for w in jieba.lcut(text.lower()) if w.strip() and w not in STOPWORDS and len(w.strip()) <= 32]


def _get_bm25():
    """按 SQLite 切片数量作为版本信号重建 BM25 索引（独立于向量库）。"""
    version = db.chunk_count()
    with _lock:
        if _bm25_cache["version"] == version and _bm25_cache["bm25"] is not None:
            return _bm25_cache["bm25"], _bm25_cache["corpus"]
        chunks = db.all_chunks()
        corpus = []
        for c in chunks:
            corpus.append({
                "chunk_id": c["chunk_id"],
                "doc_id": c["doc_id"],
                "start": c["start"],
                "text": c["text"],
                "name": c.get("name", ""),
                "category": c.get("category", ""),
            })
        tok = [_tokenize(c["text"]) for c in corpus]
        bm25 = BM25Okapi(tok) if tok else None
        _bm25_cache.update(version=version, bm25=bm25, corpus=corpus)
        return bm25, corpus


def _behavior_bias(doc_ids: list) -> dict:
    """按文档行为统计计算排序权重修正（0.5 ~ 2.0 之间）。"""
    if not doc_ids:
        return {}
    bias = {}
    docs = db.all_documents()
    by_id = {d["id"]: d for d in docs}
    max_visit = max((by_id[i]["visit_count"] for i in doc_ids if i in by_id), default=0)
    max_cite = max((by_id[i]["cite_count"] for i in doc_ids if i in by_id), default=0)
    for i in doc_ids:
        d = by_id.get(i)
        if not d:
            bias[i] = 1.0
            continue
        w = 1.0
        if max_visit:
            w += 0.25 * (d["visit_count"] / max_visit)
        if max_cite:
            w += 0.25 * (d["cite_count"] / max_cite)
        w += max(-0.3, min(0.3, d["fb_score"] * 0.1))
        bias[i] = w
    return bias


def search(query: str, k: int = None, top_per_doc: int = 3):
    """混合检索：返回排序后的片段列表。
    每片段含 doc_id/name/category/start/text/score；同一文档最多保留 top_per_doc 个。
    向量模型不可用时自动降级为纯 BM25。"""
    k = k or config.RETRIEVE_TOP_K
    bm25, corpus = _get_bm25()
    scores = {}  # chunk_index -> (rrf_score, hit)
    hits = {}    # chunk_id -> {…}

    # 1) 向量语义检索
    vec_ok = embedder.is_available()
    if vec_ok:
        try:
            qvec = embedder.embed_query(query)
            vec_hits = vector_store.query_by_vector(qvec, n_results=k * 3)
            for rank, h in enumerate(vec_hits, 1):
                if h["score"] < config.VEC_SIM_MIN:
                    continue  # 相似度低于下限：语义无关，不召回
                key = h["chunk_id"]
                hits.setdefault(key, h)
                scores.setdefault(key, [0.0, 0])
                scores[key][0] += 1.0 / (rank + config.RRF_K)
                scores[key][1] += 1
        except Exception:
            vec_ok = False

    # 2) BM25 关键词检索
    if bm25 and corpus:
        tok_q = _tokenize(query)
        if tok_q:
            bm_scores = bm25.get_scores(tok_q)
            order = sorted(range(len(bm_scores)), key=lambda i: -bm_scores[i])
            for rank, ci in enumerate(order[:k * 3], 1):
                if bm_scores[ci] <= config.BM25_MIN_SCORE:
                    continue  # 原始分过低：关键词巧合命中，不召回
                c = corpus[ci]
                key = c["chunk_id"]
                hits.setdefault(key, {
                    "chunk_id": key, "doc_id": c["doc_id"], "start": c["start"],
                    "name": c.get("name", ""), "category": c.get("category", ""),
                    "text": c["text"], "score": 0.0,
                })
                scores.setdefault(key, [0.0, 0])
                scores[key][0] += 1.0 / (rank + config.RRF_K)
                scores[key][1] += 1

    if not hits:
        return [], vec_ok

    # 3) 行为权重修正 + 按文档限流
    doc_ids = list({h["doc_id"] for h in hits.values()})
    bias = _behavior_bias(doc_ids)
    ranked = []
    per_doc = {}
    for key, (rrf, _n) in sorted(scores.items(), key=lambda x: -x[1][0]):
        h = hits[key]
        doc_id = h["doc_id"]
        if per_doc.get(doc_id, 0) >= top_per_doc:
            continue
        per_doc[doc_id] = per_doc.get(doc_id, 0) + 1
        h = dict(h)
        # 归一化 RRF 到 0~1，再叠加行为偏置（幅度受 BEHAVIOR_WEIGHT_MAX 约束）
        norm = rrf / (1.0 + config.RRF_K)
        b = bias.get(doc_id, 1.0)
        adj = (b - 1.0) * config.BEHAVIOR_WEIGHT_MAX
        h["score"] = round(min(1.0, max(0.0, norm + adj)), 4)
        h["vector_used"] = vec_ok
        ranked.append(h)
        if len(ranked) >= k:
            break
    return ranked, vec_ok


def search_documents(query: str, k: int = 12):
    """面向文档列表的检索（按文档聚合，用于侧边栏推荐）。"""
    hits, _ = search(query, k=k, top_per_doc=999)
    agg = {}
    for h in hits:
        d = agg.setdefault(h["doc_id"], {"doc_id": h["doc_id"], "name": h["name"], "score": 0.0, "text": ""})
        d["score"] = max(d["score"], h["score"])
        if not d["text"]:
            d["text"] = h["text"]
    return sorted(agg.values(), key=lambda x: -x["score"])
