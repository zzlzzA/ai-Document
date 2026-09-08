# -*- coding: utf-8 -*-
"""大模型推理：用户自行填写 API 地址/密钥/模型（设置页）。"""
import json
import threading

import requests

from . import config, db

_lock = threading.Lock()


class LLMUnavailable(Exception):
    pass


def get_settings():
    temperature = float(db.get_setting("llm_temperature", config.LLM_TEMPERATURE))
    max_tokens = int(db.get_setting("llm_max_tokens", config.LLM_MAX_TOKENS))
    api_key = db.get_setting("llm_api_key", config.LLM_API_KEY)
    return {
        "mode": "custom",
        "api_preconfigured": bool(config.LLM_API_KEY),
        "api_base": db.get_setting("llm_api_base", config.LLM_API_BASE),
        "api_key": api_key,
        "api_key_masked": "••••••" + api_key[-4:] if len(api_key) > 4 else "",
        "model": db.get_setting("llm_model", config.LLM_MODEL),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }


def update_settings(patch: dict):
    allowed = {"llm_api_base", "llm_api_key", "llm_model",
               "llm_temperature", "llm_max_tokens"}
    for k, v in patch.items():
        if k in allowed:
            db.set_setting(k, v)


def is_configured() -> bool:
    s = get_settings()
    return bool(s["api_key"])


def _chat_api(messages, temperature=None, max_tokens=None) -> str:
    s = get_settings()
    if not s["api_key"]:
        raise LLMUnavailable("API Key 未配置")
    url = s["api_base"].rstrip("/") + "/chat/completions"
    payload = {
        "model": s["model"],
        "messages": messages,
        "temperature": temperature if temperature is not None else s["temperature"],
        "max_tokens": max_tokens or s["max_tokens"],
        "stream": False,
    }
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {s['api_key']}", "Content-Type": "application/json"},
        json=payload,
        timeout=config.LLM_TIMEOUT,
    )
    if resp.status_code != 200:
        raise LLMUnavailable(f"API 返回 {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        raise LLMUnavailable(f"API 响应格式异常: {json.dumps(data, ensure_ascii=False)[:200]}")


def chat(messages, temperature=None, max_tokens=None) -> str:
    """统一入口：使用设置页配置的 API（OpenAI 兼容）。"""
    return _chat_api(messages, temperature, max_tokens)
