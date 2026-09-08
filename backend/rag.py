# -*- coding: utf-8 -*-
"""RAG 溯源问答（PRD 3.5）：
- 混合检索 → 组装带来源上下文 → LLM 生成 → 强制附参考来源
- 无资料固定回复，禁止编造；记录引用与反馈信号
"""
import re

from . import config, db, llm, retriever

_SYSTEM_PROMPT = (
    "你是一名严谨的本地知识库问答助手。只能依据【参考资料】中的内容回答用户问题。"
    "回答要求：\n"
    "1. 引用资料中的事实，不要编造资料中没有的信息；\n"
    "2. 若资料不足以回答，直接说明资料未覆盖，不要猜测；\n"
    "3. 多份资料信息冲突时，分别说明各资料的表述；\n"
    "4. 用简洁的中文回答，关键数字、条款、时间要准确。\n"
    "5. 回答末尾必须列出实际引用的资料编号，格式：【来源：资料1、资料3】；未引用任何资料时写【来源：无】。"
)

_SOURCE_RE = re.compile(r"【来源：([^】]+)】")


def _extract_cited_indices(answer_text: str):
    """从回答末尾提取引用的资料编号（1-based），返回集合；未匹配返回 None。"""
    m = _SOURCE_RE.search(answer_text)
    if not m:
        return None
    raw = m.group(1)
    if "无" in raw or not raw.strip():
        return set()
    nums = set()
    for token in re.findall(r"\d+", raw):
        try:
            nums.add(int(token))
        except ValueError:
            pass
    return nums


def answer(question: str, k: int = None):
    """返回 {answer, sources, related, no_result, vector_used, llm_ok}。"""
    hits, vec_ok = retriever.search(question, k=k or config.RAG_CONTEXT_LIMIT * 2)

    if not hits:
        return {
            "answer": config.NO_ANSWER_REPLY,
            "sources": [], "related": [], "no_result": True,
            "vector_used": vec_ok, "llm_ok": False,
        }

    # 送入 LLM 的片段（截断超长片段）
    ctx_hits = hits[:config.RAG_CONTEXT_LIMIT]
    context_parts = []
    for i, h in enumerate(ctx_hits, 1):
        text = (h["text"] or "")[:2000]
        context_parts.append(f"[资料{i}] 来自《{h['name']}》：\n{text}")
    context = "\n\n".join(context_parts)

    user_prompt = (
        f"【参考资料】\n{context}\n\n"
        f"【用户问题】\n{question}\n\n"
        f"请依据参考资料回答问题。回答末尾列出引用的资料编号，格式：【来源：资料1、资料3】"
    )

    sources = [{
        "doc_id": h["doc_id"], "name": h["name"], "category": h["category"],
        "start": h["start"], "text": (h["text"] or "")[:500], "score": h["score"],
    } for h in ctx_hits]

    # 记录引用（学习信号）
    seen = set()
    for h in ctx_hits:
        if h["doc_id"] not in seen:
            seen.add(h["doc_id"])
            db.add_cite(h["doc_id"])

    # 调用 LLM
    llm_ok = False
    if not llm.is_configured():
        answer_text = (
            "已检索到相关资料（见下方来源），但 AI 服务尚未配置："
            "请到「设置」页填写 API 地址与密钥后重试。"
        )
        related = _related(question)
        return {
            "answer": answer_text, "sources": sources, "related": related,
            "no_result": False, "vector_used": vec_ok, "llm_ok": llm_ok,
        }

    try:
        answer_text = llm.chat([
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ])
        llm_ok = True
    except llm.LLMUnavailable as e:
        answer_text = f"AI 服务调用失败：{e}\n\n已检索到以下相关资料，可先行查看："
        for s in sources:
            answer_text += f"\n- 《{s['name']}》片段：{s['text'][:120]}"
    except Exception as e:
        answer_text = f"AI 服务异常：{e}\n\n已检索到相关资料（见下方来源）。"
    if not answer_text or not answer_text.strip():
        answer_text = config.NO_ANSWER_REPLY

    # 解析 LLM 标注的引用编号，只保留实际被引用的资料作为来源
    cited = _extract_cited_indices(answer_text)
    # 从回答正文中移除【来源：...】标记（来源由前端单独渲染）
    answer_text = _SOURCE_RE.sub("", answer_text).strip()

    if cited and len(cited) > 0:
        cited_sources = [s for i, s in enumerate(sources, 1) if i in cited]
    else:
        # LLM 未按格式标注或标注为空时，降级返回全部检索片段
        cited_sources = sources
    # 来源只保留文档标识，不返回片段内容；按 doc_id 去重
    seen_ids = set()
    deduped = []
    for s in cited_sources:
        if s["doc_id"] not in seen_ids:
            seen_ids.add(s["doc_id"])
            deduped.append({"doc_id": s["doc_id"], "name": s["name"]})
    cited_sources = deduped

    return {
        "answer": answer_text, "sources": cited_sources, "related": _related(question),
        "no_result": False, "vector_used": vec_ok, "llm_ok": llm_ok,
    }


def _related(question: str, n: int = 5):
    """对话右侧动态推荐相关文档。"""
    docs = retriever.search_documents(question, k=n)
    return [{
        "doc_id": d["doc_id"], "name": d["name"], "score": d["score"],
        "snippet": (d["text"] or "")[:120],
    } for d in docs]


def feedback(query_text: str, doc_id: int, value: int):
    """问答反馈学习：赞 +1 / 踩 -1，沉淀到行为库。"""
    db.add_feedback(doc_id, 1 if value > 0 else -1)
    return {"ok": True}
