# -*- coding: utf-8 -*-
"""Fetch public East Money tape and rank by 龙头短线框架."""
from __future__ import annotations

import json
import os
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import store

ROOT = Path(__file__).resolve().parent
UA = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://quote.eastmoney.com/",
}


def load_local_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value:
            os.environ[key] = value


load_local_env()


def current_model() -> str:
    load_local_env()
    use_deepseek = bool((os.environ.get("DEEPSEEK_API_KEY") or "").strip())
    return (os.environ.get("DEEPSEEK_MODEL") or "").strip() or ("deepseek-v4-pro" if use_deepseek else "gpt-4o-mini")


def relabel_ai_actor(actor: dict) -> dict:
    if not actor or actor.get("id") != "ai":
        return actor
    model = current_model()
    stance = actor.get("stance") or ""
    if stance in ("未接入", "调用失败"):
        actor["name"] = "大模型"
        return actor
    actor["name"] = model
    note = actor.get("note") or ""
    if (not note) or note.startswith("模型 ") or "纸上" in note or "reasoner" in note:
        actor["note"] = f"模型 {model}，纸上选股，不是下单。"
    return actor


def relabel_paper(data: dict) -> dict:
    paper = (data or {}).get("paper") or {}
    today = paper.get("today") or {}
    if today.get("settled"):
        if not data.get("ai"):
            data["ai"] = store.get_ai_desk(str(data.get("date") or today.get("date") or ""))
        return data
    for actor in today.get("actors") or []:
        relabel_ai_actor(actor)
    date = str(data.get("date") or today.get("date") or "")
    if date and not data.get("ai"):
        data["ai"] = store.get_ai_desk(date)
    ai = data.get("ai")
    if isinstance(ai, dict) and ai.get("stance") not in ("未接入", "调用失败", "待选股"):
        model = current_model()
        ai["model"] = model
        note = ai.get("note") or ""
        if (not note) or note.startswith("模型 ") or "纸上" in note:
            ai["note"] = f"模型 {model}，纸上选股，不是下单。"
    return data


def get_json(url: str, retries: int = 2) -> dict:
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=12) as resp:
                return json.loads(resp.read().decode("utf-8-sig"))
        except Exception as exc:
            last = exc
            if i < retries:
                continue
    raise last


def fmt_time(v) -> str:
    if v in (None, "", 0):
        return ""
    s = f"{int(v):06d}"
    return f"{s[0:2]}:{s[2:4]}:{s[4:6]}"


def yi(n) -> float:
    try:
        return round(float(n) / 1e8, 2)
    except (TypeError, ValueError):
        return 0.0


def seal_quality(open_times: int, turnover: float) -> str:
    if open_times == 0 and turnover < 8:
        return "一字/低换手封"
    if open_times == 0:
        return "换手板(未开板)"
    if open_times >= 1 and turnover >= 15:
        return "高换手回封"
    return f"开板{open_times}次回封"


def guess_phase(max_board: int, n1: int, n3: int, zb_n: int, zt_n: int) -> tuple[str, str]:
    if max_board <= 1:
        return "ice", "冰点启动：高度只有首板，优先看先锋和能否晋级。"
    if max_board == 2 and n3 == 0:
        return "repair", "修复发酵：二板出现，确认谁能晋级成龙，少铺后排。"
    if max_board >= 5 and zb_n >= 15:
        return "diverge", "高位分歧：高度已高且炸板不少，默认挑剔，不打补涨。"
    if max_board >= 4 and n1 >= 20:
        return "climax", "高潮加速：首板很多、高度起来。只看最强，买不起就空。"
    if zb_n >= 25 and n3 <= 2 and zt_n < 40:
        return "ebb", "偏退潮：炸板多、高位少。优先空仓，不倒车接人。"
    if max_board >= 3:
        return "climax", "偏高潮：三板及以上已出现，资金在认龙。"
    return "repair", "发酵中：看二板质量和板块集中度。"


def prev_trade_date(today: datetime) -> str:
    d = today - timedelta(days=1)
    for _ in range(10):
        if d.weekday() < 5:
            return d.strftime("%Y%m%d")
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


NOISE_BOARDS = {
    "转债标的", "融资融券", "深股通", "沪股通", "港股通", "AH股",
    "QFII重仓", "基金重仓", "机构重仓", "证金持股", "社保重仓",
    "中证500", "中证1000", "中证380", "上证380", "沪深300",
    "预盈预增", "股权转让", "高送转", "破净股", "低价股", "微盘股",
    "国企改革", "一带一路", "央企改革", "央国企改革", "地方国企改革",
    "题材股", "趋势股",
    "近期新高", "历史新高", "百日新高", "价值投资", "贬值受益",
    "东方财富热股", "最近多板",
    "破发股", "破增发价股", "参股银行", "参股券商", "参股保险",
    "回购增持", "举牌", "壳资源", "次新股",
    "创业板综", "科创板综", "股权集中",
}

PROVINCES = {
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
    "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
    "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
    "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆", "深圳",
}

WEAK_THEMES = {
    "乡村振兴", "新零售", "电商概念", "食品安全", "土地流转", "生态农业",
    "西部大开发", "长江三角", "东北振兴", "雄安新区", "粤港澳",
    "并购重组概念", "共同富裕", "新型城镇化",
}


def is_noise_board(name: str) -> bool:
    if not name:
        return True
    if name in NOISE_BOARDS or name in PROVINCES:
        return True
    if "中报" in name or "年报" in name:
        return True
    if name.startswith(("昨日", "最近", "东方财富", "百日", "MSCI", "富时", "标准普尔")):
        return True
    if name.endswith("板块") and name not in {"创业板", "科创板", "北交所"}:
        return True
    return False


def is_region_name(name: str) -> bool:
    if not name:
        return False
    if name in PROVINCES or name in {"内蒙古", "新疆", "宁夏", "广西", "西藏"}:
        return True
    if name.endswith("板块") and name not in {"创业板", "科创板", "北交所"}:
        return True
    return False


def is_weak_theme(name: str) -> bool:
    return bool(name) and (name in WEAK_THEMES or "中报" in name or "年报" in name)


_BOARD_KINDS: dict[str, str] | None = None


def _clist_diff(data: dict) -> list:
    diff = ((data or {}).get("data") or {}).get("diff") or []
    if isinstance(diff, dict):
        return list(diff.values())
    return list(diff)


def fetch_board_kinds() -> dict[str, str]:
    global _BOARD_KINDS
    if _BOARD_KINDS:
        return _BOARD_KINDS
    mapping: dict[str, str] = {}
    hosts = (
        "https://push2delay.eastmoney.com/api/qt/clist/get",
        "https://push2.eastmoney.com/api/qt/clist/get",
    )
    for kind, fs in (("industry", "m:90+t:2+f:!50"), ("concept", "m:90+t:3+f:!50"), ("region", "m:90+t:1+f:!50")):
        got = 0
        for pn in range(1, 12):
            raw = None
            for host in hosts:
                try:
                    raw = get_json(
                        f"{host}?pn={pn}&pz=100&po=1&np=1&fltt=2&invt=2&fid=f12&fs={fs}&fields=f12,f14",
                        retries=1,
                    )
                    break
                except Exception:
                    continue
            rows = _clist_diff(raw or {})
            if not rows:
                break
            for x in rows:
                code = str(x.get("f12") or "")
                if code:
                    mapping[code] = kind
            got += len(rows)
            if len(rows) < 100:
                break
        if got == 0:
            continue
    _BOARD_KINDS = mapping
    return mapping


def classify_board(row: dict, kinds: dict[str, str], seen_region: bool) -> str:
    bk = str(row.get("bk") or "")
    name = row.get("name") or ""
    kind = kinds.get(bk)
    if kind:
        return kind
    if is_region_name(name):
        return "region"
    if not seen_region:
        return "industry"
    return "concept"


def decorate_boards(rows: list[dict], kinds: dict[str, str] | None = None) -> list[dict]:
    kinds = kinds if kinds is not None else fetch_board_kinds()
    out = []
    seen_region = False
    for raw in rows:
        row = dict(raw)
        kind = classify_board(row, kinds, seen_region)
        if kind == "concept" and is_noise_board(row.get("name") or ""):
            kind = "noise"
        if kind == "region":
            seen_region = True
        row["kind"] = kind
        out.append(row)
    industry = [b for b in out if b.get("kind") == "industry"]
    industry.sort(key=lambda x: -int(x.get("up") or 0))
    for i, b in enumerate(industry[:3]):
        b["level"] = ("industry_l1", "industry_l2", "industry_l3")[i]
    return out


def assignable_concepts(r: dict) -> list[str]:
    boards = r.get("boards_em") or []
    hard = [
        b["name"]
        for b in boards
        if b.get("kind") == "concept" and b.get("name") and not is_weak_theme(b["name"])
    ]
    if hard:
        return list(dict.fromkeys(hard))
    weak = [b["name"] for b in boards if b.get("kind") == "concept" and b.get("name")]
    if weak:
        return list(dict.fromkeys(weak))
    l3 = next((b["name"] for b in boards if b.get("level") == "industry_l3"), None)
    if l3:
        return [l3]
    if r.get("industry"):
        return [r["industry"]]
    return []


def board_up_of(name: str, members: list) -> int:
    for m in members:
        for b in m.get("boards_em") or []:
            if b.get("name") == name:
                return int(b.get("up") or 0)
    return 0


def is_loose_theme(name: str, members: list, zt_n: int) -> bool:
    n = len(members)
    up = board_up_of(name, members)
    if n >= max(8, int(zt_n * 0.28)):
        return True
    if up >= 120 and n < 6:
        return True
    return False


def concept_rank_score(name: str, members: list, zt_n: int) -> int:
    n = len(members)
    max_b = max((x["boards"] for x in members), default=0)
    up = board_up_of(name, members)
    score = n * 10 + max_b * 2
    if n == 1:
        score -= 8
    if is_loose_theme(name, members, zt_n):
        score -= 30
    if up >= 120:
        score -= 18
    elif up >= 60:
        score -= 8
    if up:
        score += int(min(n / up, 0.5) * 40)
    if is_weak_theme(name):
        score -= 22
    return score


def secid(code: str) -> str:
    if code.startswith(("6", "9")):
        return "1." + code
    return "0." + code


def fetch_stock_boards(code: str) -> list[dict]:
    data = get_json(
        "https://push2.eastmoney.com/api/qt/slist/get?spt=3&np=3&fltt=2&invt=2&pz=80"
        f"&secid={secid(code)}&fields=f12,f14,f3,f104,f105",
        retries=0,
    )
    rows = []
    seen = set()
    for row in ((data.get("data") or {}).get("diff") or []):
        name = (row.get("f14") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        rows.append({
            "bk": str(row.get("f12") or ""),
            "name": name,
            "pct": num(row.get("f3")),
            "up": int(row.get("f104") or 0),
            "down": int(row.get("f105") or 0),
        })
    return decorate_boards(rows)


def apply_stock_boards(r: dict, boards: list[dict]) -> None:
    r["boards_em"] = boards
    industry = [b for b in boards if b.get("kind") == "industry"]
    by_level = {b.get("level"): b for b in industry if b.get("level")}
    r["industry_l1"] = (by_level.get("industry_l1") or {}).get("name") or ""
    r["industry_l2"] = (by_level.get("industry_l2") or {}).get("name") or r.get("industry") or ""
    r["industry_l3"] = (by_level.get("industry_l3") or {}).get("name") or ""
    if r.get("industry_l2"):
        r["industry"] = r["industry_l2"]
    region = next((b for b in boards if b.get("kind") == "region"), None)
    r["region"] = (region or {}).get("name") or ""
    r["concepts"] = [b["name"] for b in boards if b.get("kind") in ("concept", "noise")]


def attach_zt_counts(zt_rows: list) -> None:
    counts: Counter = Counter()
    for r in zt_rows:
        names = {b.get("name") for b in (r.get("boards_em") or []) if b.get("name")}
        for name in names:
            counts[name] += 1
    for r in zt_rows:
        for b in r.get("boards_em") or []:
            b["zt"] = counts.get(b.get("name"), 0)


def attach_concept_boards(zt_rows: list, fallback: dict | None = None) -> None:
    fallback = fallback or {}
    mapping: dict[str, list[dict]] = {}
    need = []
    for r in zt_rows:
        old = fallback.get(r["code"]) or []
        if old and isinstance(old[0] if old else None, dict) and old[0].get("kind"):
            mapping[r["code"]] = old
        else:
            need.append(r)
    if need:
        fetch_board_kinds()

        def one(r: dict) -> tuple[str, list[dict]]:
            try:
                names = fetch_stock_boards(r["code"])
            except Exception:
                names = []
            if not names:
                prev = fallback.get(r["code"]) or []
                if prev and isinstance(prev[0] if prev else None, dict):
                    names = prev
                elif r.get("industry"):
                    names = decorate_boards([{"bk": "", "name": r["industry"], "pct": None, "up": 0, "down": 0}])
            return r["code"], names

        workers = min(8, max(1, len(need)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = [pool.submit(one, r) for r in need]
            for fut in as_completed(futs):
                code, names = fut.result()
                mapping[code] = names
    for r in zt_rows:
        boards = mapping.get(r["code"]) or []
        if not boards and r.get("industry"):
            boards = decorate_boards([{"bk": "", "name": r["industry"], "pct": None, "up": 0, "down": 0}])
        apply_stock_boards(r, boards)
    attach_zt_counts(zt_rows)


def pick_main_theme(r: dict, ranked_concepts: list[str]) -> str:
    mine = set(r.get("assign_concepts") or [])
    for name in ranked_concepts:
        if name in mine:
            return name
    return (r.get("assign_concepts") or [r.get("industry_l3") or r.get("industry") or "未分类"])[0]


def assign_theme_roles(zt_rows: list, max_board: int) -> list[dict]:
    for r in zt_rows:
        r["assign_concepts"] = assignable_concepts(r)
    index: dict[str, list] = defaultdict(list)
    for r in zt_rows:
        for name in set(r["assign_concepts"]):
            index[name].append(r)
    zt_n = len(zt_rows) or 1
    ranked_concepts = [
        name for name, members in sorted(
            index.items(),
            key=lambda kv: (-concept_rank_score(kv[0], kv[1], zt_n), -len(kv[1]), kv[0]),
        )
        if not is_loose_theme(name, members, zt_n)
    ]
    if not ranked_concepts:
        ranked_concepts = [
            name for name, _members in sorted(
                index.items(),
                key=lambda kv: (-concept_rank_score(kv[0], kv[1], zt_n), -len(kv[1]), kv[0]),
            )
        ]
    for r in zt_rows:
        r["theme"] = pick_main_theme(r, ranked_concepts)

    groups: dict[str, list] = defaultdict(list)
    for r in zt_rows:
        groups[r["theme"]].append(r)

    theme_rows = []
    for theme, members in groups.items():
        vane = sorted(members, key=lambda x: (-x["boards"], x["first_seal_raw"], x["open_times"], x["turnover"]))[0]
        army = max(members, key=lambda x: x["float_mv_yi"])
        tight = not is_loose_theme(theme, members, zt_n)
        clustered = len(members) >= 3 and tight
        member_names = [x["name"] for x in sorted(members, key=lambda z: (-z["boards"], z["first_seal_raw"]))]
        for r in members:
            r["vane"] = vane["name"]
            r["vane_code"] = vane["code"]
            r["army"] = army["name"]
            r["army_code"] = army["code"]
            r["clustered"] = clustered
            r["theme_count"] = len(members)
            r["peers"] = [n for n in member_names if n != r["name"]]
            r["theme_alts"] = [
                c for c in (r.get("assign_concepts") or [])
                if c != theme and len(index.get(c) or []) >= 2 and not is_loose_theme(c, index.get(c) or [], zt_n)
            ][:5]
            is_vane = r["code"] == vane["code"]
            is_army = r["code"] == army["code"] and army["float_mv_yi"] >= 120 and not is_vane
            if is_vane:
                if clustered:
                    r["role"] = "题材龙" if r["boards"] >= 2 else "先锋/日内龙"
                else:
                    r["role"] = "孤立高标" if r["boards"] >= 2 else "题材未成群"
            elif is_army:
                r["role"] = "中军"
            elif r["boards"] < vane["boards"]:
                r["role"] = "补涨/跟风"
            elif r["first_seal_raw"] > vane["first_seal_raw"]:
                r["role"] = "跟风"
            else:
                r["role"] = "卡位"
            if r["boards"] == max_board:
                r["height_flag"] = "市场最高板"
            else:
                r["height_flag"] = ""
            r.pop("assign_concepts", None)
        theme_rows.append({
            "name": theme,
            "count": len(members),
            "max_board": max(x["boards"] for x in members),
            "vane": vane["name"],
            "vane_code": vane["code"],
            "army": army["name"],
            "clustered": clustered,
            "members": member_names,
        })
    theme_rows.sort(key=lambda x: (-x["count"], -x["max_board"]))
    return theme_rows


def fetch_zt_pool(date: str) -> list:
    data = get_json(
        "https://push2ex.eastmoney.com/getTopicZTPool"
        "?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt&Pageindex=0&pagesize=200"
        f"&sort=lbc:desc&date={date}"
    )
    return (data.get("data") or {}).get("pool") or []


def num(v):
    try:
        if v in (None, "-", ""):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def quote_hosts() -> tuple[str, ...]:
    hm = datetime.now().hour * 100 + datetime.now().minute
    live = (
        "https://push2.eastmoney.com/api/qt/stock/get",
        "https://push2delay.eastmoney.com/api/qt/stock/get",
    )
    delayed = (
        "https://push2delay.eastmoney.com/api/qt/stock/get",
        "https://push2.eastmoney.com/api/qt/stock/get",
    )
    if 915 <= hm < 1505:
        return live
    return delayed


def quote_one(code: str) -> tuple[str, dict | None]:
    row = {}
    for host in quote_hosts():
        try:
            data = get_json(
                f"{host}?invt=2&fltt=2&secid={secid(code)}"
                "&fields=f43,f46,f47,f48,f57,f58,f60,f168,f170",
                retries=0,
            )
        except Exception:
            continue
        row = data.get("data") or {}
        if row:
            break
    last = num(row.get("f43"))
    prev = num(row.get("f60"))
    open_p = num(row.get("f46"))
    pct = num(row.get("f170"))
    if pct is None and last is not None and prev:
        pct = round((last - prev) / prev * 100, 2)
    elif pct is not None:
        pct = round(pct, 2)
    open_pct = None
    if open_p is not None and prev:
        open_pct = round((open_p - prev) / prev * 100, 2)
    amount = num(row.get("f48"))
    volume = num(row.get("f47"))
    if last is None and pct is None and open_pct is None:
        return code, None
    return code, {
        "name": row.get("f58") or "",
        "pct": pct,
        "open_pct": open_pct,
        "turnover": None if num(row.get("f168")) is None else round(num(row.get("f168")), 2),
        "open": open_p,
        "prev": prev,
        "last": last,
        "volume": volume,
        "amount_yi": None if amount is None else round(amount / 1e8, 2),
    }


def batch_quotes(codes: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    uniq = [c for c in dict.fromkeys(codes) if c]
    if not uniq:
        return out
    workers = min(6, max(1, len(uniq)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(quote_one, c) for c in uniq]
        for fut in as_completed(futs):
            try:
                code, q = fut.result()
            except Exception:
                continue
            if q:
                out[code] = q
    for code in uniq:
        if code in out:
            continue
        try:
            _, q = quote_one(code)
        except Exception:
            q = None
        if q:
            out[code] = q
    return out


def session_now() -> dict:
    now = datetime.now()
    hm = now.hour * 100 + now.minute
    if hm < 915:
        return {
            "id": "preopen",
            "label": "开盘前",
            "hint": "还没竞价。用昨晚收盘的晋级名单等 9:15。",
            "default_view": "preopen",
        }
    if hm < 930:
        return {
            "id": "auction",
            "label": "集合竞价",
            "hint": "9:15–9:25 看昨日连板竞价。高开太多是核按钮，低开则晋级变弱。",
            "default_view": "preopen",
        }
    if 1130 <= hm < 1300:
        return {
            "id": "lunch",
            "label": "午休",
            "hint": "上午已经定性。开盘后页看涨停池，开盘前页回看今早竞价。",
            "default_view": "open",
        }
    if hm < 1130 or hm < 1500:
        return {
            "id": "open",
            "label": "开盘后",
            "hint": "看连板天梯、谁先封、谁开板。高度决定情绪，封板质量决定能不能碰。",
            "default_view": "open",
        }
    return {
        "id": "closed",
        "label": "已收盘",
        "hint": "开盘后页=今天复盘。开盘前页=明天早上 9:15 该盯谁。",
        "default_view": "open",
    }


def auction_stage(now: datetime | None = None) -> str:
    now = now or datetime.now()
    hm = now.hour * 100 + now.minute
    if hm < 915:
        return "未开竞价"
    if hm < 920:
        return "9:15-9:20 可撤单，看虚拟匹配"
    if hm < 925:
        return "9:20-9:25 不可撤，盯匹配价"
    if hm < 930:
        return "9:25 已定档，等开盘"
    if hm < 1500:
        return "已开盘"
    return "已收盘"


def auction_flag(pct) -> str:
    if pct is None:
        return "无报价"
    if pct >= 9.5:
        return "核按钮"
    if pct >= 5:
        return "高开强"
    if pct >= 0:
        return "平开附近"
    return "低开弱"


def attach_live_auction(payload: dict) -> dict:
    data = payload or {}
    yest = dict(data.get("yesterday") or {})
    rows = list(yest.get("preopen") or [])
    codes = [r.get("code") for r in rows if r.get("code")]
    quotes = batch_quotes(codes[:30])
    filled = 0
    for row in rows:
        q = quotes.get(row.get("code") or "")
        if not q:
            continue
        filled += 1
        if q.get("open_pct") is not None:
            row["open_pct"] = q.get("open_pct")
        if q.get("pct") is not None:
            row["today_pct"] = q.get("pct")
        row["match_pct"] = q.get("pct") if q.get("pct") is not None else q.get("open_pct")
        row["amount_yi"] = q.get("amount_yi")
        row["last"] = q.get("last")
        row["open"] = q.get("open")
    auction_rows = []
    for row in rows[:20]:
        match = row.get("match_pct")
        if match is None:
            match = row.get("today_pct") if row.get("today_pct") is not None else row.get("open_pct")
        auction_rows.append({
            "code": row.get("code"),
            "name": row.get("name"),
            "y_boards": row.get("y_boards"),
            "theme": row.get("industry") or row.get("theme"),
            "watch_level": row.get("watch_level"),
            "match_pct": match,
            "open_pct": row.get("open_pct"),
            "amount_yi": row.get("amount_yi"),
            "flag": auction_flag(row.get("open_pct") if row.get("open_pct") is not None else match),
        })
    yest["preopen"] = rows
    yest["auction_strong"] = [r for r in rows if (r.get("open_pct") or r.get("match_pct") or 0) >= 5][:8]
    yest["auction_weak"] = [r for r in rows if r.get("open_pct") is not None and r["open_pct"] < 0][:8]
    data["yesterday"] = yest
    data["auction"] = {
        "as_of": datetime.now().strftime("%H:%M:%S"),
        "stage": auction_stage(),
        "session": session_now().get("id"),
        "source": "东方财富行情 push2 stock/get。竞价时段走实时接口，匹配价用最新价。",
        "filled": filled,
        "rows": auction_rows,
    }
    data["session"] = session_now()
    return data


def explain_stock(r: dict, max_board: int, phase: str) -> list:
    reasons = []
    theme = r.get("theme") or r.get("industry") or "未分类"
    vane = r.get("vane") or ""
    count = r.get("theme_count") or 0
    clustered = r.get("clustered")
    hy = " / ".join([x for x in (r.get("industry_l1"), r.get("industry_l2"), r.get("industry_l3")) if x])
    if hy:
        reasons.append({"tone": "ok", "text": f"东财行业 {hy}" + (f" · {r['region']}" if r.get("region") else "") + "。行业只用来对照，不拿一级化工这种大类去并群。"})

    if r["boards"] == max_board:
        reasons.append({"tone": "warn", "text": f"今天市场最高 {r['boards']} 板。这是高度风向标，不等于题材一定成群，也不等于能追。"})
    elif r["boards"] >= 2:
        reasons.append({"tone": "ok", "text": f"{r['boards']} 连板，高度够进该题材的卡位观察。"})
    else:
        reasons.append({"tone": "warn", "text": "还是首板。只有题材成群、封得住，才有资格当先锋。"})

    if clustered:
        peer_txt = ("同涨 " + "、".join(r.get("peers") or []) + "。") if r.get("peers") else ""
        reasons.append({"tone": "ok", "text": f"定位概念「{theme}」，今日 {count} 只涨停，算成群。{peer_txt}风向标是 {vane}。"})
    else:
        reasons.append({"tone": "warn", "text": f"定位概念「{theme}」，今日该方向只有 {count} 只涨停，未成群。板块溢价不稳，高位更容易独立走弱。"})
    hot = []
    for b in r.get("boards_em") or []:
        if b.get("kind") == "concept" and int(b.get("zt") or 0) >= 2:
            hot.append(f"{b['name']}涨停{b['zt']}")
    if hot:
        reasons.append({"tone": "ok", "text": "东财概念今日涨停：" + "、".join(hot[:6]) + "。"})
    if r.get("theme_alts"):
        reasons.append({"tone": "warn", "text": f"同票还重叠「{'、'.join(r['theme_alts'])}」。主题材只并今天涨停扎堆、盘子不太大的硬概念。"})
    if vane and vane != r.get("name"):
        reasons.append({"tone": "warn", "text": f"跟风/补涨的比较对象是 {vane}，不是全市场最高板，也不是市值最大的中军。"})
    if r.get("army") and r.get("role") == "中军":
        reasons.append({"tone": "warn", "text": f"它是「{theme}」里流通市值最大的中军（约 {r['float_mv_yi']} 亿）。中军是基本面风向标，不是空间龙。"})

    if r["open_times"] == 0 and r["turnover"] < 8:
        reasons.append({"tone": "ok", "text": f"未开板且换手 {r['turnover']}%，属于一致封板（一字/低换手）。"})
    elif r["open_times"] == 0:
        reasons.append({"tone": "ok", "text": f"未开板，换手 {r['turnover']}%。比反复开板干净。"})
    elif r["open_times"] >= 8:
        reasons.append({"tone": "bad", "text": f"开板 {r['open_times']} 次，高位反复博弈，打板容易当对手盘。"})
    else:
        reasons.append({"tone": "warn", "text": f"开板 {r['open_times']} 次后回封，有还手，但仍是分歧。"})

    if r["turnover"] >= 20:
        reasons.append({"tone": "bad", "text": f"换手 {r['turnover']}%，按框架算高位天量，更像有人出货。"})
    elif r["turnover"] < 12:
        reasons.append({"tone": "ok", "text": f"换手 {r['turnover']}%，抛压相对小。"})

    if r["first_seal_raw"] <= 93100:
        reasons.append({"tone": "ok", "text": f"首次封板 {r['first_seal']}，盘面辨识度来得早。"})
    elif r["first_seal_raw"] >= 140000:
        reasons.append({"tone": "warn", "text": f"尾盘才封（{r['first_seal']}），日内龙头身份弱，容易是跟风。"})

    if r.get("role") in ("补涨/跟风", "跟风"):
        reasons.append({"tone": "bad", "text": f"相对 {vane} 高度更低或封得更晚，所以是跟风/补涨。框架里不拿它代替龙。"})
    if r.get("role") in ("题材未成群", "孤立高标"):
        reasons.append({"tone": "warn", "text": "不是说它不能涨，而是没有板块合力。短线溢价通常给成群的方向。"})
    if phase in ("diverge", "ebb") and r["boards"] >= 4:
        reasons.append({"tone": "bad", "text": "市场已在高位分歧/退潮，最高板默认只盯不打。"})
    if phase in ("diverge", "ebb") and r.get("role") in ("补涨/跟风", "跟风"):
        reasons.append({"tone": "bad", "text": "分歧日打补涨，是这套玩法里最常见的亏钱方式。"})

    seal = r.get("seal_money_yi") or 0
    if seal >= 1.5 and r["open_times"] == 0:
        reasons.append({"tone": "ok", "text": f"封单约 {seal} 亿，买盘还压着。"})
    elif seal < 0.3 and r["boards"] >= 3:
        reasons.append({"tone": "warn", "text": f"封单约 {seal} 亿，高位封单偏弱，容易炸。"})
    return reasons


def verdict_of(r: dict, phase: str, is_primary: bool) -> str:
    if r.get("role") in ("补涨/跟风", "跟风", "中军", "题材未成群"):
        return "躲"
    if r.get("open_times", 0) >= 8 or (r.get("diverge") and r.get("boards", 0) >= 4):
        return "躲" if phase in ("diverge", "ebb") else "盯"
    if is_primary:
        return "盯"
    return "躲" if r.get("role") == "孤立高标" and phase in ("diverge", "ebb") else "盯"


def yesterday_review(today: str, zt_today: list, zb_today: list) -> dict:
    now = datetime.strptime(today, "%Y%m%d")
    ydate = prev_trade_date(now)
    pool = []
    for _ in range(4):
        try:
            pool = fetch_zt_pool(ydate)
        except Exception:
            pool = []
        if pool:
            break
        ydate = prev_trade_date(datetime.strptime(ydate, "%Y%m%d"))
    zt_map = {r["code"]: r for r in zt_today}
    zb_map = {r["code"]: r for r in zb_today}
    y_rows = []
    for x in pool:
        y_rows.append(
            {
                "code": str(x.get("c") or ""),
                "name": x.get("n") or "",
                "y_boards": int(x.get("lbc") or 1),
                "industry": x.get("hybk") or "",
            }
        )
    quotes = batch_quotes([r["code"] for r in y_rows])
    promoted, failed, red = [], [], []
    for r in y_rows:
        q = quotes.get(r["code"]) or {}
        r["open_pct"] = q.get("open_pct")
        r["today_pct"] = q.get("pct")
        r["match_pct"] = q.get("pct") if q.get("pct") is not None else q.get("open_pct")
        r["amount_yi"] = q.get("amount_yi")
        r["last"] = q.get("last")
        t = zt_map.get(r["code"])
        reasons = [{"tone": "ok", "text": f"昨日 {r['y_boards']} 板，开盘前先看它竞价，不看跟风。"}]
        if r["open_pct"] is None and r["today_pct"] is None:
            reasons.append({"tone": "warn", "text": "今开和现价都没拉到，可能停牌，或行情接口没给这只。"})
        elif r["open_pct"] is None:
            reasons.append({"tone": "warn", "text": f"开盘价接口没给到。现涨幅 {r['today_pct']}%，用的是最新价相对昨收。"})
        elif r["open_pct"] >= 9:
            reasons.append({"tone": "bad", "text": f"今开 {r['open_pct']}%，接近涨停开，核按钮风险高。"})
        elif r["open_pct"] >= 3:
            reasons.append({"tone": "ok", "text": f"今开 {r['open_pct']}%，竞价偏强，只说明有人抢，不保证能封。"})
        elif r["open_pct"] >= 0:
            reasons.append({"tone": "warn", "text": f"今开 {r['open_pct']}%，平开附近，看能否回封。"})
        else:
            reasons.append({"tone": "bad", "text": f"今开 {r['open_pct']}%，低开，昨日涨停晋级变弱。"})
        if t:
            r["today_boards"] = t["boards"]
            r["result"] = "晋级"
            r["today_pct"] = t["pct"]
            if r["open_pct"] is None and t.get("first_seal_raw", 999999) <= 92530:
                r["open_pct"] = round(float(t.get("pct") or 10), 2)
                reasons.append({"tone": "ok", "text": f"今开按一字/早盘封板处理，约 {r['open_pct']}%。竞价几乎没给对手盘。" })
            reasons.append({"tone": "ok", "text": f"今天已经 {t['boards']} 板，算晋级成功。"})
            promoted.append(r)
        else:
            r["today_boards"] = 0
            pct = r["today_pct"]
            if pct is None and r["code"] in zb_map:
                pct = zb_map[r["code"]]["pct"]
                r["today_pct"] = pct
            if pct is None:
                r["result"] = "未知"
            elif pct >= 9.8:
                r["result"] = "接近涨停"
            elif pct >= 0:
                r["result"] = "红盘未板"
                red.append(r)
                reasons.append({"tone": "warn", "text": "红盘但没封住，不是晋级。"})
            else:
                r["result"] = "断板"
                failed.append(r)
                reasons.append({"tone": "bad", "text": "已经断板。开盘前若低开，更不要倒车接。"})
        if r["y_boards"] >= 3:
            r["watch_level"] = "重点"
        elif r["y_boards"] == 2:
            r["watch_level"] = "次重点"
        else:
            r["watch_level"] = "观察"
        r["reasons"] = reasons
    n = len(y_rows) or 1
    preopen = sorted(y_rows, key=lambda x: (-x["y_boards"], -(x.get("open_pct") if x.get("open_pct") is not None else -999)))
    return {
        "date": ydate,
        "count": len(y_rows),
        "promoted_n": len(promoted),
        "failed_n": len(failed),
        "red_n": len(red),
        "rate": round(len(promoted) / n, 3),
        "promoted": sorted(promoted, key=lambda x: -x.get("today_boards", 0))[:12],
        "failed": sorted(failed, key=lambda x: (x.get("today_pct") is None, x.get("today_pct") or 0))[:8],
        "preopen": preopen[:25],
        "auction_strong": [r for r in preopen if (r.get("open_pct") or 0) >= 5][:8],
        "auction_weak": [r for r in preopen if r.get("open_pct") is not None and r["open_pct"] < 0][:8],
    }


def build_tomorrow(ranked: list, zb_rows: list, phase: str, yest: dict) -> dict:
    promote = [
        r for r in ranked
        if r["role"] in ("空间龙候选", "卡位", "先锋首板")
        and r["open_times"] <= 1
        and r["turnover"] < 18
        and r["role"] != "补涨/跟风"
    ][:5]
    rebound = [
        r for r in ranked
        if (r["role"] == "空间龙候选" and r["diverge"]) or r["open_times"] >= 8
    ][:3]
    theme = ranked[0]["industry"] if ranked else ""
    # 容量主线：涨停只数最多且高度不高时，只观察先锋
    # 已在 picks 里处理
    if phase in ("diverge", "ebb"):
        plan = "明天先看高位是否反包。没有反包就继续空，不要倒车接补涨。"
    elif phase == "climax":
        plan = "明天只盯空间龙是否还在。跟风、补涨一律降低权重。"
    elif phase == "ice":
        plan = "明天核心看先锋能不能二板。二板出来再认龙。"
    else:
        plan = "明天看谁能把二板、三板走实。晋级失败的方向减仓。"
    if yest.get("rate", 1) < 0.25 and yest.get("count", 0) >= 20:
        plan += "昨日涨停晋级偏弱，情绪已经在降温。"
    return {
        "plan": plan,
        "promote": promote,
        "rebound": rebound,
        "theme_note": theme,
    }


def build_morning_watch(zt_rows: list) -> list:
    rows = sorted(zt_rows, key=lambda x: (-x["boards"], x["first_seal_raw"]))
    out = []
    for r in rows[:20]:
        if r["boards"] >= 3:
            note = "明早重点。只验证竞价是否还在、会不会核。"
        elif r["boards"] == 2:
            note = "次重点。看二板能否继续，不看它的补涨队友。"
        else:
            note = "首板观察。没有成群就降权。"
        if r.get("role") in ("补涨/跟风", "跟风"):
            note = f"补涨票。明早不拿它当龙，风向标是 {r.get('vane') or '—'}"
        if r.get("verdict") == "躲":
            note = "纪律上明早先躲。" + note
        out.append({
            "code": r["code"],
            "name": r["name"],
            "boards": r["boards"],
            "pct": r.get("pct"),
            "turnover": r.get("turnover"),
            "open_times": r.get("open_times"),
            "role": r.get("role"),
            "verdict": r.get("verdict"),
            "theme": r.get("theme") or r.get("industry"),
            "industry": r.get("industry"),
            "industry_l1": r.get("industry_l1"),
            "industry_l2": r.get("industry_l2"),
            "industry_l3": r.get("industry_l3"),
            "region": r.get("region"),
            "boards_em": r.get("boards_em") or [],
            "watch_note": note,
        })
    return out


def slim_bet(b: dict) -> dict:
    return {
        "code": b.get("code"),
        "name": b.get("name"),
        "side": b.get("side"),
        "why": b.get("why"),
        "pct": b.get("pct"),
        "open_pct": b.get("open_pct"),
        "fill": b.get("fill"),
        "hit": b.get("hit"),
        "pnl": b.get("pnl"),
        "pnl_yuan": b.get("pnl_yuan"),
        "size": b.get("size"),
        "note": b.get("note"),
    }


def make_actors(phase: str, zt_rows: list, picks: dict, review: list | None = None, date: str = "") -> list:
    primary = picks.get("primary") or []
    if phase in ("diverge", "ebb"):
        rules_bets = [{
            "code": r["code"],
            "name": r["name"],
            "side": "盯不打",
            "why": r.get("action") or "分歧日只盯不打",
        } for r in primary[:2]]
        rules_stance = "空仓优先，最多盯不打"
    else:
        rules_bets = [{
            "code": r["code"],
            "name": r["name"],
            "side": "盯",
            "why": r.get("action") or "做最强",
        } for r in primary[:2]]
        rules_stance = "做最强"
    chase_src = [
        r for r in zt_rows
        if r.get("role") in ("补涨/跟风", "跟风")
    ]
    chase_src.sort(key=lambda x: (-(x.get("boards") or 0), x.get("first_seal_raw") or 999999))
    chase = []
    for r in chase_src[:2]:
        chase.append({
            "code": r["code"],
            "name": r["name"],
            "side": "打补涨",
            "why": f"跟风 {r.get('vane') or ''}".strip(),
        })
    seed = {"starting": store.STARTING_CASH, "cash": store.STARTING_CASH}
    return [
        {"id": "rules", "name": "纪律派", "stance": rules_stance, "bets": rules_bets, **seed},
        {"id": "chase", "name": "补涨派", "stance": "专打后排", "bets": chase, **seed},
        {"id": "cash", "name": "空仓派", "stance": "全天空仓", "bets": [], **seed},
        {"id": "ai", "name": "大模型", "stance": "待选股", "bets": [], "note": "点「让AI选股」。规则只提供盘面标签，选股由模型拍板。", **seed},
    ]


PLAYBOOK = (
    "你是这套龙头短线的选股员，负责射门：盯谁、躲谁、能不能进攻。人类只给你打法思路和盘面标签，最终名单必须由你出。"
    "打法思路（约束，不是替你写结论）："
    "1.高度：最高板才有空间资格。"
    "2.质量：未开板、换手不太大，优于反复开板。"
    "3.身份：跟风的风向标是该题材最高、最早封的那只，不是市值最大的中军。"
    "4.成群：同题材不足3只算未成群，溢价不稳。"
    "5.情绪：晋级弱、高位分歧时要挑剔，不要用补涨代替龙。"
    "6.每人10万纸上资金，side=盯 或 打补涨 才按每笔2万记账；盯不打、空仓、买不进资金不动。"
    "7.涨停可能买不进。不要写仓位和买点价格。"
    "8.若 decision_window=auction：必须依据刚拉的东财竞价 auction.rows 拍板，不要只用昨晚收盘标签。"
    "高开≥9.5%按核按钮/买不进；低开说明晋级变弱，不要倒车接；竞价里不买补涨，只验证昨日连板最强的那只。"
    "engine_phase / engine_verdict / role 只是规则机打的标签，供你参考，不要照抄。你必须自己判断今天打还是不打。"
    "不要只会空仓。若空仓，watch可以为空，但think要写清缺什么信号才出手。"
    "recent_paper 是已结算纸上结果，含净值cash。盯不打和空仓盈亏是0，买不进也是0，不要把没买到当成功。"
    "只输出一个JSON，不要Markdown："
    "{\"stance\":\"一句话可执行立场\",\"plan\":\"盘中或明早怎么用这名单\",\"think\":\"6-10句，先情绪再题材再个股\","
    "\"watch\":[{\"code\":\"\",\"name\":\"\",\"side\":\"盯|盯不打\",\"why\":\"\"}],"
    "\"avoid\":[{\"code\":\"\",\"name\":\"\",\"why\":\"\"}]}"
    "watch最多3个，avoid最多4个。side=盯 表示你选它当核心标的（纸上记账）；盯不打=只当情绪温度计。"
)


def slim_tape_row(r: dict) -> dict:
    return {
        "name": r.get("name"),
        "code": r.get("code"),
        "boards": r.get("boards"),
        "role": r.get("role"),
        "industry": r.get("industry"),
        "industry_l3": r.get("industry_l3"),
        "theme": r.get("theme"),
        "clustered": r.get("clustered"),
        "theme_count": r.get("theme_count"),
        "concepts": [
            {"name": b.get("name"), "zt": b.get("zt"), "kind": b.get("kind")}
            for b in (r.get("boards_em") or [])
            if b.get("kind") in ("concept", "industry")
        ][:8],
        "vane": r.get("vane"),
        "army": r.get("army"),
        "engine_verdict": r.get("verdict"),
        "open_times": r.get("open_times"),
        "turnover": r.get("turnover"),
        "first_seal": r.get("first_seal"),
        "pct": r.get("pct"),
        "peers": (r.get("peers") or [])[:6],
    }


def actor_from_desk(desk: dict) -> dict:
    model = desk.get("model") or current_model()
    watch = desk.get("watch") or []
    bets = []
    for item in watch[:3]:
        bets.append({
            "code": item.get("code"),
            "name": item.get("name"),
            "side": item.get("side") or "盯不打",
            "why": item.get("why") or "",
        })
    return {
        "id": "ai",
        "name": model,
        "stance": desk.get("stance") or "已接入",
        "bets": bets,
        "think": desk.get("think") or "",
        "plan": desk.get("plan") or "",
        "avoid": desk.get("avoid") or [],
        "note": desk.get("note") or f"模型 {model}，纸上选股，不是下单。",
    }


def desk_is_weak(desk: dict | None) -> bool:
    if not desk:
        return True
    if desk.get("stance") in ("未接入", "调用失败", "待选股"):
        return True
    return not (desk.get("watch") or desk.get("think") or desk.get("plan"))


def try_ai_actor(phase: str, zt_rows: list, review: list | None = None, date: str = "", picks: dict | None = None, yest: dict | None = None, phase_why: str = "") -> dict:
    return actor_from_desk(try_ai_desk(phase, zt_rows, picks or {}, yest or {}, review=review, date=date, phase_why=phase_why, auction=None))


def try_ai_desk(phase: str, zt_rows: list, picks: dict, yest: dict, review: list | None = None, date: str = "", phase_why: str = "", auction: dict | None = None) -> dict:
    load_local_env()
    date = date or datetime.now().strftime("%Y%m%d")
    key = (os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
    use_deepseek = bool((os.environ.get("DEEPSEEK_API_KEY") or "").strip())
    base = "https://api.deepseek.com/chat/completions" if use_deepseek else "https://api.openai.com/v1/chat/completions"
    model = current_model()
    empty = {
        "model": model,
        "stance": "未接入",
        "think": "",
        "plan": "",
        "watch": [],
        "avoid": [],
        "note": "在项目目录 .env 里填写 DEEPSEEK_API_KEY=你的key，然后重启 start.bat。不真下单。",
    }
    if not key:
        store.log_ai_run(date, model=model, status="skip", error="no_key")
        return empty
    rows = sorted(zt_rows, key=lambda x: (-(x.get("boards") or 0), x.get("first_seal_raw") or 999999))
    themes = []
    seen = set()
    for r in zt_rows:
        name = r.get("theme")
        if name and name not in seen:
            seen.add(name)
            themes.append({"name": name, "count": r.get("theme_count"), "clustered": r.get("clustered"), "vane": r.get("vane"), "army": r.get("army")})
    sess = session_now()
    auction = auction or {}
    decision_window = "auction" if sess.get("id") == "auction" or auction.get("session") == "auction" else sess.get("id") or "open"
    yest = yest or {}
    context = {
        "decision_window": decision_window,
        "session": sess,
        "engine_phase": phase,
        "engine_phase_why": phase_why,
        "max_board": max((r.get("boards") or 0) for r in zt_rows) if zt_rows else 0,
        "zt_count": len(zt_rows),
        "yesterday": {
            "date": yest.get("date"),
            "count": yest.get("count"),
            "promoted_n": yest.get("promoted_n"),
            "failed_n": yest.get("failed_n"),
            "rate": yest.get("rate"),
        },
        "auction": {
            "as_of": auction.get("as_of"),
            "stage": auction.get("stage") or auction_stage(),
            "filled": auction.get("filled"),
            "source": auction.get("source"),
            "rows": auction.get("rows") or [],
        },
        "themes": themes[:10],
        "tape": [slim_tape_row(r) for r in rows[:25]],
        "engine_picks": {
            "stance": (picks or {}).get("stance"),
            "primary": [slim_tape_row(r) for r in ((picks or {}).get("primary") or [])[:3]],
            "avoid": [slim_tape_row(r) for r in ((picks or {}).get("avoid") or [])[:6]],
        },
        "recent_paper": review or [],
        "account": {
            "starting": store.STARTING_CASH,
            "bet_size": store.BET_SIZE,
            "equity": [{k: r[k] for k in ("id", "name", "cash", "pnl_yuan", "days")} for r in store.scoreboard()],
        },
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": PLAYBOOK},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ],
    }
    if "reasoner" not in model:
        payload["temperature"] = 0.2
    req = urllib.request.Request(base, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + key,
        "User-Agent": "Mozilla/5.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        msg = ((raw.get("choices") or [{}])[0].get("message") or {})
        text = (msg.get("content") or msg.get("reasoning_content") or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.split("\n", 1)[-1]
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise RuntimeError("模型没有返回JSON")
        parsed = json.loads(text[start:end + 1])
        watch = []
        for item in (parsed.get("watch") or parsed.get("bets") or [])[:3]:
            if not (item.get("code") or item.get("name")):
                continue
            watch.append({
                "code": item.get("code"),
                "name": item.get("name"),
                "side": item.get("side") or "盯",
                "why": item.get("why") or "",
            })
        avoid = []
        for item in (parsed.get("avoid") or [])[:4]:
            if not (item.get("code") or item.get("name")):
                continue
            avoid.append({
                "code": item.get("code"),
                "name": item.get("name"),
                "why": item.get("why") or "",
            })
        desk = {
            "model": model,
            "stance": parsed.get("stance") or "已选股",
            "plan": (parsed.get("plan") or "").strip(),
            "think": (parsed.get("think") or "").strip(),
            "watch": watch,
            "avoid": avoid,
            "note": f"模型 {model}，纸上选股，不是下单。",
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        store.log_ai_run(date, model=model, status="ok", context=context, result=desk)
        return desk
    except Exception as exc:
        store.log_ai_run(date, model=model, status="fail", context=context if "context" in locals() else None, error=str(exc))
        return {
            "model": model,
            "stance": "调用失败",
            "think": "",
            "plan": "",
            "watch": [],
            "avoid": [],
            "note": str(exc),
        }



def settle_actor(actor: dict, outcome: dict[str, dict]) -> dict:
    settled = []
    wins = losses = 0
    pnl_yuan = 0.0
    size = float(store.BET_SIZE)
    for b in actor.get("bets") or []:
        row = dict(b)
        code = row.get("code")
        oc = outcome.get(code) or {}
        pct = oc.get("today_pct")
        open_pct = oc.get("open_pct")
        row["pct"] = pct
        row["open_pct"] = open_pct
        side = row.get("side") or ""
        if side in ("空仓",) or not code:
            row["fill"] = "空仓"
            row["hit"] = None
            row["pnl"] = 0
            row["pnl_yuan"] = 0
            row["size"] = 0
            row["note"] = "没有持仓"
        elif side == "盯不打":
            row["fill"] = "观察"
            row["hit"] = None
            row["pnl"] = 0
            row["pnl_yuan"] = 0
            row["size"] = 0
            row["note"] = f"收盘 {pct}%" if pct is not None else "无价格"
        elif open_pct is not None and open_pct >= 9.5:
            row["fill"] = "买不进"
            row["hit"] = False
            row["pnl"] = 0
            row["pnl_yuan"] = 0
            row["size"] = 0
            row["note"] = f"今开 {open_pct}%，按涨停开处理，纸上不算买到"
            losses += 1
        elif pct is None:
            row["fill"] = "无数据"
            row["hit"] = None
            row["pnl"] = 0
            row["pnl_yuan"] = 0
            row["size"] = 0
            row["note"] = "没有次日涨幅"
        else:
            yuan = round(size * float(pct) / 100.0, 2)
            row["fill"] = "按收盘涨幅"
            row["hit"] = pct > 0
            row["pnl"] = round(pct, 2)
            row["pnl_yuan"] = yuan
            row["size"] = size
            row["note"] = f"2万 × {pct}% = {yuan}元"
            pnl_yuan += yuan
            if pct > 0:
                wins += 1
            else:
                losses += 1
        settled.append(slim_bet(row))
    done = wins + losses
    return {
        "id": actor.get("id"),
        "name": actor.get("name"),
        "stance": actor.get("stance"),
        "note": actor.get("note"),
        "think": actor.get("think"),
        "bets": settled,
        "wins": wins,
        "losses": losses,
        "pnl_yuan": round(pnl_yuan, 2),
        "pnl": round(pnl_yuan / store.STARTING_CASH * 100.0, 2) if store.STARTING_CASH else 0,
        "rate": round(wins / done, 3) if done else None,
        "settled": True,
    }


def outcome_for_bets(actors: list, yest: dict) -> dict:
    outcome = {r["code"]: r for r in (yest.get("preopen") or []) if r.get("code")}
    missing = []
    for actor in actors:
        for bet in actor.get("bets") or []:
            code = bet.get("code")
            if code and code not in outcome:
                missing.append(code)
    if missing:
        extra = batch_quotes(missing)
        for code, quote in extra.items():
            if not quote:
                continue
            outcome[code] = {
                "code": code,
                "open_pct": quote.get("open_pct"),
                "today_pct": quote.get("pct"),
            }
    return outcome


def actionable_bet_codes(actors: list) -> list[str]:
    codes = []
    for actor in actors:
        for bet in actor.get("bets") or []:
            side = bet.get("side") or ""
            code = bet.get("code")
            if code and side not in ("空仓", "盯不打"):
                codes.append(code)
    return codes


def ai_is_weak(actor: dict | None) -> bool:
    if not actor:
        return True
    if actor.get("stance") in ("未接入", "调用失败", "待选股"):
        return True
    return not (actor.get("bets") or actor.get("think"))


def can_settle(actors: list, yest: dict, outcome: dict) -> bool:
    codes = actionable_bet_codes(actors)
    if not codes:
        return True
    priced = 0
    for code in codes:
        row = outcome.get(code) or {}
        if row.get("today_pct") is not None or row.get("open_pct") is not None:
            priced += 1
    if priced >= max(1, (len(codes) + 1) // 2):
        return True
    filled = sum(1 for r in (yest.get("preopen") or []) if r.get("today_pct") is not None)
    return filled >= max(3, len(yest.get("preopen") or []) // 3)


def update_paper(date: str, phase: str, zt_rows: list, picks: dict, yest: dict, force_ai: bool = False, phase_why: str = "", auction: dict | None = None) -> dict:
    store.init()
    store.import_legacy_journal()
    ydate = str((yest or {}).get("date") or "")
    if ydate and ydate != date:
        prev = store.get_day(ydate)
        if prev and not prev.get("settled"):
            outcome = outcome_for_bets(prev.get("actors") or [], yest or {})
            if can_settle(prev.get("actors") or [], yest or {}, outcome):
                settled_actors = [settle_actor(actor, outcome) for actor in (prev.get("actors") or [])]
                store.set_settled(ydate, settled_actors)
    review = store.recent_review(5)
    existing = store.get_day(date)
    if not existing:
        store.put_new_day(date, phase, make_actors(phase, zt_rows, picks, review=review, date=date))
        existing = store.get_day(date)
    if force_ai:
        if existing and existing.get("settled"):
            raise RuntimeError("这一天已经结算，不能再改AI选股")
        desk = try_ai_desk(phase, zt_rows, picks, yest or {}, review=review, date=date, phase_why=phase_why, auction=auction)
        store.set_ai_desk(date, desk)
        store.replace_ai_actor(date, actor_from_desk(desk))
    elif existing and not existing.get("settled"):
        day = store.get_day(date)
        if day:
            for actor in day.get("actors") or []:
                relabel_ai_actor(actor)
            store.touch_actors(date, day["actors"])
    paper = store.paper_payload(date)
    today = paper.get("today")
    if today and not today.get("settled"):
        for actor in today.get("actors") or []:
            relabel_ai_actor(actor)
    store.export_journal()
    return paper


def rerun_ai_pick(payload: dict) -> dict:
    data = attach_live_auction(dict(payload or {}))
    date = str(data.get("date") or "")
    yest = data.get("yesterday") or {}
    if not date or not ((data.get("limit_up") or []) or (yest.get("preopen") or [])):
        raise RuntimeError("没有可用盘面，先刷新数据")
    paper = update_paper(
        date,
        data.get("phase") or "diverge",
        data.get("limit_up") or [],
        data.get("picks") or {},
        yest,
        force_ai=True,
        phase_why=data.get("phase_why") or "",
        auction=data.get("auction") or {},
    )
    data["paper"] = paper
    data["ai"] = store.get_ai_desk(date)
    data["session"] = session_now()
    return data


def fetch_today(prev: dict | None = None) -> dict:
    date = datetime.now().strftime("%Y%m%d")
    prev = prev or {}
    try:
        zt = get_json(
            "https://push2ex.eastmoney.com/getTopicZTPool"
            f"?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt&Pageindex=0&pagesize=200&sort=lbc:desc&date={date}"
        )
    except Exception:
        zt = {}
    try:
        zb = get_json(
            "https://push2ex.eastmoney.com/getTopicZBPool"
            f"?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt&Pageindex=0&pagesize=200&sort=zdp:desc&date={date}"
        )
    except Exception:
        zb = {}
    try:
        dt = get_json(
            "https://push2ex.eastmoney.com/getTopicDTPool"
            f"?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt&Pageindex=0&pagesize=100&sort=fund:asc&date={date}"
        )
    except Exception:
        dt = {}
    try:
        bk = get_json(
            "https://push2.eastmoney.com/api/qt/clist/get"
            "?pn=1&pz=30&po=1&np=1&fltt=2&invt=2&fid=f3"
            "&fs=m:90+t:3+f:!50&fields=f12,f14,f2,f3,f8,f104,f105,f128,f140,f136"
        )
        bks = ((bk.get("data") or {}).get("diff") or [])
    except Exception:
        bks = []

    pool = (zt.get("data") or {}).get("pool") or []
    sess = session_now()
    if not pool:
        if prev.get("limit_up") and sess.get("id") in ("preopen", "auction", "weekend", "closed"):
            payload = dict(prev)
            payload["date"] = date
            payload["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            payload["session"] = sess
            try:
                payload["yesterday"] = yesterday_review(date, prev.get("limit_up") or [], [])
            except Exception:
                payload["yesterday"] = prev.get("yesterday") or {}
            attach_live_auction(payload)
            try:
                if payload.get("limit_up") and not (payload["limit_up"][0] or {}).get("boards_em"):
                    attach_concept_boards(payload["limit_up"], fallback={})
                    payload = relabel_cached(payload)
            except Exception:
                pass
            payload["fetch_error"] = "今天涨停池还没出来。已保留上一份天梯，并重新拉了东财竞价/今开报价。"
            payload["paper"] = update_paper(
                date,
                payload.get("phase") or "diverge",
                payload.get("limit_up") or [],
                payload.get("picks") or {},
                payload.get("yesterday") or {},
                phase_why=payload.get("phase_why") or "",
                auction=payload.get("auction") or {},
            )
            return persist_payload(payload)
        raise RuntimeError("东方财富涨停池为空或连不上，已保留上一份盘面")
    zpool = (zb.get("data") or {}).get("pool") or []
    dpool = (dt.get("data") or {}).get("pool") or []

    zt_rows = []
    for x in pool:
        boards = int(x.get("lbc") or 1)
        open_times = int(x.get("zbc") or 0)
        turnover = round(float(x.get("hs") or 0), 2)
        zt_stat = x.get("zttj") or {}
        zt_rows.append(
            {
                "code": str(x.get("c") or ""),
                "name": x.get("n") or "",
                "pct": round(float(x.get("zdp") or 0), 2),
                "boards": boards,
                "open_times": open_times,
                "first_seal": fmt_time(x.get("fbt")),
                "first_seal_raw": int(x.get("fbt") or 150000),
                "last_seal": fmt_time(x.get("lbt")),
                "turnover": turnover,
                "amount_yi": yi(x.get("amount")),
                "float_mv_yi": yi(x.get("ltsz")),
                "seal_money_yi": yi(x.get("fund")),
                "industry": x.get("hybk") or "未分类",
                "days_zt": zt_stat.get("days") or zt_stat.get("ct") or None,
                "seal": seal_quality(open_times, turnover),
            }
        )

    zb_rows = [
        {
            "code": str(x.get("c") or ""),
            "name": x.get("n") or "",
            "pct": round(float(x.get("zdp") or 0), 2),
            "industry": x.get("hybk") or "",
            "open_times": int(x.get("zbc") or 0),
            "turnover": round(float(x.get("hs") or 0), 2),
        }
        for x in zpool
    ]
    dt_rows = [
        {
            "code": str(x.get("c") or ""),
            "name": x.get("n") or "",
            "pct": round(float(x.get("zdp") or 0), 2),
            "industry": x.get("hybk") or "",
        }
        for x in dpool
    ]
    bk_rows = [
        {
            "code": b.get("f12"),
            "name": b.get("f14"),
            "pct": b.get("f3"),
            "up_count": b.get("f104"),
            "down_count": b.get("f105"),
            "leader": b.get("f128") or b.get("f140"),
            "leader_pct": b.get("f136"),
        }
        for b in bks
    ]

    max_board = max((r["boards"] for r in zt_rows), default=0)
    by_board: dict[int, list] = defaultdict(list)
    for r in zt_rows:
        by_board[r["boards"]].append(r)

    prev_concepts = {}
    if prev.get("date") == date:
        for row in prev.get("limit_up") or []:
            if row.get("code") and row.get("boards_em"):
                prev_concepts[row["code"]] = row["boards_em"]
    attach_concept_boards(zt_rows, fallback=prev_concepts)
    themes = assign_theme_roles(zt_rows, max_board)
    for r in zt_rows:
        r["diverge"] = r["turnover"] >= 20 or r["open_times"] >= 3
        r["action"] = suggest_action(r, max_board)

    n1 = len(by_board.get(1, []))
    n3 = len([r for r in zt_rows if r["boards"] >= 3])
    phase, phase_why = guess_phase(max_board, n1, n3, len(zb_rows), len(zt_rows))

    ranked = []
    for r in zt_rows:
        score = r["boards"] * 20
        if r["open_times"] == 0:
            score += 8
        score -= min(r["open_times"], 8) * 2
        if r["diverge"] and r["boards"] < max_board:
            score -= 8
        if r["role"] in ("题材龙", "先锋/日内龙", "卡位", "孤立高标"):
            score += 6
        if r["role"] in ("补涨/跟风", "跟风"):
            score -= 10
        if r["role"] in ("题材未成群", "中军"):
            score -= 4
        score += max(0, (110000 - r["first_seal_raw"]) / 15000)
        if r["float_mv_yi"] > 400:
            score -= 4
        r["score"] = round(score, 1)
        r["reasons"] = explain_stock(r, max_board, phase)
        ranked.append(r)
    ranked.sort(key=lambda x: (-x["score"], x["first_seal_raw"]))

    picks = build_picks(ranked, phase, max_board)
    primary_codes = {r["code"] for r in picks["primary"]}
    for r in zt_rows:
        r["verdict"] = verdict_of(r, phase, r["code"] in primary_codes)
    ladder = []
    for h in sorted(by_board.keys(), reverse=True):
        ladder.append({
            "boards": h,
            "stocks": [
                {
                    "code": x["code"],
                    "name": x["name"],
                    "role": x["role"],
                    "verdict": x["verdict"],
                    "open_times": x["open_times"],
                    "turnover": x["turnover"],
                    "industry": x.get("theme") or x["industry"],
                    "theme": x.get("theme") or "",
                    "vane": x.get("vane") or "",
                }
                for x in sorted(by_board[h], key=lambda z: z["first_seal_raw"])
            ],
        })
    yest = {"date": "", "count": 0, "promoted_n": 0, "failed_n": 0, "red_n": 0, "rate": 0, "promoted": [], "failed": [], "preopen": []}
    prev_yest = prev.get("yesterday") or {}
    prev_rows = prev_yest.get("preopen") or []
    filled = sum(1 for r in prev_rows if r.get("today_pct") is not None)
    if prev.get("date") == date and prev_rows and filled >= max(3, len(prev_rows) // 3) and session_now().get("id") != "auction":
        yest = prev_yest
    else:
        try:
            yest = yesterday_review(date, zt_rows, zb_rows)
        except Exception:
            if prev_yest:
                yest = prev_yest
    tomorrow = build_tomorrow(ranked, zb_rows, phase, yest)
    morning = build_morning_watch(zt_rows)
    paper = update_paper(date, phase, zt_rows, picks, yest, phase_why=phase_why)
    payload = {
        "date": date,
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "东方财富公开接口（涨停池/炸板/跌停/昨日涨停）",
        "phase": phase,
        "phase_name": {
            "ice": "冰点启动",
            "repair": "修复发酵",
            "climax": "高潮加速",
            "diverge": "高位分歧",
            "ebb": "退潮",
        }[phase],
        "phase_why": phase_why,
        "max_board": max_board,
        "zt_count": len(zt_rows),
        "zb_count": len(zb_rows),
        "dt_count": len(dt_rows),
        "board_dist": {str(k): len(v) for k, v in sorted(by_board.items())},
        "hot_industries": [{"name": n, "count": c} for n, c in Counter(r.get("theme") or r["industry"] for r in zt_rows).most_common(12)],
        "themes": themes[:12],
        "data_source": {
            "limit_up": "东方财富涨停池 push2ex.eastmoney.com/getTopicZTPool（含连板、换手、开板次数、首次封板、行业hybk）",
            "broken": "东方财富炸板池 getTopicZBPool",
            "quotes": "东方财富行情 push2 stock/get。竞价/盘中走实时，收盘后走延时。匹配价用最新价，今开用开盘价。",
            "theme": "东方财富个股所属板块 slist，按东财盘口拆成行业/地区/概念。主题材只用概念里今天涨停扎堆、盘子不太大的硬标签，不用基础化工这种一级行业去并群。",
            "limit": "同一只票会挂十几个概念。深股通、央国企改革只展示，不参与成群。西部大开发等弱标签降权。",
        },
        "sectors": bk_rows[:20],
        "limit_up": zt_rows,
        "broken": zb_rows[:50],
        "limit_down": dt_rows[:30],
        "ranked": ranked[:25],
        "picks": picks,
        "yesterday": yest,
        "tomorrow": tomorrow,
        "morning_watch": morning,
        "paper": paper,
        "session": session_now(),
        "ladder": ladder,
        "rules": [
            "高度：先看今天最高几板，最高板才有资格当空间龙。",
            "质量：未开板、换手不太大，比反复开板干净。",
            "身份：跟风/补涨的风向标是该题材里最高、最早封的那只，不是全市场最高板，也不是市值最大的中军。",
            "成群：按东财概念并群，至少 3 只且板块不能太大。一级行业、深股通、地域政策不当主线。",
            "情绪：昨日涨停今天晋级不到 25%，按分歧/退潮处理，默认空仓。",
            "开盘前：盘中回看今早竞价。收盘后改看明天的名单——用今天的连板，不是昨天那张缺今开的表。",
            "开盘后 / 收盘：看天梯谁先封、谁炸板。买不起龙就空，不降标准。",
            "纸上对打：纪律派、补涨派、空仓派每天记账，次日用收盘涨幅结算。大模型要配 API Key 才上场，不接下单。",
        ],
        "disclaimer": "公开数据筛选，不是买卖建议。四个角色各10万纸上资金，成交按每笔2万计。涨停可能买不进。",
    }
    attach_live_auction(payload)
    return persist_payload(payload)


def persist_payload(payload: dict) -> dict:
    try:
        store.init()
        if payload.get("date") and payload.get("limit_up"):
            store.save_market_from_payload(payload)
    except Exception as exc:
        payload["ledger_error"] = str(exc)
    return payload


def suggest_action(r: dict, max_board: int) -> str:
    if r["role"] in ("补涨/跟风", "跟风"):
        return f"不碰补涨，风向标是 {r.get('vane') or '该题材龙头'}"
    if r["role"] == "中军":
        return f"中军不是龙。空间看 {r.get('vane') or '题材龙'}"
    if r["role"] in ("题材龙", "孤立高标") and r["open_times"] >= 8:
        return "高位反复开板，不追"
    if r["diverge"] and r["boards"] >= 3:
        return "只观察，不打板"
    if r["role"] == "题材龙" and not r["diverge"]:
        return "该题材风向标，看晋级"
    if r["role"] == "先锋/日内龙":
        return "成群题材的日内龙，看能否晋级"
    if r["role"] in ("卡位",) and r["open_times"] == 0 and r["turnover"] < 18:
        return "质量尚可，看能否晋级"
    if r["role"] in ("题材未成群", "孤立高标"):
        return "题材未成群，谨慎"
    return "观察"


def build_picks(ranked: list, phase: str, max_board: int) -> dict:
    dragons = [r for r in ranked if r["role"] in ("题材龙", "先锋/日内龙", "孤立高标")]
    clean_high = [
        r for r in ranked
        if r["boards"] >= 2 and r["open_times"] <= 1 and r["turnover"] < 18 and r["role"] not in ("补涨/跟风", "跟风", "中军")
    ]
    pioneers = [
        r for r in ranked
        if r["role"] == "先锋/日内龙" and r["open_times"] == 0 and r["turnover"] < 16
    ]
    avoid = [
        r for r in ranked
        if r["role"] in ("补涨/跟风", "跟风", "中军", "题材未成群") or (r["open_times"] >= 5 and r["boards"] < max_board)
    ]

    if phase in ("diverge", "ebb"):
        stance = "空仓优先。今天最多盯名单，不打补涨，不追反复开板的高位票。"
        primary = (clean_high[:2] or dragons[:1])[:3]
    elif phase == "climax":
        stance = "只做最强。买不起空间龙就空，不要用后排代替。"
        primary = [r for r in dragons if not r["diverge"]][:2] or clean_high[:2]
    elif phase == "ice":
        stance = "认先锋首板，等它能不能晋级。不要提前铺一篮子。"
        primary = (pioneers[:2] + dragons)[:3]
    else:
        stance = "确认谁能晋级成龙。二板质量优于首板数量。"
        primary = (clean_high[:3] or pioneers[:3])

    primary_codes = {r["code"] for r in primary}
    watch = [r for r in ranked if r["code"] not in primary_codes and r["role"] in ("题材龙", "先锋/日内龙", "卡位", "孤立高标")][:8]
    avoid = [r for r in avoid if r["code"] not in primary_codes][:8]

    return {
        "stance": stance,
        "primary": primary[:3],
        "watch": watch,
        "avoid": avoid,
    }


def relabel_cached(payload: dict) -> dict:
    zt_rows = payload.get("limit_up") or []
    if not zt_rows:
        return payload
    if not zt_rows[0].get("boards_em"):
        attach_concept_boards(zt_rows, fallback={})
    else:
        attach_zt_counts(zt_rows)
    max_board = payload.get("max_board") or max((r["boards"] for r in zt_rows), default=0)
    phase = payload.get("phase") or "diverge"
    by_board: dict[int, list] = defaultdict(list)
    for r in zt_rows:
        by_board[r["boards"]].append(r)
    themes = assign_theme_roles(zt_rows, max_board)
    ranked = []
    for r in zt_rows:
        r["diverge"] = r["turnover"] >= 20 or r["open_times"] >= 3
        r["action"] = suggest_action(r, max_board)
        score = r["boards"] * 20
        if r["open_times"] == 0:
            score += 8
        score -= min(r["open_times"], 8) * 2
        if r["diverge"] and r["boards"] < max_board:
            score -= 8
        if r["role"] in ("题材龙", "先锋/日内龙", "卡位", "孤立高标"):
            score += 6
        if r["role"] in ("补涨/跟风", "跟风"):
            score -= 10
        if r["role"] in ("题材未成群", "中军"):
            score -= 4
        score += max(0, (110000 - r["first_seal_raw"]) / 15000)
        if r["float_mv_yi"] > 400:
            score -= 4
        r["score"] = round(score, 1)
        r["reasons"] = explain_stock(r, max_board, phase)
        ranked.append(r)
    ranked.sort(key=lambda x: (-x["score"], x["first_seal_raw"]))
    picks = build_picks(ranked, phase, max_board)
    primary_codes = {r["code"] for r in picks["primary"]}
    for r in zt_rows:
        r["verdict"] = verdict_of(r, phase, r["code"] in primary_codes)
    ladder = []
    for h in sorted(by_board.keys(), reverse=True):
        ladder.append({
            "boards": h,
            "stocks": [
                {
                    "code": x["code"],
                    "name": x["name"],
                    "role": x["role"],
                    "verdict": x["verdict"],
                    "open_times": x["open_times"],
                    "turnover": x["turnover"],
                    "industry": x.get("theme") or x["industry"],
                    "theme": x.get("theme") or "",
                    "vane": x.get("vane") or "",
                }
                for x in sorted(by_board[h], key=lambda z: z["first_seal_raw"])
            ],
        })
    payload["themes"] = themes[:12]
    payload["hot_industries"] = [{"name": n, "count": c} for n, c in Counter(r.get("theme") or r["industry"] for r in zt_rows).most_common(12)]
    payload["limit_up"] = zt_rows
    payload["ranked"] = ranked[:25]
    payload["picks"] = picks
    payload["ladder"] = ladder
    src = payload.get("data_source") or {}
    src["theme"] = "东方财富个股所属板块 slist，按东财盘口拆成行业/地区/概念。主题材只用概念里今天涨停扎堆、盘子不太大的硬标签，不用基础化工这种一级行业去并群。"
    src["limit"] = "同一只票会挂十几个概念。深股通、央国企改革只展示，不参与成群。西部大开发等弱标签降权。"
    payload["data_source"] = src
    payload["rules"] = [
        "高度：先看今天最高几板，最高板才有资格当空间龙。",
        "质量：未开板、换手不太大，比反复开板干净。",
        "身份：跟风/补涨的风向标是该题材里最高、最早封的那只，不是全市场最高板，也不是市值最大的中军。",
        "成群：按东财概念并群，至少 3 只且板块不能太大。一级行业、深股通、地域政策不当主线。",
        "情绪：昨日涨停今天晋级不到 25%，按分歧/退潮处理，默认空仓。",
        "开盘前：只验证昨日连板的竞价，不在竞价里买补涨。",
        "开盘后：看天梯谁先封、谁炸板。买不起龙就空，不降标准。",
    ]
    return payload


def main() -> None:
    data = fetch_today()
    store.atomic_write_json(ROOT / "today.json", data)
    print(json.dumps({
        "date": data["date"],
        "phase": data["phase_name"],
        "zt": data["zt_count"],
        "max": data["max_board"],
        "picks": [f"{x['boards']} {x['code']} {x['name']} {x['role']}" for x in data["picks"]["primary"]],
        "yest_rate": data.get("yesterday", {}).get("rate"),
        "tomorrow": data.get("tomorrow", {}).get("plan"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
