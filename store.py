# -*- coding: utf-8 -*-
"""Local desk ledger. Market snapshots, paper decisions and AI runs stay separate."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "data" / "desk.db"
ACTOR_NAMES = (("rules", "纪律派"), ("chase", "补涨派"), ("cash", "空仓派"), ("ai", "大模型"))
STARTING_CASH = 100_000.0
BET_SIZE = 20_000.0
PAPER_NOTE = "每人10万纸上资金，成交按每笔2万计，次日收盘涨幅结算；开盘涨停记买不进。不是实盘。台账在 data/desk.db。"

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None
_db_path: Path | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  session_id TEXT,
  is_close INTEGER NOT NULL DEFAULT 0,
  phase TEXT,
  zt_count INTEGER,
  tape TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_date ON snapshots(date, id);

CREATE TABLE IF NOT EXISTS days (
  date TEXT PRIMARY KEY,
  phase TEXT,
  settled INTEGER NOT NULL DEFAULT 0,
  actors TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL,
  model TEXT,
  status TEXT NOT NULL,
  context TEXT,
  result TEXT,
  error TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ai_runs_date ON ai_runs(date, id);

CREATE TABLE IF NOT EXISTS meta (
  k TEXT PRIMARY KEY,
  v TEXT NOT NULL
);
"""


def db_path() -> Path:
    raw = (os.environ.get("DESK_DB") or "").strip()
    return Path(raw) if raw else DEFAULT_DB


def now_text() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def loads(text, default=None):
    if not text:
        return default
    try:
        return json.loads(text)
    except Exception:
        return default


def atomic_write_json(path: Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def connect() -> sqlite3.Connection:
    global _conn, _db_path
    path = db_path()
    if _conn is not None and _db_path == path:
        return _conn
    if _conn is not None:
        _conn.close()
        _conn = None
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(days)").fetchall()}
    if "ai_desk" not in cols:
        conn.execute("ALTER TABLE days ADD COLUMN ai_desk TEXT")
    conn.commit()
    _conn = conn
    _db_path = path
    return conn


def init() -> None:
    with _lock:
        connect()


def reset_for_tests() -> None:
    global _conn, _db_path
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = None
        _db_path = None


def _row_day(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return {
        "date": row["date"],
        "phase": row["phase"],
        "settled": bool(row["settled"]),
        "actors": loads(row["actors"], []) or [],
        "ai_desk": loads(row["ai_desk"], None) if "ai_desk" in row.keys() else None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_day(date: str) -> dict | None:
    with _lock:
        row = connect().execute("SELECT * FROM days WHERE date=?", (date,)).fetchone()
        return _row_day(row)


def all_days() -> list[dict]:
    with _lock:
        rows = connect().execute("SELECT * FROM days ORDER BY date DESC").fetchall()
        return [_row_day(r) for r in rows]


def put_new_day(date: str, phase: str, actors: list) -> bool:
    stamp = now_text()
    with _lock:
        conn = connect()
        cur = conn.execute(
            "INSERT OR IGNORE INTO days(date, phase, settled, actors, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (date, phase, 0, dumps(actors), stamp, stamp),
        )
        conn.commit()
        return cur.rowcount == 1


def replace_ai_actor(date: str, actor: dict) -> bool:
    with _lock:
        conn = connect()
        row = conn.execute("SELECT * FROM days WHERE date=?", (date,)).fetchone()
        if row is None or row["settled"]:
            return False
        actors = [a for a in (loads(row["actors"], []) or []) if a.get("id") != "ai"]
        actors.append(actor)
        conn.execute(
            "UPDATE days SET actors=?, updated_at=? WHERE date=? AND settled=0",
            (dumps(actors), now_text(), date),
        )
        conn.commit()
        return True


def touch_actors(date: str, actors: list) -> bool:
    with _lock:
        conn = connect()
        cur = conn.execute(
            "UPDATE days SET actors=?, updated_at=? WHERE date=? AND settled=0",
            (dumps(actors), now_text(), date),
        )
        conn.commit()
        return cur.rowcount == 1


def set_settled(date: str, actors: list) -> bool:
    with _lock:
        conn = connect()
        row = conn.execute("SELECT settled FROM days WHERE date=?", (date,)).fetchone()
        if row is None or row["settled"]:
            return False
        conn.execute(
            "UPDATE days SET actors=?, settled=1, updated_at=? WHERE date=? AND settled=0",
            (dumps(actors), now_text(), date),
        )
        conn.commit()
        return True


def desk_from_actor(actor: dict | None) -> dict | None:
    if not actor:
        return None
    return {
        "model": actor.get("name") or "大模型",
        "stance": actor.get("stance") or "",
        "think": actor.get("think") or "",
        "plan": actor.get("plan") or "",
        "watch": [
            {
                "code": b.get("code"),
                "name": b.get("name"),
                "side": b.get("side") or "盯不打",
                "why": b.get("why") or "",
            }
            for b in (actor.get("bets") or [])
        ],
        "avoid": actor.get("avoid") or [],
        "note": actor.get("note") or "",
    }


def get_ai_desk(date: str) -> dict | None:
    day = get_day(date)
    if not day:
        return None
    desk = day.get("ai_desk")
    if isinstance(desk, dict) and (desk.get("stance") or desk.get("watch") or desk.get("think")):
        return desk
    actor = next((a for a in (day.get("actors") or []) if a.get("id") == "ai"), None)
    return desk_from_actor(actor)


def set_ai_desk(date: str, desk: dict) -> bool:
    with _lock:
        conn = connect()
        row = conn.execute("SELECT settled FROM days WHERE date=?", (date,)).fetchone()
        if row is None or row["settled"]:
            return False
        conn.execute(
            "UPDATE days SET ai_desk=?, updated_at=? WHERE date=? AND settled=0",
            (dumps(desk), now_text(), date),
        )
        conn.commit()
        return True


def save_snapshot(date: str, tape: dict, *, fetched_at: str, session_id: str = "", is_close: bool = False, phase: str = "", zt_count: int = 0) -> int:
    with _lock:
        conn = connect()
        cur = conn.execute(
            "INSERT INTO snapshots(date, fetched_at, session_id, is_close, phase, zt_count, tape) VALUES (?,?,?,?,?,?,?)",
            (date, fetched_at, session_id or "", 1 if is_close else 0, phase, int(zt_count or 0), dumps(tape)),
        )
        conn.commit()
        return int(cur.lastrowid)


def latest_snapshot(date: str) -> dict | None:
    with _lock:
        row = connect().execute(
            "SELECT * FROM snapshots WHERE date=? ORDER BY id DESC LIMIT 1",
            (date,),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "date": row["date"],
            "fetched_at": row["fetched_at"],
            "session_id": row["session_id"],
            "is_close": bool(row["is_close"]),
            "phase": row["phase"],
            "zt_count": row["zt_count"],
            "tape": loads(row["tape"], {}) or {},
        }


def log_ai_run(date: str, *, model: str, status: str, context=None, result=None, error: str = "") -> None:
    with _lock:
        conn = connect()
        conn.execute(
            "INSERT INTO ai_runs(date, model, status, context, result, error, created_at) VALUES (?,?,?,?,?,?,?)",
            (date, model, status, dumps(context) if context is not None else "", dumps(result) if result is not None else "", error or "", now_text()),
        )
        conn.commit()


def day_pnl_yuan(actor: dict | None) -> float:
    if not actor:
        return 0.0
    if actor.get("pnl_yuan") is not None:
        try:
            return float(actor.get("pnl_yuan") or 0)
        except (TypeError, ValueError):
            return 0.0
    total = 0.0
    filled = 0
    for b in actor.get("bets") or []:
        if b.get("pnl_yuan") is not None:
            total += float(b.get("pnl_yuan") or 0)
            filled += 1
        elif (b.get("fill") or "") == "按收盘涨幅" and b.get("pnl") is not None:
            total += BET_SIZE * float(b.get("pnl") or 0) / 100.0
            filled += 1
    if filled:
        return round(total, 2)
    try:
        return round(STARTING_CASH * float(actor.get("pnl") or 0) / 100.0, 2)
    except (TypeError, ValueError):
        return 0.0


def running_cash(days: list[dict] | None = None) -> dict[str, dict[str, float]]:
    """Equity after each day, oldest date first. Unsettled days keep previous cash."""
    days = list(days if days is not None else all_days())
    days.sort(key=lambda d: str(d.get("date") or ""))
    cash = {actor_id: STARTING_CASH for actor_id, _ in ACTOR_NAMES}
    out: dict[str, dict[str, float]] = {}
    for day in days:
        date = str(day.get("date") or "")
        if day.get("settled"):
            for actor_id, _ in ACTOR_NAMES:
                actor = next((a for a in (day.get("actors") or []) if a.get("id") == actor_id), None)
                if actor:
                    cash[actor_id] = round(cash[actor_id] + day_pnl_yuan(actor), 2)
        if date:
            out[date] = dict(cash)
    return out


def scoreboard(days: list[dict] | None = None) -> list[dict]:
    days = days if days is not None else all_days()
    cash_map = running_cash(days)
    latest_date = max(cash_map) if cash_map else ""
    latest = cash_map.get(latest_date) or {i: STARTING_CASH for i, _ in ACTOR_NAMES}
    board = []
    for actor_id, actor_name in ACTOR_NAMES:
        wins = losses = 0
        pnl_yuan = 0.0
        n_days = 0
        for day in days:
            if not day.get("settled"):
                continue
            actor = next((a for a in day.get("actors") or [] if a.get("id") == actor_id), None)
            if not actor:
                continue
            n_days += 1
            wins += int(actor.get("wins") or 0)
            losses += int(actor.get("losses") or 0)
            pnl_yuan += day_pnl_yuan(actor)
        done = wins + losses
        cash = float(latest.get(actor_id, STARTING_CASH))
        board.append({
            "id": actor_id,
            "name": actor_name,
            "days": n_days,
            "wins": wins,
            "losses": losses,
            "pnl_yuan": round(pnl_yuan, 2),
            "pnl": round(pnl_yuan / STARTING_CASH * 100.0, 2) if STARTING_CASH else 0,
            "cash": round(cash, 2),
            "starting": STARTING_CASH,
            "rate": round(wins / done, 3) if done else None,
        })
    return board


def recent_review(limit: int = 5) -> list[dict]:
    out = []
    for day in all_days():
        if not day.get("settled"):
            continue
        actors = []
        for actor in day.get("actors") or []:
            bets = []
            for b in actor.get("bets") or []:
                bets.append({
                    "code": b.get("code"),
                    "name": b.get("name"),
                    "side": b.get("side"),
                    "fill": b.get("fill"),
                    "pnl": b.get("pnl"),
                    "today_pct": b.get("pct"),
                    "open_pct": b.get("open_pct"),
                })
            actors.append({
                "id": actor.get("id"),
                "name": actor.get("name"),
                "stance": actor.get("stance"),
                "pnl": actor.get("pnl"),
                "pnl_yuan": day_pnl_yuan(actor),
                "wins": actor.get("wins"),
                "losses": actor.get("losses"),
                "bets": bets,
            })
        out.append({"date": day["date"], "phase": day.get("phase"), "actors": actors})
        if len(out) >= limit:
            break
    return out


def history_rows(limit: int = 12) -> list[dict]:
    days = all_days()
    cash_map = running_cash(days)
    rows = []
    for day in days[:limit]:
        snap = latest_snapshot(day["date"])
        date_cash = cash_map.get(day["date"]) or {i: STARTING_CASH for i, _ in ACTOR_NAMES}
        actors = []
        for actor in day.get("actors") or []:
            aid = str(actor.get("id") or "")
            actors.append({
                "id": actor.get("id"),
                "name": actor.get("name"),
                "stance": actor.get("stance"),
                "pnl": actor.get("pnl"),
                "pnl_yuan": actor.get("pnl_yuan") if actor.get("pnl_yuan") is not None else day_pnl_yuan(actor) if day.get("settled") else 0,
                "cash": date_cash.get(aid, STARTING_CASH),
                "rate": actor.get("rate"),
                "settled": bool(actor.get("settled") or day.get("settled")),
                "bets": actor.get("bets") or [],
            })
        rows.append({
            "date": day["date"],
            "phase": day.get("phase"),
            "settled": bool(day.get("settled")),
            "zt_count": (snap or {}).get("zt_count"),
            "fetched_at": (snap or {}).get("fetched_at"),
            "actors": actors,
        })
    return rows


def paper_payload(date: str) -> dict:
    days = all_days()
    today = next((d for d in days if d.get("date") == date), None)
    board = scoreboard(days)
    date_cash = running_cash(days).get(date) or {i: STARTING_CASH for i, _ in ACTOR_NAMES}
    if today:
        actors = []
        for actor in today.get("actors") or []:
            a = dict(actor)
            a["cash"] = round(float(date_cash.get(str(a.get("id") or ""), STARTING_CASH)), 2)
            a["starting"] = STARTING_CASH
            actors.append(a)
        today = dict(today)
        today["actors"] = actors
    return {
        "today": today,
        "scoreboard": board,
        "history": history_rows(12),
        "ai": get_ai_desk(date) if date else None,
        "note": PAPER_NOTE,
        "starting": STARTING_CASH,
        "bet_size": BET_SIZE,
    }


def export_journal(path: Path | None = None) -> dict:
    path = Path(path) if path else ROOT / "journal.json"
    days = list(reversed(all_days()))[-30:]
    book = {"days": days, "scoreboard": scoreboard(all_days()[:30])}
    atomic_write_json(path, book)
    return book


def import_legacy_journal(path: Path | None = None) -> int:
    path = Path(path) if path else ROOT / "journal.json"
    with _lock:
        conn = connect()
        n = conn.execute("SELECT COUNT(*) AS n FROM days").fetchone()["n"]
        if n:
            return 0
        if not path.exists():
            return 0
        try:
            book = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return 0
        imported = 0
        stamp = now_text()
        for day in book.get("days") or []:
            date = str(day.get("date") or "")
            if not date:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO days(date, phase, settled, actors, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                (date, day.get("phase") or "", 1 if day.get("settled") else 0, dumps(day.get("actors") or []), stamp, stamp),
            )
            imported += 1
        conn.commit()
        return imported


def slim_stock(row: dict) -> dict:
    keys = (
        "code", "name", "boards", "pct", "theme", "industry", "role", "verdict",
        "turnover", "open_times", "first_seal", "vane", "clustered", "theme_count",
        "action", "y_boards", "open_pct", "today_pct", "result",
    )
    return {k: row.get(k) for k in keys if row.get(k) is not None}


def compact_tape(data: dict) -> dict:
    yest = data.get("yesterday") or {}
    picks = data.get("picks") or {}
    return {
        "date": data.get("date"),
        "updated": data.get("updated"),
        "phase": data.get("phase"),
        "phase_name": data.get("phase_name"),
        "phase_why": data.get("phase_why"),
        "max_board": data.get("max_board"),
        "zt_count": data.get("zt_count"),
        "zb_count": data.get("zb_count"),
        "themes": data.get("themes") or [],
        "picks": {
            "stance": picks.get("stance"),
            "primary": [slim_stock(x) for x in (picks.get("primary") or [])],
            "hide": [slim_stock(x) for x in (picks.get("hide") or [])][:12],
        },
        "limit_up": [slim_stock(x) for x in (data.get("limit_up") or [])],
        "morning_watch": [slim_stock(x) for x in (data.get("morning_watch") or [])],
        "yesterday": {
            "date": yest.get("date"),
            "count": yest.get("count"),
            "promoted_n": yest.get("promoted_n"),
            "failed_n": yest.get("failed_n"),
            "rate": yest.get("rate"),
            "preopen": [slim_stock(x) for x in (yest.get("preopen") or [])],
        },
        "ladder": data.get("ladder") or [],
    }


def save_market_from_payload(data: dict) -> int:
    sess = data.get("session") or {}
    return save_snapshot(
        str(data.get("date") or ""),
        compact_tape(data),
        fetched_at=str(data.get("updated") or now_text()),
        session_id=str(sess.get("id") or ""),
        is_close=str(sess.get("id") or "") in ("closed", "weekend"),
        phase=str(data.get("phase") or ""),
        zt_count=int(data.get("zt_count") or 0),
    )
