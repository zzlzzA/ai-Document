# -*- coding: utf-8 -*-
"""入库流水线：解析 → 切片 → Embedding → 向量入库 → AI 分类 → 元数据落库。
后台线程异步执行，任务进度写入 db.tasks，前端轮询。
"""
import os
import shutil
import threading
import time
import uuid

from . import chunker, classifier, config, db, embedder, parser, scanner, vector_store


def _default_download_dir():
    try:
        import ctypes
        from ctypes import wintypes
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf)  # CSIDL_PERSONAL? 5=我的文档
        # Downloads 用已知文件夹 API 更准，但此处兜底取用户目录
        home = os.path.expanduser("~")
        dl = os.path.join(home, "Downloads")
        return dl if os.path.isdir(dl) else home
    except Exception:
        return os.path.expanduser("~")


def start_ingest(files: list, source: str = "manual") -> str:
    """files: [{path}]。返回 task_id。source: manual | 自动-目录名"""
    task_id = uuid.uuid4().hex[:12]
    db.task_begin(task_id, "ingest", total=len(files))
    t = threading.Thread(target=_run_ingest, args=(task_id, files, source), daemon=True)
    t.start()
    return task_id


def _run_ingest(task_id: str, files: list, source: str):
    done, failed = 0, 0
    results = []
    for item in files:
        path = item.get("path", "")
        try:
            r = _ingest_one(path, source)
            results.append(r)
            if r.get("ok"):
                done += 1
            else:
                failed += 1
        except Exception as e:  # 单文件失败不中断批量
            failed += 1
            results.append({"path": path, "ok": False, "error": f"入库异常: {e}"})
        db.task_update(task_id, done=done, failed=failed,
                       result=results[-50:])
    db.task_update(task_id, status="done", done=done, failed=failed, result=results)


def _ingest_one(path: str, source: str) -> dict:
    base = {"path": path, "name": os.path.basename(path), "ok": False}
    if not os.path.exists(path):
        base["error"] = "文件不存在"
        return base
    try:
        md5 = scanner.compute_md5(path)
    except OSError as e:
        base["error"] = f"读取失败: {e}"
        return base
    if db.doc_exists_by_md5(md5):
        # 清理上传产生的重复副本（避免 uploads 积累垃圾文件）
        if os.path.abspath(path).startswith(config.UPLOAD_DIR) and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
        base["error"] = "重复文件（MD5 一致），已跳过"
        base["duplicate"] = True
        return base

    st = os.stat(path)
    ext = os.path.splitext(path)[1].lower()

    # 手动上传：复制到本地 uploads 目录，保证原件随知识库存放
    store_path = path
    if source == "manual" and not os.path.abspath(path).startswith(config.UPLOAD_DIR):
        try:
            dst = os.path.join(config.UPLOAD_DIR, f"{uuid.uuid4().hex[:8]}_{os.path.basename(path)}")
            shutil.copy2(path, dst)
            store_path = dst
        except OSError as e:
            base["error"] = f"复制原件失败: {e}"
            return base

    # 解析
    pr = parser.parse_file(store_path)
    if not pr.ok or not pr.text.strip():
        # 解析失败也登记，便于用户看到异常文件（PRD 6.4 容错）
        doc = {
            "path": store_path, "md5": md5, "name": os.path.basename(store_path),
            "ext": ext, "size": st.st_size, "category": "其他", "category_manual": 0,
            "tags": "[]", "summary": "", "text_len": 0, "chunk_count": 0,
            "parse_ok": 0, "parse_msg": pr.msg, "source": source,
            "created_at": time.time(), "modified_at": st.st_mtime,
        }
        doc_id = db.add_document(doc)
        base.update(ok=False, doc_id=doc_id, error=pr.msg or "解析失败")
        return base

    # 切片
    chunks = chunker.chunk_text(pr.text)
    if not chunks:
        doc = {
            "path": store_path, "md5": md5, "name": os.path.basename(store_path),
            "ext": ext, "size": st.st_size, "category": "其他", "category_manual": 0,
            "tags": "[]", "summary": parser.make_summary(pr.text), "text_len": len(pr.text),
            "chunk_count": 0, "parse_ok": 1, "parse_msg": "文本过短", "source": source,
            "created_at": time.time(), "modified_at": st.st_mtime,
        }
        doc_id = db.add_document(doc)
        base.update(ok=True, doc_id=doc_id, chunks=0)
        return base

    # 先创建文档记录（拿到 doc_id）
    doc_id = db.add_document({
        "path": store_path, "md5": md5, "name": os.path.basename(store_path),
        "ext": ext, "size": st.st_size, "category": "其他", "category_manual": 0,
        "tags": "[]", "summary": parser.make_summary(pr.text), "text_len": len(pr.text),
        "chunk_count": len(chunks), "parse_ok": 1, "parse_msg": "", "source": source,
        "created_at": time.time(), "modified_at": st.st_mtime,
    })

    # 切片文本落 SQLite（BM25 语料，不依赖向量模型）
    db.add_chunks(doc_id, chunks)

    # 向量化（模型不可用时降级：跳过向量，仅 BM25 检索）
    vectors = None
    vec_ok = False
    try:
        vectors = embedder.embed_texts([c["text"] for c in chunks])
        vec_ok = True
    except embedder.EmbeddingUnavailable:
        vectors = None

    # AI 分类
    category, conf, reason = classifier.classify(pr.text, os.path.basename(store_path))

    db.update_document(doc_id, category=category, summary=parser.make_summary(pr.text),
                       text_len=len(pr.text), chunk_count=len(chunks), parse_ok=1)
    if vectors:
        try:
            vector_store.add_chunks(doc_id, os.path.basename(store_path), category, chunks, vectors)
        except Exception as e:
            db.update_document(doc_id, parse_msg=f"向量入库失败: {e}")
            vectors = None

    base.update(ok=True, doc_id=doc_id, chunks=len(chunks),
                category=category, conf=round(conf, 3), reason=reason,
                vector_ok=vec_ok)
    return base
