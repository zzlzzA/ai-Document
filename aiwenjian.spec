# -*- mode: python ; coding: utf-8 -*-
"""AI 智能文档知识库 - PyInstaller 打包配置
产出：dist/AI文档知识库/AI文档知识库.exe（one-dir，双击即用）
注意：本地大模型 GGUF(约2.1GB) 不打包，首次问答时自动下载到 exe 同目录 data/models/
"""
from PyInstaller.utils.hooks import collect_all

# 前端静态资源（必须随包分发，运行时从 _MEIPASS/frontend 读取）
datas = [("frontend", "frontend")]

binaries = []
hiddenimports = []

# 动态导入 / 带数据文件 / 带 DLL 的第三方包：整包收集
for pkg in (
    "chromadb",
    "fastembed",
    "onnxruntime",
    "llama_cpp",
    "jieba",
    "rank_bm25",
    "pdfplumber",
    "docx",
    "openpyxl",
    "pptx",
    "requests",
    "fastapi",
    "uvicorn",
    "pydantic",
    "webview",
    "pythonnet",
    "clr_loader",
):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as exc:  # noqa: BLE001
        print(f"[spec] collect_all({pkg}) 失败: {exc}")

# uvicorn 动态加载的协议/循环实现
hiddenimports += [
    "backend.api",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.lifespan.on",
    "webview.platforms.winforms",
    "webview.platforms.edgechromium",
    "clr_loader",
    "pythonnet",
]

a = Analysis(
    ["run.py"],
    pathex=["E:\\个人\\项目\\aiwenjian"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["paddle", "paddleocr", "fitz", "pymupdf", "tkinter", "matplotlib"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AI文档知识库",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # 桌面应用：无控制台黑窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="AI文档知识库",
)
