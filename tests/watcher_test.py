# -*- coding: utf-8 -*-
"""V2.0 后台扫描通知验证。"""
import os
import sys
import tempfile
import time

sys.path.insert(0, r"E:\个人\项目\aiwenjian")

from backend import db, scanner, watcher

tmp = tempfile.mkdtemp(prefix="aiwj_watch_")
p1 = os.path.join(tmp, "新项目计划书.txt")
with open(p1, "w", encoding="utf-8") as f:
    f.write("新项目计划书：2026年Q4 智能客服系统建设方案。")

# 配置监控目录
scanner.set_monitor_dirs([tmp])
print("监控目录:", scanner.get_monitor_dirs())

# 等待文件写入稳定（watcher 有 10s 保护，防扫描到未写完的文件）
time.sleep(11)

# 模拟轮询扫描
added = watcher.scan_once()
print("首次扫描新增通知:", added)

# 再次扫描（应去重，不重复通知）
added2 = watcher.scan_once()
print("二次扫描新增通知:", added2)

# 已入库的文件不应再通知
from backend import pipeline
import time
task_id = pipeline.start_ingest([{"path": p1}], "测试")
for _ in range(40):
    t = db.task_get(task_id)
    if t and t["status"] == "done":
        break
    time.sleep(0.3)
added3 = watcher.scan_once()
print("入库后扫描新增通知:", added3)

pending = db.list_notifications(status="pending")
print("pending 通知:", [(n["name"], n["status"]) for n in pending])

# 清理
scanner.set_monitor_dirs([])
db.get_conn().execute("DELETE FROM notifications")
db.get_conn().commit()
db.delete_document(1) if db.get_document(1) else None
print("测试完成，已清理")
