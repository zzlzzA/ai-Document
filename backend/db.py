# -*- coding: utf-8 -*-
"""SQLite 元数据存储：文档、行为、分类、标签、设置。线程安全。"""
import json
import sqlite3
import threading
import time

from . import config

_lock = threading.RLock()
_conn = None


def get_conn():
    global _conn
    with _lock:
        if _conn is None:
            _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _init_schema(_conn)
            _migrate(_conn)
        return _conn


def _migrate(conn):
    """轻量列迁移：老库补新增列。"""
    with _lock:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(documents)").fetchall()}
        if "favorite" not in cols:
            conn.execute("ALTER TABLE documents ADD COLUMN favorite INTEGER DEFAULT 0")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_fav ON documents(favorite)")
        conn.commit()


def _init_schema(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT NOT NULL UNIQUE,          -- 文件绝对路径（去重依据之一）
        md5 TEXT NOT NULL,                  -- 文件 MD5（全局去重）
        name TEXT NOT NULL,                 -- 文件名（含后缀）
        ext TEXT NOT NULL,                  -- 后缀
        size INTEGER DEFAULT 0,             -- 字节
        category TEXT DEFAULT '其他',       -- 当前分类
        category_manual INTEGER DEFAULT 0,  -- 是否人工修正过分类（学习信号）
        tags TEXT DEFAULT '[]',             -- JSON 标签数组
        summary TEXT DEFAULT '',            -- 摘要（首段）
        text_len INTEGER DEFAULT 0,         -- 解析文本长度
        chunk_count INTEGER DEFAULT 0,      -- 切片数
        parse_ok INTEGER DEFAULT 0,         -- 解析是否成功
        parse_msg TEXT DEFAULT '',          -- 解析失败原因
        source TEXT DEFAULT 'manual',       -- manual | 自动-目录名
        created_at REAL DEFAULT 0,          -- 入库时间戳
        modified_at REAL DEFAULT 0,         -- 文件修改时间戳
        opened_at REAL DEFAULT 0,           -- 最近打开时间
        visit_count INTEGER DEFAULT 0,      -- 打开次数
        cite_count INTEGER DEFAULT 0,       -- 问答引用次数
        fb_score REAL DEFAULT 0,            -- 反馈净得分（赞+1 踩-1）
        favorite INTEGER DEFAULT 0          -- 收藏（1=已收藏，文档库星标）
    );
    CREATE INDEX IF NOT EXISTS idx_doc_cat ON documents(category);
    CREATE INDEX IF NOT EXISTS idx_doc_md5 ON documents(md5);

    CREATE TABLE IF NOT EXISTS behavior (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id INTEGER NOT NULL,
        kind TEXT NOT NULL,                 -- open | click | cite | like | dislike
        ts REAL DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_bhv_doc ON behavior(doc_id, kind);

    CREATE TABLE IF NOT EXISTS chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id INTEGER NOT NULL,
        text TEXT NOT NULL,
        start INTEGER DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);

    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );

    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        status TEXT NOT NULL,               -- running | done | error
        total INTEGER DEFAULT 0,
        done INTEGER DEFAULT 0,
        failed INTEGER DEFAULT 0,
        message TEXT DEFAULT '',
        result TEXT DEFAULT '[]',
        ts REAL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT NOT NULL,
        md5 TEXT NOT NULL,
        name TEXT NOT NULL,
        size INTEGER DEFAULT 0,
        dir TEXT DEFAULT '',
        status TEXT DEFAULT 'pending',      -- pending | ingested | dismissed
        ts REAL DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_notify_status ON notifications(status);
    """)
    conn.commit()


# ---------- 文档 CRUD ----------

def add_document(doc: dict) -> int:
    conn = get_conn()
    with _lock:
        cur = conn.execute(
            """INSERT OR IGNORE INTO documents
            (path, md5, name, ext, size, category, category_manual, tags, summary,
             text_len, chunk_count, parse_ok, parse_msg, source, created_at, modified_at)
            VALUES (:path,:md5,:name,:ext,:size,:category,:category_manual,:tags,:summary,
             :text_len,:chunk_count,:parse_ok,:parse_msg,:source,:created_at,:modified_at)""",
            doc,
        )
        conn.commit()
        return cur.lastrowid


def doc_exists_by_md5(md5: str) -> bool:
    conn = get_conn()
    with _lock:
        row = conn.execute("SELECT id FROM documents WHERE md5=?", (md5,)).fetchone()
        return row is not None


def doc_exists_by_path(path: str) -> bool:
    conn = get_conn()
    with _lock:
        row = conn.execute("SELECT id FROM documents WHERE path=?", (path,)).fetchone()
        return row is not None


def get_document(doc_id: int):
    conn = get_conn()
    with _lock:
        return conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()


def set_favorite(doc_id: int, fav: bool):
    """收藏 / 取消收藏。"""
    conn = get_conn()
    with _lock:
        conn.execute("UPDATE documents SET favorite=? WHERE id=?", (1 if fav else 0, doc_id))
        conn.commit()


def list_favorites():
    """收藏文档列表（首页收藏板块）。"""
    conn = get_conn()
    with _lock:
        rows = conn.execute(
            "SELECT * FROM documents WHERE favorite=1 ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def list_documents(category=None, tag=None, q=None, source=None, ext=None, created_from=None, page=1, page_size=50):
    conn = get_conn()
    where, args = [], []
    if category:
        where.append("category=?")
        args.append(category)
    if tag:
        where.append("tags LIKE ?")
        args.append(f'%"{tag}"%')
    if q:
        where.append("(name LIKE ? OR summary LIKE ?)")
        args += [f"%{q}%", f"%{q}%"]
    if source:
        where.append("source=?")
        args.append(source)
    if ext:
        where.append("ext=?")
        e = ext.strip().lower()
        args.append(e if e.startswith(".") else "." + e)
    if created_from:
        where.append("created_at >= ?")
        args.append(created_from)
    sql = "SELECT * FROM documents"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    args += [page_size, (page - 1) * page_size]
    with _lock:
        rows = conn.execute(sql, args).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) c FROM documents" + (" WHERE " + " AND ".join(where) if where else ""),
            args[:-2] if where else [],
        ).fetchone()["c"]
    return [dict(r) for r in rows], total


def update_document(doc_id: int, **fields):
    conn = get_conn()
    allowed = {"name", "category", "category_manual", "tags", "summary",
               "parse_ok", "parse_msg", "text_len", "chunk_count"}
    sets = [f"{k}=?" for k in fields if k in allowed]
    if not sets:
        return
    vals = [json.dumps(fields[k]) if k == "tags" else fields[k] for k in fields if k in allowed]
    with _lock:
        conn.execute(f"UPDATE documents SET {', '.join(sets)} WHERE id=?", (*vals, doc_id))
        conn.commit()


def touch_visit(doc_id: int):
    conn = get_conn()
    with _lock:
        conn.execute(
            "UPDATE documents SET visit_count=visit_count+1, opened_at=? WHERE id=?",
            (time.time(), doc_id),
        )
        conn.execute("INSERT INTO behavior(doc_id, kind, ts) VALUES (?,?,?)",
                     (doc_id, "open", time.time()))
        conn.commit()


def add_cite(doc_id: int):
    conn = get_conn()
    with _lock:
        conn.execute("UPDATE documents SET cite_count=cite_count+1 WHERE id=?",
                     (doc_id,))
        conn.execute("INSERT INTO behavior(doc_id, kind, ts) VALUES (?,?,?)",
                     (doc_id, "cite", time.time()))
        conn.commit()


def add_feedback(doc_id: int, value: int):
    """value: 1 赞 / -1 踩"""
    conn = get_conn()
    with _lock:
        conn.execute("UPDATE documents SET fb_score=fb_score+? WHERE id=?",
                     (value, doc_id))
        conn.execute("INSERT INTO behavior(doc_id, kind, ts) VALUES (?,?,?)",
                     (doc_id, "like" if value > 0 else "dislike", time.time()))
        conn.commit()


def delete_document(doc_id: int):
    conn = get_conn()
    with _lock:
        conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        conn.execute("DELETE FROM behavior WHERE doc_id=?", (doc_id,))
        conn.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
        conn.commit()


def add_chunks(doc_id: int, chunks: list):
    """切片文本入 SQLite（BM25 语料，独立于向量库，向量不可用时检索仍可用）。"""
    conn = get_conn()
    with _lock:
        conn.executemany(
            "INSERT INTO chunks(doc_id, text, start) VALUES (?,?,?)",
            [(doc_id, c["text"], c.get("start", 0)) for c in chunks],
        )
        conn.commit()


def all_chunks():
    conn = get_conn()
    with _lock:
        return [dict(r) for r in conn.execute(
            "SELECT c.id chunk_id, c.doc_id, c.text, c.start, d.name, d.category "
            "FROM chunks c LEFT JOIN documents d ON c.doc_id=d.id ORDER BY c.id"
        ).fetchall()]


def chunk_count():
    conn = get_conn()
    with _lock:
        return conn.execute("SELECT COUNT(*) c FROM chunks").fetchone()["c"]


def all_documents():
    conn = get_conn()
    with _lock:
        return [dict(r) for r in conn.execute("SELECT * FROM documents").fetchall()]


def categories_with_count():
    conn = get_conn()
    with _lock:
        rows = conn.execute(
            "SELECT category, COUNT(*) c FROM documents GROUP BY category ORDER BY c DESC"
        ).fetchall()
    return [{"name": r["category"], "count": r["c"]} for r in rows]


def all_tags():
    conn = get_conn()
    with _lock:
        rows = conn.execute("SELECT tags FROM documents WHERE tags != '[]'").fetchall()
    counter = {}
    for r in rows:
        for t in json.loads(r["tags"]):
            counter[t] = counter.get(t, 0) + 1
    return sorted([{"name": k, "count": v} for k, v in counter.items()], key=lambda x: -x["count"])


def stats():
    conn = get_conn()
    with _lock:
        total = conn.execute("SELECT COUNT(*) c FROM documents").fetchone()["c"]
        chunks = conn.execute("SELECT COALESCE(SUM(chunk_count),0) c FROM documents").fetchone()["c"]
        cats = conn.execute("SELECT COUNT(DISTINCT category) c FROM documents").fetchone()["c"]
        fail = conn.execute("SELECT COUNT(*) c FROM documents WHERE parse_ok=0").fetchone()["c"]
        ext_rows = conn.execute("SELECT ext, COUNT(*) c FROM documents GROUP BY ext").fetchall()
    formats = sorted(
        [{"ext": (r["ext"] or "").lstrip(".").upper() or "?", "count": r["c"]} for r in ext_rows],
        key=lambda x: -x["count"],
    )
    return {"documents": total, "chunks": chunks, "categories": cats, "parse_failed": fail, "formats": formats}


# ---------- 设置 ----------

def get_setting(key, default=None):
    conn = get_conn()
    with _lock:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if row is None:
        return default
    try:
        return json.loads(row["value"])
    except Exception:
        return row["value"]


def set_setting(key, value):
    conn = get_conn()
    with _lock:
        conn.execute(
            "INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)",
            (key, json.dumps(value, ensure_ascii=False)),
        )
        conn.commit()


# ---------- 任务 ----------

def task_begin(task_id: str, kind: str, total: int = 0):
    conn = get_conn()
    with _lock:
        conn.execute(
            "INSERT OR REPLACE INTO tasks(id,kind,status,total,done,failed,message,result,ts) "
            "VALUES (?,?,?,?,0,0,'','[]',?)",
            (task_id, kind, "running", total, time.time()),
        )
        conn.commit()


def task_update(task_id: str, done=None, failed=None, status=None, message=None, result=None):
    conn = get_conn()
    sets, args = [], []
    if done is not None:
        sets.append("done=?"); args.append(done)
    if failed is not None:
        sets.append("failed=?"); args.append(failed)
    if status is not None:
        sets.append("status=?"); args.append(status)
    if message is not None:
        sets.append("message=?"); args.append(message)
    if result is not None:
        sets.append("result=?"); args.append(json.dumps(result, ensure_ascii=False))
    if not sets:
        return
    with _lock:
        conn.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id=?", (*args, task_id))
        conn.commit()


def task_get(task_id: str):
    conn = get_conn()
    with _lock:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["result"] = json.loads(d["result"])
    return d


# ---------- 扫描通知（V2.0 后台静默扫描） ----------

def add_notification(nt: dict) -> bool:
    """返回 False 表示已存在同 md5 的 pending 通知。"""
    conn = get_conn()
    with _lock:
        exists = conn.execute(
            "SELECT id FROM notifications WHERE md5=? AND status='pending'",
            (nt["md5"],),
        ).fetchone()
        if exists:
            return False
        conn.execute(
            "INSERT INTO notifications(path,md5,name,size,dir,status,ts) VALUES (?,?,?,?,?,?,?)",
            (nt["path"], nt["md5"], nt["name"], nt["size"], nt.get("dir", ""),
             "pending", time.time()),
        )
        conn.commit()
        return True


def list_notifications(status="pending", limit=100):
    conn = get_conn()
    with _lock:
        rows = conn.execute(
            "SELECT * FROM notifications WHERE status=? ORDER BY ts DESC LIMIT ?",
            (status, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def set_notification_status(nid: int, status: str):
    conn = get_conn()
    with _lock:
        conn.execute("UPDATE notifications SET status=? WHERE id=?", (status, nid))
        conn.commit()


def pending_notification_count() -> int:
    conn = get_conn()
    with _lock:
        return conn.execute(
            "SELECT COUNT(*) c FROM notifications WHERE status='pending'"
        ).fetchone()["c"]
