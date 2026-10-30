"""Run Hypercorn off the GUI thread; keep pywebview on the main thread."""

import asyncio
import os
import socket
import threading
import time
import urllib.request

from hypercorn.asyncio import serve
from hypercorn.config import Config
from platformdirs import user_data_path

from resolvent.web import create_app


def serve_browser(port: int = 8765, *, timeout: float = 15, open_browser: bool = False):
    config = Config()
    config.bind = [f"127.0.0.1:{port}"]
    config.accesslog = None
    config.graceful_timeout = 2
    url = f"http://127.0.0.1:{port}"
    print(f"Resolvent is running at {url}", flush=True)
    if open_browser:
        import webbrowser

        threading.Timer(0.8, webbrowser.open, args=(url,)).start()
    asyncio.run(serve(create_app(timeout=timeout), config))


def launch(*, gui: str | None = None, debug: bool = False, timeout: float = 15):
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError("Desktop support is not installed. Run: uv sync --extra desktop") from exc
    # JSON exports use a browser Blob download and need the native save dialog.
    webview.settings["ALLOW_DOWNLOADS"] = True
    # The socket remains reserved until Hypercorn takes ownership; port=0 avoids
    # collisions and does not briefly expose an unbound port to another process.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(100)
    port = sock.getsockname()[1]
    stopped = threading.Event()
    errors = []

    async def shutdown():
        while not stopped.is_set():
            await asyncio.sleep(0.1)

    def run_server():
        async def run():
            config = Config()
            if os.name == "nt":
                # Windows has no socket.fromfd; bind the allocated loopback port.
                sock.close()
                config.bind = [f"127.0.0.1:{port}"]
            else:
                # Hypercorn owns and closes this descriptor. Detach it so the
                # outer socket object cannot close a descriptor it no longer owns.
                config.bind = [f"fd://{sock.detach()}"]
            config.accesslog = None
            config.graceful_timeout = 2
            await serve(create_app(timeout=timeout), config, shutdown_trigger=shutdown)

        try:
            asyncio.run(run())
        except Exception as exc:
            errors.append(exc)
            stopped.set()

    thread = threading.Thread(target=run_server, name="resolvent-server", daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            if errors:
                raise RuntimeError(f"The local server could not start: {errors[0]}")
            try:
                with urllib.request.urlopen(url + "/api/health", timeout=0.2):
                    break
            except OSError:
                time.sleep(0.05)
        else:
            raise RuntimeError("The local server did not become ready.")
        try:
            webview.create_window(
                "Resolvent · Mathematics workbench",
                url,
                width=1440,
                height=960,
                min_size=(820, 650),
                background_color="#f7f8fa",
            )
            webview.start(
                gui=gui,
                debug=debug,
                private_mode=False,
                storage_path=str(user_data_path("resolvent", appauthor=False) / "webview"),
            )
        except Exception as exc:
            raise RuntimeError(
                f"Could not open the desktop renderer: {exc}. On Linux try "
                "'uv sync --extra qt' and 'uv run resolvent gui --gui qt', "
                "or use 'uv run resolvent serve --open'."
            ) from exc
    finally:
        stopped.set()
        thread.join(timeout=4)
        sock.close()
