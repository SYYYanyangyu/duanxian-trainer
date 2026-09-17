# -*- coding: utf-8 -*-
"""Serve the trainer + live screening API."""
from __future__ import annotations

import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import fetch_today
import store

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "web" / "dist"
PORT = 8765
CACHE: dict | None = None
_refresh_lock = threading.Lock()


def attach_paper(data: dict | None) -> dict:
    store.init()
    store.import_legacy_journal()
    data = dict(data or {})
    date = str(data.get("date") or "")
    if date:
        data["paper"] = store.paper_payload(date)
        data["ai"] = store.get_ai_desk(date)
    return fetch_today.relabel_paper(data)


def json_bytes(data) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def send_json(handler: SimpleHTTPRequestHandler, data, status: int = 200) -> None:
    body = json_bytes(data)
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_disk() -> dict | None:
    disk = ROOT / "today.json"
    if not disk.exists():
        return None
    return json.loads(disk.read_text(encoding="utf-8"))


def _load_cache_unlocked(refresh: bool = False) -> dict:
    global CACHE
    disk = ROOT / "today.json"
    if CACHE is None:
        CACHE = read_disk()
    if not refresh and CACHE:
        return CACHE
    prev = CACHE or read_disk()
    try:
        fresh = fetch_today.fetch_today(prev=prev)
        if not (fresh.get("limit_up") or []):
            raise RuntimeError("刷新结果没有涨停池")
        CACHE = fetch_today.relabel_paper(fresh)
        CACHE.pop("fetch_error", None)
        store.atomic_write_json(disk, CACHE)
    except Exception as exc:
        if prev:
            CACHE = dict(prev)
            CACHE["fetch_error"] = str(exc)
        elif CACHE is None:
            raise
        else:
            CACHE = dict(CACHE)
            CACHE["fetch_error"] = str(exc)
    return CACHE


def load_cache(refresh: bool = False) -> dict:
    if refresh:
        with _refresh_lock:
            return _load_cache_unlocked(True)
    return _load_cache_unlocked(False)


def run_ai_pick() -> dict:
    global CACHE
    with _refresh_lock:
        base = _load_cache_unlocked(False) or {}
        yest = base.get("yesterday") or {}
        if not (base.get("limit_up") or yest.get("preopen") or base.get("morning_watch")):
            raise RuntimeError("没有可用盘面，先刷新数据")
        data = fetch_today.rerun_ai_pick(dict(base))
        CACHE = data
        store.atomic_write_json(ROOT / "today.json", CACHE)
        return attach_paper(CACHE)


def send_bytes(handler: SimpleHTTPRequestHandler, body: bytes, content_type: str, status: int = 200) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST if DIST.exists() else ROOT), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/today.json":
            disk = ROOT / "today.json"
            if disk.exists():
                send_bytes(self, disk.read_bytes(), "application/json; charset=utf-8")
                return
        if parsed.path == "/api/today":
            qs = parse_qs(parsed.query)
            refresh = qs.get("refresh", ["0"])[0] == "1"
            try:
                data = attach_paper(load_cache(refresh=refresh))
                send_json(self, data)
            except Exception as exc:
                send_json(self, {"error": str(exc)}, 502)
            return
        if parsed.path == "/api/ai":
            try:
                send_json(self, run_ai_pick())
            except Exception as exc:
                send_json(self, {"error": str(exc)}, 502)
            return
        if parsed.path == "/api/history":
            try:
                store.init()
                store.import_legacy_journal()
                send_json(self, {
                    "scoreboard": store.scoreboard(),
                    "days": store.history_rows(30),
                    "note": store.PAPER_NOTE,
                })
            except Exception as exc:
                send_json(self, {"error": str(exc)}, 502)
            return
        if DIST.exists():
            rel = parsed.path.lstrip("/") or "index.html"
            candidate = (DIST / rel).resolve()
            try:
                candidate.relative_to(DIST.resolve())
            except ValueError:
                send_json(self, {"error": "bad path"}, 400)
                return
            if not candidate.is_file():
                self.path = "/index.html"
        super().do_GET()


if __name__ == "__main__":
    store.init()
    store.import_legacy_journal()
    if (ROOT / "today.json").exists():
        CACHE = fetch_today.relabel_paper(json.loads((ROOT / "today.json").read_text(encoding="utf-8")))
        try:
            store.save_market_from_payload(CACHE)
        except Exception:
            pass
        print("已载入 today.json，打开页面后可点「刷新实盘」")
    print(f"打开 http://127.0.0.1:{PORT}/  （今日选股需要这个服务才能刷新实盘）")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
