# -*- coding: utf-8 -*-
"""Integrity checks for the desk ledger. Run: python test_store.py"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

os.environ["DESK_DB"] = str(Path(tempfile.mkdtemp()) / "desk.db")

import store  # noqa: E402
from fetch_today import can_settle, settle_actor  # noqa: E402


def check(cond, msg):
    if not cond:
        raise SystemExit("FAIL: " + msg)
    print("ok:", msg)


def main() -> None:
    store.reset_for_tests()
    store.init()

    check(store.get_day("20260917") is None, "empty db has no day")
    actors = [
        {"id": "rules", "name": "纪律派", "stance": "盯", "bets": [{"code": "000001", "name": "平安", "side": "盯"}]},
        {"id": "cash", "name": "空仓派", "stance": "空", "bets": []},
        {"id": "ai", "name": "deepseek-v4-pro", "stance": "空仓", "bets": [], "think": "先空"},
    ]
    check(store.put_new_day("20260917", "diverge", actors), "first write of a day succeeds")
    check(not store.put_new_day("20260917", "climax", actors), "second write of same day is ignored")
    day = store.get_day("20260917")
    check(day["phase"] == "diverge", "phase stays the first write")

    store.save_snapshot("20260917", {"zt_count": 40}, fetched_at="2026-09-17 15:01:00", session_id="closed", is_close=True, phase="diverge", zt_count=40)
    store.save_snapshot("20260917", {"zt_count": 41}, fetched_at="2026-09-17 15:40:00", session_id="closed", is_close=True, phase="diverge", zt_count=41)
    with store._lock:
        n = store.connect().execute("SELECT COUNT(*) AS n FROM snapshots WHERE date='20260917'").fetchone()["n"]
    check(n == 2, "snapshots append, never overwrite")
    check(store.latest_snapshot("20260917")["zt_count"] == 41, "latest snapshot is the last one")

    settled = [settle_actor(a, {"000001": {"today_pct": 2.5, "open_pct": 1.2}}) for a in day["actors"]]
    check(store.set_settled("20260917", settled), "first settle succeeds")
    check(not store.set_settled("20260917", settled), "second settle is refused")
    check(not store.replace_ai_actor("20260917", {"id": "ai", "think": "改口"}), "settled day cannot change AI")
    frozen = store.get_day("20260917")
    check(frozen["settled"] and frozen["actors"][2]["think"] == "先空", "settled AI think is frozen")

    yest = {"date": "20260917", "preopen": [{"code": "000001", "today_pct": 3.0, "open_pct": 1.0}]}
    check(can_settle(actors, yest, {"000001": {"today_pct": 3.0}}), "settle allowed when prices exist")
    check(not can_settle(
        [{"id": "chase", "bets": [{"code": "000002", "side": "打补涨"}]}],
        {"preopen": []},
        {},
    ), "do not settle aggressive bets without next-day prices")
    check(can_settle([{"id": "cash", "bets": []}], {"preopen": []}, {}), "empty-cash day can settle")

    store.log_ai_run("20260917", model="deepseek-v4-pro", status="ok", context={"phase": "diverge"}, result={"stance": "空仓"})
    review = store.recent_review(5)
    check(review and review[0]["date"] == "20260917", "settled day enters AI review")

    journal = Path(os.environ["DESK_DB"]).parent / "journal.json"
    store.export_journal(journal)
    book = json.loads(journal.read_text(encoding="utf-8"))
    check(book["days"][0]["date"] == "20260917" and book["days"][0]["settled"], "journal export keeps settled day")

    check(store.STARTING_CASH == 100000, "each role starts with 100000")
    check(store.BET_SIZE == 20000, "filled bet size is 20000")
    rules = next(a for a in settled if a["id"] == "rules")
    check(rules["pnl_yuan"] == 500, "盯 2.5% on 20000 is 500 yuan")
    cash_actor = next(a for a in settled if a["id"] == "cash")
    check(cash_actor["pnl_yuan"] == 0, "empty book stays 0 yuan")
    board = store.scoreboard()
    rules_row = next(r for r in board if r["id"] == "rules")
    check(rules_row["cash"] == 100500, "discipline equity is 100500 after +500")
    cash_row = next(r for r in board if r["id"] == "cash")
    check(cash_row["cash"] == 100000, "cash role still 100000")
    check(store.day_pnl_yuan({"pnl": 0.5}) == 500, "legacy percent pnl converts against 100000")

    day2 = [
        {"id": "rules", "name": "纪律派", "stance": "盯", "bets": [{"code": "000001", "name": "平安", "side": "盯"}]},
        {"id": "cash", "name": "空仓派", "stance": "空", "bets": []},
        {"id": "chase", "name": "补涨派", "stance": "打", "bets": []},
        {"id": "ai", "name": "deepseek-v4-pro", "stance": "空仓", "bets": []},
    ]
    check(store.put_new_day("20260918", "repair", day2), "second day writes")
    settled2 = [settle_actor(a, {"000001": {"today_pct": 1.0, "open_pct": 0.4}}) for a in day2]
    check(store.set_settled("20260918", settled2), "second day settles")
    rules2 = next(r for r in store.scoreboard() if r["id"] == "rules")
    check(rules2["cash"] == 100700, "two-day equity compounds 500+200")
    check(rules2["pnl_yuan"] == 700, "cumulative yuan is 700")

    print("ALL PASS")


if __name__ == "__main__":
    main()
