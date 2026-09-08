# -*- coding: utf-8 -*-
"""FastAPI 路由层：全部本地服务，前端通过 HTTP 调用。"""
import json
import os
import sys

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import classifier, config, db, llm, pipeline, rag, recommender, scanner, vector_store, watcher

app = FastAPI(title="AIWenJian 本地知识库", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


def _frontend_dir():
    """前端静态资源目录：
    - 开发模式：项目 frontend/
    - 打包运行：PyInstaller 资源目录（_MEIPASS 或 _internal）下的 frontend/
    """
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "frontend")
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")


FRONTEND_DIR = _frontend_dir()


@app.on_event("startup")
def _startup():
    # V2.0：后台静默扫描（仅在配置了监控目录时工作，新文件只提醒不自动入库）
    watcher.start()


# ---------- 请求模型 ----------

class ScanReq(BaseModel):
    directories: list[str]


class IngestReq(BaseModel):
    files: list[dict]
    source: str = "manual"


class DocUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    tags: list[str] | None = None


class FavoriteUpdate(BaseModel):
    favorite: bool


class DocCategory(BaseModel):
    category: str


class QueryReq(BaseModel):
    question: str
    k: int | None = None


class FeedbackReq(BaseModel):
    doc_id: int
    value: int  # 1 / -1


class SettingsReq(BaseModel):
    llm_api_base: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_temperature: float | None = None
    llm_max_tokens: int | None = None


class IgnoreReq(BaseModel):
    files: list[str] | None = None
    dirs: list[str] | None = None
    exts: list[str] | None = None


# ---------- 基础 ----------

@app.get("/api/health")
def health():
    return {
        "ok": True,
        "embedding": {"model": config.EMBED_MODEL, "available": _safe_embed_check()},
        "llm_configured": llm.is_configured(),
        "llm_mode": llm.get_settings()["mode"],
        "notifications": db.pending_notification_count(),
        "stats": db.stats(),
    }


# ---------- 背景图片（V2.5 设置页 · 更改背景） ----------

_BG_DIR = os.path.join(config.DATA_DIR, "backgrounds")
_BG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
_BG_LEGACY = os.path.join(_BG_DIR, "current.bgimg")  # 旧版本保存的文件名（兼容）


def _bg_current() -> str | None:
    """返回当前背景文件路径（按真实扩展名保存，保证 MIME 正确）。"""
    for ext in _BG_EXTS:
        p = os.path.join(_BG_DIR, "current" + ext)
        if os.path.exists(p):
            return p
    if os.path.exists(_BG_LEGACY):
        return _BG_LEGACY
    return None


def _bg_remove_all():
    for ext in _BG_EXTS:
        p = os.path.join(_BG_DIR, "current" + ext)
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
    if os.path.exists(_BG_LEGACY):
        try:
            os.remove(_BG_LEGACY)
        except OSError:
            pass


@app.post("/api/background")
async def upload_background(bg: UploadFile = File(...)):
    """上传背景图片（仅本地保存，不上传云端）。"""
    ext = os.path.splitext(bg.filename or "")[1].lower()
    if ext not in _BG_EXTS:
        raise HTTPException(400, "仅支持 JPG/PNG/WEBP 图片")
    os.makedirs(_BG_DIR, exist_ok=True)
    _bg_remove_all()
    dst = os.path.join(_BG_DIR, "current" + ext)
    try:
        with open(dst, "wb") as out:
            import shutil
            shutil.copyfileobj(bg.file, out)
    except OSError:
        raise HTTPException(500, "背景图片保存失败")
    return {"ok": True, "ext": ext}


@app.get("/api/background")
def get_background():
    p = _bg_current()
    if not p:
        raise HTTPException(404, "未设置背景图")
    return FileResponse(p)


@app.delete("/api/background")
def delete_background():
    _bg_remove_all()
    return {"ok": True}


# ---------- 扫描通知（V2.0 后台静默扫描确认入库） ----------

@app.get("/api/notifications")
def notifications(status: str = "pending"):
    return {
        "pending": db.pending_notification_count(),
        "items": db.list_notifications(status=status),
    }


@app.post("/api/notifications/{nid}/ingest")
def notification_ingest(nid: int):
    rows = db.list_notifications(status="pending")
    nt = next((n for n in rows if n["id"] == nid), None)
    if not nt:
        raise HTTPException(404, "通知不存在或已处理")
    if not os.path.exists(nt["path"]):
        db.set_notification_status(nid, "dismissed")
        raise HTTPException(404, "文件已不存在，通知已自动忽略")
    task_id = pipeline.start_ingest([{"path": nt["path"]}], f"自动-{nt['dir']}")
    db.set_notification_status(nid, "ingested")
    return {"task_id": task_id}


@app.post("/api/notifications/ingest-all")
def notification_ingest_all():
    rows = db.list_notifications(status="pending")
    valid = [n for n in rows if os.path.exists(n["path"])]
    if not valid:
        return {"task_id": None, "skipped": len(rows)}
    task_id = pipeline.start_ingest(
        [{"path": n["path"]} for n in valid], f"自动-{valid[0]['dir']}"
    )
    for n in valid:
        db.set_notification_status(n["id"], "ingested")
    return {"task_id": task_id, "skipped": len(rows) - len(valid)}


@app.post("/api/notifications/{nid}/dismiss")
def notification_dismiss(nid: int):
    db.set_notification_status(nid, "dismissed")
    return {"ok": True}


@app.post("/api/notifications/dismiss-all")
def notification_dismiss_all():
    for n in db.list_notifications(status="pending"):
        db.set_notification_status(n["id"], "dismissed")
    return {"ok": True}


def _safe_embed_check():
    try:
        return __import__("backend.embedder", fromlist=["is_available"]).is_available()
    except Exception:
        return False


@app.get("/api/stats")
def stats():
    return db.stats()


# ---------- 扫描 ----------

@app.post("/api/scan")
def scan(req: ScanReq):
    dirs = [d for d in req.directories if d and os.path.isdir(d)]
    if not dirs:
        raise HTTPException(400, "目录不存在或不可访问")
    try:
        cands = scanner.scan_candidates(dirs)
    except Exception as e:
        raise HTTPException(500, f"扫描失败: {e}")
    return {
        "scanned": len(cands),
        "new": sum(1 for c in cands if not c.get("duplicate")),
        "duplicates": sum(1 for c in cands if c.get("duplicate")),
        "candidates": cands[:500],
    }


@app.get("/api/default-downloads")
def default_downloads():
    return {"path": pipeline._default_download_dir()}


# ---------- 入库 ----------

@app.post("/api/upload")
async def upload_files(files: list[UploadFile] = File(...)):
    """选择文档上传入库（V2.1）：浏览器打开本地文件选择器 → 上传原件 → 后台入库。
    原件保存于本地 uploads 目录，全程不出本机。"""
    import shutil
    import uuid

    saved, skipped = [], 0
    for f in files:
        orig = os.path.basename(f.filename or "file")
        ext = os.path.splitext(orig)[1].lower()
        if ext not in config.SUPPORTED_EXTS:
            skipped += 1
            continue
        if not f.size:
            skipped += 1
            continue
        fname = f"{uuid.uuid4().hex[:8]}_{orig}"
        dst = os.path.join(config.UPLOAD_DIR, fname)
        try:
            with open(dst, "wb") as out:
                shutil.copyfileobj(f.file, out)
            saved.append({"path": dst, "name": orig})
        except OSError:
            skipped += 1
    if not saved:
        raise HTTPException(400, "没有可导入的文档（支持 PDF/DOCX/DOC/XLSX/PPTX/TXT/MD）")
    task_id = pipeline.start_ingest([{"path": s["path"]} for s in saved], "手动")
    return {"task_id": task_id, "count": len(saved), "skipped": skipped}

@app.post("/api/ingest")
def ingest(req: IngestReq):
    files = [f for f in req.files if f.get("path")]
    if not files:
        raise HTTPException(400, "没有可入库的文件")
    task_id = pipeline.start_ingest(files, req.source)
    return {"task_id": task_id}


@app.get("/api/tasks/{task_id}")
def task(task_id: str):
    t = db.task_get(task_id)
    if t is None:
        raise HTTPException(404, "任务不存在")
    return t


# ---------- 文档管理 ----------

@app.get("/api/documents")
def documents(category: str = "", tag: str = "", q: str = "", source: str = "",
              ext: str = "", created_from: float = 0, page: int = 1, page_size: int = 50):
    rows, total = db.list_documents(
        category=category or None, tag=tag or None, q=q or None,
        source=source or None, ext=ext or None, created_from=created_from or None,
        page=page, page_size=page_size,
    )
    items = []
    for r in rows:
        d = dict(r)
        d["tags"] = json.loads(d.get("tags") or "[]")
        items.append(d)
    return {"items": items, "total": total, "page": page}


@app.get("/api/documents/{doc_id}")
def document(doc_id: int):
    d = db.get_document(doc_id)
    if not d:
        raise HTTPException(404, "文档不存在")
    return dict(d)


@app.post("/api/documents/{doc_id}/favorite")
def favorite_document(doc_id: int, body: FavoriteUpdate):
    """收藏 / 取消收藏（文档库星标）。"""
    d = db.get_document(doc_id)
    if not d:
        raise HTTPException(404, "文档不存在")
    db.set_favorite(doc_id, body.favorite)
    return {"ok": True, "favorite": body.favorite}


@app.get("/api/favorites")
def favorites():
    """首页收藏文档板块。"""
    rows = db.list_favorites()
    items = []
    for r in rows:
        items.append({
            "id": r["id"], "name": r["name"], "ext": r["ext"], "summary": r["summary"],
            "category": r["category"], "tags": json.loads(r["tags"]),
            "created_at": r["created_at"], "visit_count": r["visit_count"],
            "cite_count": r["cite_count"], "favorite": 1,
        })
    return {"items": items}


@app.patch("/api/documents/{doc_id}")
def update_document(doc_id: int, body: DocUpdate):
    d = db.get_document(doc_id)
    if not d:
        raise HTTPException(404, "文档不存在")
    fields = {}
    if body.name is not None:
        fields["name"] = body.name
    if body.category is not None:
        # 人工修正分类 → 触发学习
        classifier.learn_from_correction(doc_id, body.category)
        fields["category"] = body.category
        fields["category_manual"] = 1
    if body.tags is not None:
        fields["tags"] = body.tags
    if fields:
        db.update_document(doc_id, **fields)
        if "category" in fields:
            _refresh_chunks_category(doc_id, body.category)
    return {"ok": True}


def _refresh_chunks_category(doc_id: int, category: str):
    """分类变更后同步更新向量库元数据。"""
    try:
        col = vector_store._get_collection()
        res = col.get(where={"doc_id": doc_id}, include=[])
        if res["ids"]:
            for i in range(0, len(res["ids"]), 200):
                batch = res["ids"][i:i + 200]
                metas = col.get(ids=batch, include=["metadatas"])["metadatas"]
                for m in metas:
                    m["category"] = category
                col.update(ids=batch, metadatas=metas)
    except Exception:
        pass


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: int):
    d = db.get_document(doc_id)
    if not d:
        raise HTTPException(404, "文档不存在")
    vector_store.delete_document(doc_id)
    db.delete_document(doc_id)
    # 清理手动上传的原件副本（仅限 uploads 目录内）
    p = d["path"]
    if p and os.path.abspath(p).startswith(config.UPLOAD_DIR) and os.path.exists(p):
        try:
            os.remove(p)
        except OSError:
            pass
    return {"ok": True}


@app.post("/api/documents/{doc_id}/open")
def open_document(doc_id: int):
    """本地打开原文件（桌面端体验）。"""
    d = db.get_document(doc_id)
    if not d:
        raise HTTPException(404, "文档不存在")
    p = d["path"]
    if not p or not os.path.exists(p):
        raise HTTPException(404, "原文件缺失（可能已被移动或删除）")
    db.touch_visit(doc_id)
    try:
        os.startfile(p)  # Windows 默认应用打开
    except Exception as e:
        raise HTTPException(500, f"打开失败: {e}")
    return {"ok": True}


# ---------- 分类 / 标签 ----------

@app.get("/api/categories")
def categories():
    rows = db.categories_with_count()
    names = {r["name"] for r in rows}
    for c in config.DEFAULT_CATEGORIES:
        if c not in names:
            rows.append({"name": c, "count": 0})
    return rows


@app.get("/api/tags")
def tags():
    return db.all_tags()


# ---------- 推荐 / 最近 ----------

@app.get("/api/recommend")
def recommend(limit: int = 10, exclude: str = ""):
    ex = [int(x) for x in exclude.split(",") if x.strip().isdigit()]
    return recommender.recommend(limit=limit, exclude_ids=ex)


@app.get("/api/recent")
def recent(limit: int = 10):
    rows, _ = db.list_documents(page=1, page_size=limit)
    return rows


# ---------- RAG 问答 ----------

@app.post("/api/query")
def query(body: QueryReq):
    q = (body.question or "").strip()
    if not q:
        raise HTTPException(400, "问题不能为空")
    try:
        return rag.answer(q, k=body.k)
    except Exception as e:
        raise HTTPException(500, f"问答失败: {e}")


@app.post("/api/feedback")
def feedback(body: FeedbackReq):
    if body.value not in (1, -1):
        raise HTTPException(400, "value 必须为 1 或 -1")
    if not db.get_document(body.doc_id):
        raise HTTPException(404, "文档不存在")
    return rag.feedback("", body.doc_id, body.value)


# ---------- 设置 ----------

@app.get("/api/settings")
def settings():
    s = llm.get_settings()
    s["monitor_dirs"] = scanner.get_monitor_dirs()
    s["ignore"] = scanner.get_ignore_rules()
    return s


@app.post("/api/settings")
def update_settings(body: SettingsReq):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if patch:
        llm.update_settings(patch)
    return llm.get_settings()


@app.post("/api/ignore")
def update_ignore(body: IgnoreReq):
    rules = {}
    if body.files is not None:
        rules["files"] = body.files
    if body.dirs is not None:
        rules["dirs"] = body.dirs
    if body.exts is not None:
        rules["exts"] = body.exts
    if rules:
        scanner.set_ignore_rules(rules)
    return scanner.get_ignore_rules()


@app.post("/api/monitor-dirs")
def update_monitor(body: dict):
    dirs = [d for d in body.get("directories", []) if d and os.path.isdir(d)]
    scanner.set_monitor_dirs(dirs)
    return scanner.get_monitor_dirs()


@app.post("/api/monitor-scan")
def monitor_scan():
    """立即触发一次监控目录扫描（无需等 60s 轮询），返回新发现数。"""
    try:
        n = watcher.scan_once()
        return {"added": n, "pending": db.pending_notification_count()}
    except Exception as e:
        raise HTTPException(500, f"扫描失败: {e}")


# ---------- 清空 / 维护 ----------

@app.post("/api/clear")
def clear_knowledge():
    """一键清空本地知识库数据（PRD 6.1 隐私销毁）。"""
    vector_store.delete_all()
    conn = db.get_conn()
    with db._lock:
        conn.execute("DELETE FROM documents")
        conn.execute("DELETE FROM behavior")
        conn.execute("DELETE FROM chunks")
        conn.execute("DELETE FROM tasks")
        conn.commit()
    return {"ok": True}


# ---------- 静态前端 ----------

@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
