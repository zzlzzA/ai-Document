# -*- coding: utf-8 -*-
"""AI 自动分类 + 个性化学习（PRD 3.3）。
- 语义向量：文档摘要与类中心相似度
- 关键词规则：文件名 + 正文头部命中加分
- 学习机制：用户修正过的分类沉淀为样本，后续同语义文档优先沿用
"""
import threading

from . import config, db, embedder, vector_store

_lock = threading.Lock()
_centers = None          # {category: vector}
_samples = None          # [{doc_id, category, vector, ts}]
_SIM_THRESHOLD = 0.72    # 与人工修正样本的相似度阈值


def _cos(a, b):
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _get_centers():
    global _centers
    if _centers is not None:
        return _centers
    with _lock:
        if _centers is not None:
            return _centers
        if not embedder.is_available():
            _centers = {}
            return _centers
        descs = [config.CATEGORY_PROFILES[c]["desc"] for c in config.DEFAULT_CATEGORIES]
        vecs = embedder.embed_texts(descs)
        _centers = {c: v for c, v in zip(config.DEFAULT_CATEGORIES, vecs)}
    return _centers


def _load_samples():
    """加载人工修正样本：doc_id + 分类 + 首个切片向量（向量库直查）。"""
    global _samples
    with _lock:
        rows = db.get_conn().execute(
            "SELECT id, category, created_at FROM documents WHERE category_manual=1"
        ).fetchall()
        if not rows:
            _samples = []
            return _samples
        col = vector_store._get_collection()
        _samples = []
        for r in rows:
            try:
                res = col.get(where={"doc_id": r["id"]}, limit=1, include=["embeddings"])
                if res["ids"] and res["embeddings"] and res["embeddings"][0] is not None:
                    _samples.append({
                        "doc_id": r["id"], "category": r["category"],
                        "vector": [float(x) for x in res["embeddings"][0]],
                        "ts": r["created_at"],
                    })
            except Exception:
                continue
        _samples.sort(key=lambda x: -x["ts"])
        return _samples[:50]  # 最多取最近 50 条修正样本


def _invalidate_samples():
    global _samples
    with _lock:
        _samples = None


def _keyword_score(text: str, filename: str) -> dict:
    """关键词规则打分，返回 {category: score}。"""
    head = (filename + " " + text[:1500]).lower()
    scores = {}
    for cat, prof in config.CATEGORY_PROFILES.items():
        s = sum(1 for kw in prof["keywords"] if kw.lower() in head)
        if s:
            scores[cat] = s
    return scores


def classify(text: str, filename: str):
    """返回 (category, confidence, reason)。"""
    kw = _keyword_score(text, filename)
    centers = _get_centers()
    vec_scores = {}
    vec_ok = bool(centers) and embedder.is_available()
    if vec_ok:
        try:
            head = text[:800].strip() or filename
            v = embedder.embed_one(head)
            vec_scores = {c: _cos(v, cv) for c, cv in centers.items()}
        except Exception:
            vec_ok = False

    # 综合：向量 60% + 关键词 40%（关键词归一化）
    total = {}
    if vec_scores:
        k_max = max(kw.values()) if kw else 1
        for c in config.DEFAULT_CATEGORIES:
            k_norm = kw.get(c, 0) / k_max
            total[c] = 0.6 * max(0.0, vec_scores.get(c, 0.0)) + 0.4 * k_norm
    else:
        k_max = max(kw.values()) if kw else 1
        for c in config.DEFAULT_CATEGORIES:
            total[c] = kw.get(c, 0) / k_max

    best = max(total, key=total.get) if total else "其他"
    top2 = sorted(total.items(), key=lambda x: -x[1])[:2]
    conf = float(top2[0][1]) if top2 else 0.0
    margin = (top2[0][1] - top2[1][1]) if len(top2) > 1 else 1.0

    # 学习机制：与用户修正样本做相似度匹配，超过阈值则沿用用户习惯
    if vec_ok:
        try:
            samples = _load_samples()
            if samples:
                v = embedder.embed_one(text[:800].strip() or filename)
                best_sample, best_sim = None, 0.0
                for s in samples:
                    sim = _cos(v, s["vector"])
                    if sim > best_sim:
                        best_sim, best_sample = sim, s
                if best_sample and best_sim >= _SIM_THRESHOLD and margin < 0.35:
                    return best_sample["category"], float(best_sim), "学习样本匹配"
        except Exception:
            pass

    if conf < 0.05:
        return "其他", conf, "低置信度归入其他"
    return best, conf, ("关键词+语义" if vec_ok else "关键词规则")


def learn_from_correction(doc_id: int, category: str):
    """用户手动修正分类后调用：标记学习信号并刷新样本缓存。"""
    db.update_document(doc_id, category=category, category_manual=1)
    _invalidate_samples()
