# -*- coding: utf-8 -*-
"""新文档提醒（PRD 7.2 / 3.1.1 隐私规则）：
每次进入软件时对监控目录扫描一次（设置页可配置，也可手动「立即扫描一次」），
发现新文件只生成「待入库提醒」（通知），绝不静默入库；用户在前端确认后才进入入库流水线。"""
import os
import threading
import time

from . import config, db, scanner

_lock = threading.Lock()
_running = False
_last_scan = {}


def _is_new_candidate(path: str) -> bool:
    """新文件判定：支持格式 + 未入库 + 无 pending 通知 + 未被忽略。"""
    if os.path.splitext(path)[1].lower() not in config.SUPPORTED_EXTS:
        return False
    if scanner.is_ignored(path):
        return False
    try:
        md5 = scanner.compute_md5(path)
    except OSError:
        return False
    if db.doc_exists_by_md5(md5):
        return False
    return md5


def scan_once() -> int:
    """扫描一轮监控目录，新增 pending 通知，返回新增数。"""
    dirs = scanner.get_monitor_dirs()
    added = 0
    for root in dirs:
        if not os.path.isdir(root):
            continue
        for p in scanner.walk_documents(root):
            md5 = _is_new_candidate(p)
            if not md5:
                continue
            try:
                st = os.stat(p)
                size, mtime = st.st_size, st.st_mtime
            except OSError:
                size, mtime = 0, 0
            # 文件刚写入（<10s 内修改过）可能未写完，跳过本轮
            if time.time() - mtime < 10:
                continue
            ok = db.add_notification({
                "path": p, "md5": md5, "name": os.path.basename(p),
                "size": size, "dir": os.path.basename(os.path.dirname(p)),
            })
            if ok:
                added += 1
    return added


def _once():
    """进入软件时对监控目录扫描一轮，完成后线程即退出（不做循环轮询）。"""
    global _running
    try:
        n = scan_once()
        if n:
            print(f"[watcher] 检测到 {n} 个新文档，已生成待确认提醒", flush=True)
    except Exception as e:
        print(f"[watcher] 扫描异常: {e}", flush=True)
    finally:
        _running = False


def start():
    """每次进入软件时扫描一次监控目录（后台线程，不阻塞启动）。"""
    global _running
    with _lock:
        if _running:
            return
        _running = True
        t = threading.Thread(target=_once, daemon=True, name="doc-watcher")
        t.start()


def stop():
    global _running
    _running = False
