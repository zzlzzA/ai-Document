# -*- coding: utf-8 -*-
"""V2.0 本地离线模式 RAG 端到端测试。"""
import os
import sys

sys.path.insert(0, r"E:\个人\项目\aiwenjian")

from backend import db, llm, rag

# 切换到本地离线模式
llm.update_settings({"llm_mode": "local"})
print("模式:", llm.get_settings()["mode"], "| 就绪:", llm.is_configured())

# 有资料问答
print("\n[1] 有资料问答（本地推理）")
r = rag.answer("合同里付款方式是怎么约定的？请列出具体比例")
print("回答:", r["answer"][:200])
print("来源:", [s["name"] for s in r["sources"]], "| llm_ok:", r["llm_ok"])

# 无资料防幻觉
print("\n[2] 无资料防幻觉（本地推理）")
r2 = rag.answer("量子咖啡机的制作方法")
print("回答:", r2["answer"][:120], "| no_result:", r2["no_result"])

# 还原 API 模式
llm.update_settings({"llm_mode": "api"})
print("\n已还原 API 模式")
