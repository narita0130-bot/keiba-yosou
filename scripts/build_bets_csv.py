#!/usr/bin/env python3
"""買い目定義（data/YYYY-MM-DD.orders.json）を1行1点のCSVに展開する。

流し・フォーメーションを実際の組番まで展開し、netkeiba の最新オッズと
エンジンのEV判定を付けて出力する。自動投票ソフトの入力データや、
表計算での検証に使うことを想定している。

  python3 scripts/build_bets_csv.py --orders data/2026-09-06.orders.json \
      --ev data/2026-09-06.ev.json --out data/2026-09-06.bets.csv

--ev を省略するとEV列は空になる（オッズだけ付く）。

--format autofill を付けると Chrome拡張「JRA CSV 自動入力」が読める列構成で出す。
拡張が必須とするのは 競馬場 / レース / 式別 / 馬番1 / 金額 の5列で、
馬番は1点ぶんを馬番1〜3に分けて持つ（着順ありの式別は1着→2着→3着の順）。
競馬場には開催曜日を付ける（土日開催で同じ場が2つ並ぶと拡張が停止するため）。
オッズ・EV等の列も併記するが、拡張はヘッダ名で列を引くので無視される。

※ 2026-09-08 に再作成したもの。元ファイルはコンテナ破棄で失われた。
   列構成と展開仕様は実際の出力CSVから復元しているが、原本と1対1ではない。
"""
import argparse
import csv
import datetime
import itertools
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine"))

from fetch_odds import (JYO, TYPE_SANRENPUKU, TYPE_SANRENTAN, TYPE_TAN_FUKU,  # noqa: E402
                        TYPE_UMAREN, TYPE_UMATAN, TYPE_WIDE, odds_api, race_info)

# JRA の式別番号（投票データで一般的に使われるもの）と netkeiba API の type 番号。
# netkeiba には枠連(JRA式別3)が無いため、枠連は odds_type=None になる。
BET_SPEC = {
    "単勝":   {"jra_code": 1, "odds_type": TYPE_TAN_FUKU,   "odds_key": "1", "legs": 1, "ordered": False},
    "複勝":   {"jra_code": 2, "odds_type": TYPE_TAN_FUKU,   "odds_key": "2", "legs": 1, "ordered": False},
    "馬連":   {"jra_code": 4, "odds_type": TYPE_UMAREN,     "odds_key": None, "legs": 2, "ordered": False},
    "ワイド": {"jra_code": 5, "odds_type": TYPE_WIDE,       "odds_key": None, "legs": 2, "ordered": False},
    "馬単":   {"jra_code": 6, "odds_type": TYPE_UMATAN,     "odds_key": None, "legs": 2, "ordered": True},
    "3連複":  {"jra_code": 7, "odds_type": TYPE_SANRENPUKU, "odds_key": None, "legs": 3, "ordered": False},
    "3連単":  {"jra_code": 8, "odds_type": TYPE_SANRENTAN,  "odds_key": None, "legs": 3, "ordered": True},
}
WD = "月火水木金土日"


def to_odds(v):
    """netkeiba は 1000倍以上を "1,103.5" とカンマ区切りで返す。"""
    return float(str(v).replace(",", ""))


def expand(order):
    """1件の買い目定義を組番のリストに展開する。"""
    kind = order["kind"]
    legs = BET_SPEC[kind]["legs"]
    method = order.get("method", "normal")
    if method == "normal":
        return [tuple(order["combo"])]
    axis = list(order.get("axis", []))
    partners = [p for p in order.get("partners", []) if p not in axis]
    if method == "nagashi":                      # 着順なし・軸固定
        return [tuple(axis) + c for c in itertools.combinations(partners, legs - len(axis))]
    if method == "nagashi_1st":                  # 1着固定流し（馬単・3連単）
        return [tuple(axis) + c
                for c in itertools.permutations(partners, legs - len(axis))]
    if method == "formation":                    # 各列の候補から重複を除いて総当たり
        cols = order["columns"]
        out = []
        for c in itertools.product(*cols):
            if len(set(c)) == legs:
                out.append(tuple(c))
        seen, uniq = set(), []
        for c in out:
            k = c if BET_SPEC[kind]["ordered"] else tuple(sorted(c))
            if k not in seen:
                seen.add(k); uniq.append(c)
        return uniq
    raise ValueError(f"未知の method: {method}")


def combo_str(kind, nums):
    sep = ">" if BET_SPEC[kind]["ordered"] else "-"
    seq = nums if BET_SPEC[kind]["ordered"] else sorted(nums)
    return sep.join(f"{n:02d}" for n in seq)


def odds_key(kind, nums):
    seq = nums if BET_SPEC[kind]["ordered"] else sorted(nums)
    return "".join(f"{n:02d}" for n in seq)


def fetch_odds_map(rid, kinds):
    """レース1鞍ぶんの、必要な式別のオッズ表をまとめて取る。"""
    out, stamp = {}, ""
    for kind in kinds:
        spec = BET_SPEC[kind]
        if spec["odds_type"] is None:
            out[kind] = {}
            continue
        try:
            res = odds_api(rid, spec["odds_type"])
            stamp = res.get("official_datetime") or stamp
            key = spec["odds_key"] or str(spec["odds_type"])
            out[kind] = res["odds"].get(key, {})
        except (SystemExit, KeyError):
            out[kind] = {}
        time.sleep(0.35)
    return out, stamp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orders", required=True)
    ap.add_argument("--ev", help="印の定義。EV列を付ける場合に指定")
    ap.add_argument("--out", required=True)
    ap.add_argument("--format", choices=["standard", "autofill"], default="standard")
    args = ap.parse_args()

    spec = json.load(open(args.orders, encoding="utf-8"))
    default_amount = spec.get("default_amount", 100)
    marks_by_race = {}
    if args.ev:
        marks_by_race = {r["race_id"]: r["marks"]
                         for r in json.load(open(args.ev, encoding="utf-8"))["races"]}

    engine_cache = {}
    if marks_by_race:
        from run_ev import build_engine, judge          # noqa: E402

    rows, gid = [], 0
    for race in spec["races"]:
        rid = race["race_id"]
        info = race_info(rid)
        post = info["condition"].split("発走")[0].strip()
        d = datetime.date(int(rid[:4]), 1, 1)           # 曜日は開催日から取れないので日付から
        date_s = spec["date"]
        y, m, dd = (int(x) for x in date_s.split("-"))
        wd = WD[datetime.date(y, m, dd).weekday()]
        venue = JYO.get(rid[4:6], "")
        kinds = sorted({o["kind"] for o in race["orders"]})
        omap, stamp = fetch_odds_map(rid, kinds)

        eng = None
        if rid in marks_by_race:
            if rid not in engine_cache:
                try:
                    engine_cache[rid] = build_engine(rid, marks_by_race[rid])[1]
                except Exception:
                    engine_cache[rid] = None
            eng = engine_cache[rid]

        for order in race["orders"]:
            kind = order["kind"]
            gid += 1
            group = f"G{gid:03d}"
            combos = expand(order)
            for nums in combos:
                raw = omap.get(kind, {}).get(odds_key(kind, nums))
                odds = to_odds(raw[0]) if raw else ""
                ninki = raw[2] if raw and len(raw) > 2 else ""
                ev = lo = jd = ""
                if eng is not None and odds != "":
                    try:
                        ev = eng.ev(kind, list(nums), actual_odds=odds)[0]
                        lo = eng.ev_robust(kind, list(nums), actual_odds=odds)[0]
                        jd = {"🟢買い": "buy", "🟡見かけ": "apparent",
                              "❌見送り": "pass"}[judge(lo, ev)]
                    except Exception:
                        ev = lo = jd = ""
                rows.append({
                    "date": date_s.replace("-", ""), "race_id": rid,
                    "jyo_code": rid[4:6], "venue": venue, "race_no": int(rid[10:12]),
                    "post_time": post, "bet_type": kind,
                    "bet_type_code": BET_SPEC[kind]["jra_code"],
                    "combo": combo_str(kind, nums),
                    "amount": order.get("amount", default_amount),
                    "group_id": group, "group_method": order.get("method", "normal"),
                    "group_points": len(combos),
                    "odds": f"{odds:.1f}" if odds != "" else "",
                    "ninki": ninki,
                    "ev": f"{ev:.3f}" if ev != "" else "",
                    "ev_low": f"{lo:.3f}" if lo != "" else "",
                    "judge": jd, "source": order.get("source", ""),
                    "odds_time": stamp,
                    "_nums": (list(nums) if BET_SPEC[kind]["ordered"] else sorted(nums)),
                    "_venue_wd": f"{venue}({wd})",
                })

    rows.sort(key=lambda r: (r["post_time"], r["race_id"], r["group_id"]))

    if args.format == "autofill":
        cols = ["競馬場", "レース", "式別", "馬番1", "馬番2", "馬番3", "金額", "発走",
                "オッズ", "人気", "EV", "頑健下限", "判定", "出典", "グループ"]
        out_rows = []
        for r in rows:
            n = r["_nums"] + ["", "", ""]
            out_rows.append({"競馬場": r["_venue_wd"], "レース": r["race_no"],
                             "式別": r["bet_type"], "馬番1": n[0], "馬番2": n[1], "馬番3": n[2],
                             "金額": r["amount"], "発走": r["post_time"], "オッズ": r["odds"],
                             "人気": r["ninki"], "EV": r["ev"], "頑健下限": r["ev_low"],
                             "判定": r["judge"], "出典": r["source"], "グループ": r["group_id"]})
    else:
        cols = ["date", "race_id", "jyo_code", "venue", "race_no", "post_time", "bet_type",
                "bet_type_code", "combo", "amount", "group_id", "group_method", "group_points",
                "odds", "ninki", "ev", "ev_low", "judge", "source", "odds_time"]
        out_rows = [{c: r[c] for c in cols} for r in rows]

    with open(args.out, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(out_rows)

    total = sum(int(r["amount"]) for r in rows)
    buys = sum(1 for r in rows if r["judge"] == "buy")
    groups = len({r["group_id"] for r in rows})
    print(f"wrote {args.out}  [{args.format}]  {len(rows)}点 / {groups}操作 / "
          f"合計{total:,}円 / 🟢{buys}点")


if __name__ == "__main__":
    main()
