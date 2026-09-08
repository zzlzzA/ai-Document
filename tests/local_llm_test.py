# -*- coding: utf-8 -*-
"""本地离线模型验证：GGUF 头 + 加载 + 问答。"""
import os
import sys
import time

sys.path.insert(0, r"E:\个人\项目\aiwenjian")

from backend import config

path = config.LOCAL_MODEL_PATH
print("GGUF:", path)
print("size:", os.path.getsize(path))

# 1) GGUF 魔数校验（GGUF 文件头 = 0x46554747 "GGUF" + 版本）
with open(path, "rb") as f:
    head = f.read(8)
print("magic:", head[:4], "OK" if head[:4] == b"GGUF" else "BAD!")

# 2) 加载 + 推理
print("\n加载模型中（CPU 推理，首次约 30-60 秒）…")
t0 = time.time()
from llama_cpp import Llama

llm = Llama(
    model_path=path,
    n_ctx=config.LOCAL_LLM_CTX,
    n_threads=config.LOCAL_LLM_THREADS,
    n_batch=512,
    verbose=False,
)
print(f"加载完成，耗时 {time.time()-t0:.1f}s")

t0 = time.time()
out = llm.create_chat_completion(
    messages=[
        {"role": "system", "content": "你是一名严谨的本地知识库问答助手，用简洁的中文回答。"},
        {"role": "user", "content": "用一句话介绍你自己。"},
    ],
    temperature=0.3,
    max_tokens=128,
)
answer = out["choices"][0]["message"]["content"].strip()
print(f"推理耗时 {time.time()-t0:.1f}s")
print("回答:", answer)
