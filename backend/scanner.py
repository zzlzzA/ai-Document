# -*- coding: utf-8 -*-
"""文档扫描（PRD 3.1.1）：监控目录扫描、MD5 去重、忽略规则、来源标记。
隐私规则：只扫描并列出候选，不静默入库；入库由用户确认后触发。
"""
import hashlib
import os

from . import config, db


def compute_md5(path: str, chunk_size=1 << 20) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk_size)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def get_ignore_rules() -> dict:
    return {
        "files": db.get_setting("ignore_files", []),
        "dirs": db.get_setting("ignore_dirs", []),
        "exts": db.get_setting("ignore_exts", []),
    }


def set_ignore_rules(rules: dict):
    for k in ("files", "dirs", "exts"):
        if k in rules:
            db.set_setting("ignore_" + k, list(rules[k]))


def is_ignored(path: str) -> bool:
    rules = get_ignore_rules()
    norm = os.path.normcase(os.path.abspath(path))
    if norm in {os.path.normcase(p) for p in rules["files"]}:
        return True
    ext = os.path.splitext(path)[1].lower()
    if ext in {e.lower() if e.startswith(".") else "." + e.lower() for e in rules["exts"]}:
        return True
    for d in rules["dirs"]:
        dnorm = os.path.normcase(os.path.abspath(d))
        if norm.startswith(dnorm + os.sep) or norm == dnorm:
            return True
    return False


def walk_documents(root: str):
    """递归遍历目录，返回支持格式的文件绝对路径列表（跳过忽略规则）。"""
    if not os.path.isdir(root):
        return []
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        # 剪枝忽略目录
        dirnames[:] = [
            d for d in dirnames
            if not is_ignored(os.path.join(dirpath, d))
        ]
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            ext = os.path.splitext(p)[1].lower()
            if ext not in config.SUPPORTED_EXTS:
                continue
            if is_ignored(p):
                continue
            found.append(p)
    return found


def scan_candidates(roots: list):
    """扫描多个目录，返回待入库候选（已存在的文件标记 duplicate）。"""
    seen = set()
    candidates = []
    for root in roots:
        for p in walk_documents(root):
            if p in seen:
                continue
            seen.add(p)
            try:
                md5 = compute_md5(p)
                st = os.stat(p)
                candidates.append({
                    "path": p,
                    "name": os.path.basename(p),
                    "ext": os.path.splitext(p)[1].lower(),
                    "size": st.st_size,
                    "modified_at": st.st_mtime,
                    "md5": md5,
                    "duplicate": db.doc_exists_by_md5(md5),
                    "dir": os.path.basename(os.path.dirname(p)),
                })
            except OSError as e:
                candidates.append({
                    "path": p, "name": os.path.basename(p), "size": 0,
                    "duplicate": False, "error": str(e), "dir": "",
                })
    # 未入库的优先展示，已存在的排在后面
    candidates.sort(key=lambda c: (c.get("duplicate", False), c["path"].lower()))
    return candidates


def get_monitor_dirs() -> list:
    return db.get_setting("monitor_dirs", [])


def set_monitor_dirs(dirs: list):
    db.set_setting("monitor_dirs", list(dirs))
