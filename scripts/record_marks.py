#!/usr/bin/env python3
"""非馬の印が実際に何着だったかを、人気とセットで蓄積する。

うちのEVエンジンは確率を単勝オッズから作っているため、独立した確率推定を持っていない
（docs/handoff.md §17）。それを作る材料がこの記録。印ごとの勝率・2着内率・3着内率を、
**人気帯で層別して**測れるようにする。人気の補正なしに印別成績を比べても、
非馬が◎に人気薄を置く傾向があるぶん見かけの差が出てしまう。

  python3 scripts/record_marks.py --ev data/2026-09-13.ev.json

data/marks_record.csv に追記する（race_id + umaban で重複排除するので何度流してもよい）。
"""
import argparse
import csv
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch_odds import JYO           # noqa: E402
from fetch_result import race_result  # noqa: E402

COLS = ["date", "race_id", "venue", "race_no", "stars", "umaban", "mark",
        "horse", "chaku", "ninki", "odds", "field_size", "scratched"]
DEFAULT_OUT = "data/marks_record.csv"


def rows_for(spec, date):
    out = []
    for r in spec["races"]:
        marks = r.get("marks") or {}
        if not marks:
            continue
        rid = r["race_id"]
        try:
            res = race_result(rid)
        except SystemExit as e:
            print(f"  {rid}: 取得できず（{e}）")
            continue
        if not res["finished"]:
            print(f"  {rid}: 未確定のため記録しない")
            continue
        scratched = {h["umaban"]: h for h in res.get("scratched", [])}
        pos = {h["umaban"]: h for h in res["order"]}
        size = len(res["order"]) + len(scratched)
        for n, mk in marks.items():
            n = int(n)
            h = pos.get(n)
            out.append({
                "date": date, "race_id": rid,
                "venue": JYO.get(rid[4:6], ""), "race_no": int(rid[10:12]),
                "stars": r.get("stars", ""), "umaban": n, "mark": mk,
                "horse": (h or scratched.get(n, {})).get("name", ""),
                "chaku": h["chaku"] if h else "",
                "ninki": (h or {}).get("ninki") or "",
                "odds": (h or {}).get("odds") or "",
                "field_size": size,
                "scratched": "1" if n in scratched else "",
            })
        time.sleep(0.3)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ev", required=True, nargs="+", help="ev.json（複数可）")
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    existing, seen = [], set()
    if os.path.exists(args.out):
        with open(args.out, encoding="utf-8-sig") as fh:
            existing = list(csv.DictReader(fh))
        seen = {(r["race_id"], r["umaban"]) for r in existing}

    added = 0
    for f in args.ev:
        spec = json.load(open(f, encoding="utf-8"))
        # 古い sheet.json には date が無いのでファイル名から拾う
        m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(f))
        date = spec.get("date") or (m.group(1) if m else "")
        for row in rows_for(spec, date):
            if (row["race_id"], str(row["umaban"])) in seen:
                continue
            existing.append(row); seen.add((row["race_id"], str(row["umaban"]))); added += 1

    existing.sort(key=lambda r: (r["date"], r["race_id"], int(r["umaban"])))
    with open(args.out, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader(); w.writerows(existing)
    races = len({r["race_id"] for r in existing})
    print(f"wrote {args.out}  {len(existing)}頭 / {races}レース（今回 +{added}頭）")


if __name__ == "__main__":
    main()
