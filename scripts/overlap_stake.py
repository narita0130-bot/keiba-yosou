#!/usr/bin/env python3
"""非馬の◎を Logic も注目馬に挙げたレースだけ、買い目の金額を引き上げる（2026-10-29 ユーザー指示）。

  python3 scripts/overlap_stake.py --ev data/<日付>.all.ev.json --logic data/<日付>.logic.json \
      [--logic data/<日付>.logic_gensen.json] --in data/<日付>.all.bets.csv [--amount 200]

- 対象は「非馬◎の馬番が Logic の注目馬（無料note・厳選のどちらでも）に入っているレース」
- そのレースの買い目すべてを --amount 円（既定200円）にする。他のレースは元のまま
- 同じファイルを上書きする。bets.csv（amount列）と autofill.csv（金額列）のどちらにも使える
- どのレースを引き上げたかを表示する
"""
import argparse
import csv
import json


def overlap_races(ev_path, logic_paths):
    picks = {}
    for p in logic_paths:
        for r in json.load(open(p))["races"]:
            picks.setdefault(r["race_id"], set()).update(int(h["umaban"]) for h in r["horses"])
    out = {}
    for r in json.load(open(ev_path))["races"]:
        hon = [int(u) for u, k in r["marks"].items() if k == "◎"]
        if len(hon) == 1 and hon[0] in picks.get(r["race_id"], set()):
            out[r["race_id"]] = hon[0]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ev", required=True)
    ap.add_argument("--logic", action="append", default=[])
    ap.add_argument("--in", dest="path", action="append", required=True)
    ap.add_argument("--amount", type=int, default=200)
    args = ap.parse_args()

    target = overlap_races(args.ev, args.logic)
    for path in args.path:
        rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
        if not rows:
            continue
        cols = list(rows[0].keys())
        amt_col = "amount" if "amount" in cols else "金額"
        changed = 0
        for r in rows:
            rid = r.get("race_id")
            if rid is None:      # autofill.csv は race_id を持たないので場名＋Rで照合する
                rid = next((t for t in target if r.get("レース") == str(int(t[10:12]))
                            and r.get("競馬場", "").startswith(_venue(t))), None)
            if rid in target:
                r[amt_col] = str(args.amount)
                changed += 1
        w = csv.DictWriter(open(path, "w", encoding="utf-8-sig", newline=""), fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
        total = sum(int(r[amt_col]) for r in rows)
        print(f"{path}: {changed}点を{args.amount}円に（合計 {len(rows)}点・{total:,}円）")
    for rid, u in sorted(target.items()):
        print(f"  引き上げ対象 {_venue(rid)}{int(rid[10:12])}R：非馬◎{u}をLogicも指名")


def _venue(rid):
    from fetch_odds import JYO
    return JYO.get(rid[4:6], rid[4:6])


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
