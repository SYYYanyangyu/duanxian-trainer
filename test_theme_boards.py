# -*- coding: utf-8 -*-
import fetch_today as f


def test_decorate_eastmoney_layout():
    rows = [
        {"bk": "BK1439", "name": "膜材料", "up": 6, "pct": -0.82},
        {"bk": "BK1206", "name": "基础化工", "up": 180, "pct": -0.17},
        {"bk": "BK0454", "name": "塑料", "up": 29, "pct": -0.4},
        {"bk": "BK0173", "name": "贵州板块", "up": 15, "pct": 0.12},
        {"bk": "BK1068", "name": "净水概念", "up": 13, "pct": 0.74},
        {"bk": "BK0804", "name": "深股通", "up": 802, "pct": -0.04},
        {"bk": "BK0590", "name": "西部大开发", "up": 257, "pct": -0.03},
        {"bk": "BK0494", "name": "节能环保", "up": 170, "pct": -0.1},
    ]
    kinds = {
        "BK1439": "industry",
        "BK1206": "industry",
        "BK0454": "industry",
        "BK0173": "region",
        "BK1068": "concept",
        "BK0804": "concept",
        "BK0590": "concept",
        "BK0494": "concept",
    }
    out = f.decorate_boards(rows, kinds)
    by_name = {b["name"]: b for b in out}
    assert by_name["基础化工"]["level"] == "industry_l1"
    assert by_name["塑料"]["level"] == "industry_l2"
    assert by_name["膜材料"]["level"] == "industry_l3"
    assert by_name["贵州板块"]["kind"] == "region"
    assert by_name["净水概念"]["kind"] == "concept"
    assert by_name["深股通"]["kind"] == "noise"

    stock = {"industry": "塑料", "boards_em": out}
    assign = f.assignable_concepts(stock)
    assert "基础化工" not in assign
    assert "塑料" not in assign
    assert "净水概念" in assign
    assert "深股通" not in assign
    assert "西部大开发" not in assign


def test_loose_theme_not_cluster():
    members = [{"boards": 1, "boards_em": [{"name": "节能环保", "up": 170}]}] * 3
    assert f.is_loose_theme("节能环保", members, 47) is True
    tight = [{"boards": 1, "boards_em": [{"name": "净水概念", "up": 13}]}] * 3
    assert f.is_loose_theme("净水概念", tight, 47) is False


if __name__ == "__main__":
    test_decorate_eastmoney_layout()
    test_loose_theme_not_cluster()
    print("ALL PASS")
