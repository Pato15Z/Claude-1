import os
import socket
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures" / "sites"


@pytest.fixture()
def con(tmp_path, monkeypatch):
    from leadpipe import config, db
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "SCREENSHOT_DIR", tmp_path / "shots")
    monkeypatch.setattr(config, "DEBUG_DIR", tmp_path / "debug")
    if not config.CHROMIUM_PATH and os.path.exists("/opt/pw-browsers/chromium-1194/chrome-linux/chrome"):
        monkeypatch.setattr(config, "CHROMIUM_PATH", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
    c = db.connect(tmp_path / "t.db")
    yield c
    c.close()


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@pytest.fixture(scope="session")
def site_server():
    """Serve tests/fixtures/sites em 127.0.0.1:<porta livre>."""
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = ThreadingHTTPServer(("127.0.0.1", port), partial(_Quiet, directory=str(FIX)))
    t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()
