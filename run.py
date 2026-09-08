# -*- coding: utf-8 -*-
"""启动入口：
- 开发模式：python run.py  →  浏览器访问 http://127.0.0.1:8000
- 桌面版（PyInstaller frozen）：双击 exe → 后台启动服务 + 弹出原生桌面窗口（pywebview），
  数据/模型/日志保存在 exe 同目录 data/ 下，全程本地。
"""
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

# Windows 下统一 UTF-8 输出，避免 GBK 乱码
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_FROZEN = bool(getattr(sys, "frozen", False))

PORT = int(os.environ.get("AIWJ_PORT", "8000"))
HOST = os.environ.get("AIWJ_HOST", "127.0.0.1")


def _pick_port(preferred: int) -> int:
    """端口被占用时自动顺延，避免二次启动冲突。"""
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, port))
                return port
            except OSError:
                continue
    return preferred


def _msgbox(title: str, text: str):
    """桌面版（无控制台）弹窗提示错误。"""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)
    except Exception:
        pass


def _check_single_instance() -> bool:
    """Windows 命名互斥量：防止用户多次双击导致多进程抢占端口。"""
    if not _FROZEN:
        return True
    try:
        import ctypes
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\AIWenJianDesktopMutex")
        if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            _msgbox("已在运行", "AI 智能文档知识库已经在运行中，请勿重复启动。")
            return False
        return True
    except Exception:
        return True


def _setup_file_logging():
    """桌面版把运行日志写入 exe 同目录 data/logs/desktop.log，
    并将 stdout/stderr 重定向到该文件，保证 uvicorn 与所有 print 落盘。"""
    try:
        from backend import config
        os.makedirs(config.LOG_DIR, exist_ok=True)
        log_path = os.path.join(config.LOG_DIR, "desktop.log")
        stream = open(log_path, "a", encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = stream
        if sys.stderr is None:
            sys.stderr = stream
        import logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            handlers=[logging.FileHandler(log_path, encoding="utf-8")],
            force=True,
        )
    except Exception:
        pass


def _wait_ready(url: str, timeout: int = 30):
    """轮询等待本地服务就绪。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def _open_browser(url: str):
    time.sleep(1.2)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def _serve(host: str, port: int):
    """后台线程运行 uvicorn。"""
    import traceback
    try:
        import uvicorn
        uvicorn.run("backend.api:app", host=host, port=port, log_level="info", log_config=None)
    except Exception:
        if _FROZEN:
            try:
                traceback.print_exc()
            except Exception:
                pass
            _msgbox("启动失败", "AI 智能文档知识库启动失败，请查看 exe 同目录 data/logs/desktop.log")
        else:
            raise


def main():
    if _FROZEN:
        _setup_file_logging()
        if not _check_single_instance():
            os._exit(0)

    port = _pick_port(PORT) if _FROZEN else PORT
    url = f"http://{HOST}:{port}"

    if not _FROZEN:
        print("=" * 56)
        print("  Windows AI 智能文档知识库客户端")
        print(f"  服务地址: {url}")
        print("  数据目录: 项目 data/ 下（全本地存储）")
        print("=" * 56)

    # 后台线程启动服务
    serve_thread = threading.Thread(target=_serve, args=(HOST, port), daemon=True)
    serve_thread.start()

    if _FROZEN:
        # 桌面版：等服务就绪后弹出原生窗口
        if not _wait_ready(url):
            _msgbox("启动超时", "服务启动超时，请查看 data/logs/desktop.log")
            os._exit(1)
        try:
            import webview
            window = webview.create_window(
                "AI 智能文档知识库",
                url,
                width=1280,
                height=820,
                min_size=(960, 600),
                text_select=True,
            )
            webview.start(debug=False)
        except Exception as e:
            try:
                import traceback
                traceback.print_exc()
            except Exception:
                pass
            _msgbox("窗口启动失败", f"桌面窗口启动失败：{e}\n将改用浏览器模式。")
            # 降级：打开浏览器
            _open_browser(url)
            serve_thread.join()
        finally:
            os._exit(0)
    else:
        # 开发模式：自动打开浏览器
        if os.environ.get("AIWJ_NO_BROWSER") != "1":
            threading.Thread(target=_open_browser, args=(url,), daemon=True).start()
        serve_thread.join()


if __name__ == "__main__":
    main()
