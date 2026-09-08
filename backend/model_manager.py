# -*- coding: utf-8 -*-
"""V2.0 本地离线模型管理器：检测 GGUF 文件、推理库、加载状态。"""
import os

from . import config

_llama_lib_ok = None


def llama_lib_available() -> bool:
    global _llama_lib_ok
    if _llama_lib_ok is None:
        try:
            import llama_cpp  # noqa
            _llama_lib_ok = True
        except ImportError:
            _llama_lib_ok = False
    return _llama_lib_ok


def model_info() -> dict:
    """本地模型状态（用于设置页展示）。"""
    path = config.LOCAL_MODEL_PATH
    size = os.path.getsize(path) if os.path.exists(path) else 0
    return {
        "name": config.LOCAL_MODEL_NAME,
        "path": path,
        "installed": size > 100 * 1024 * 1024,   # >100MB 视为有效（防下载中断残留）
        "size": size,
        "expected": config.LOCAL_MODEL_EXPECTED_BYTES,
        "download_url": config.LOCAL_MODEL_URL,
        "llama_lib": llama_lib_available(),
        "threads": config.LOCAL_LLM_THREADS,
        "context": config.LOCAL_LLM_CTX,
    }


def model_ready() -> bool:
    info = model_info()
    return info["installed"] and info["llama_lib"]
