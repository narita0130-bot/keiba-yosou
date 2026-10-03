#!/usr/bin/env python3
"""過去レースをまとめて取り込み、モデル学習用のCSVに貯める。

**オッズから確率を作るのをやめる**のが目的（docs/handoff.md §17, §20）。
今のエンジンは単勝オッズを基礎能力に使い γ を市場に合わせているので、
構造上、市場のコピーにしかならない。独立した確率を作るには素材が要る。

  python3 scripts/collect_races.py --from 2025-01-01 --to 2025-12-31

出力: data/races/YYYY-MM.csv（月ごと）。**再開可能** — 既に入っている
race_id は取りに行かない。netkeibaは叩きすぎると400を返すので、
途中で止まっても同じコマンドを流し直せば続きから埋まる。
"""
import argparse
import csv
import glob
import os
import re
import sys
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch_odds import _get                    # noqa: E402
from kaisai_days import kaisai_days            # noqa: E402
from race_data import COLS, race_rows          # noqa: E402

OUTDIR = "data/races"


def race_ids(day):
    d = day.replace("-", "")
    html = _get(f"https://race.netkeiba.com/top/race_list_sub.html?kaisai_date={d}").decode("utf-8", "replace")
    return sorted(set(re.findall(r"race_id=(\d{12})", html)))


def existing():
    seen = set()
    for f in glob.glob(f"{OUTDIR}/*.csv"):
        with open(f, encoding="utf-8-sig") as fh:
            seen |= {r["race_id"] for r in csv.DictReader(fh)}
    return seen


def append(month, rows):
    os.makedirs(OUTDIR, exist_ok=True)
    p = f"{OUTDIR}/{month}.csv"
    new = not os.path.exists(p)
    with open(p, "a", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        if new:
            w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", required=True)
    ap.add_argument("--to", dest="end", required=True)
    ap.add_argument("--sleep", type=float, default=0.5)
    args = ap.parse_args()

    s, e = date.fromisoformat(args.start), date.fromisoformat(args.end)
    days, y, m = [], s.year, s.month
    while (y, m) <= (e.year, e.month):
        days += [d for d in kaisai_days(y, m) if args.start <= d <= args.end]
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        time.sleep(0.4)
    days.sort()

    seen = existing()
    print(f"{args.start}〜{args.end}: 開催{len(days)}日 / 取得済み {len(seen):,}レース", flush=True)

    got = skipped = failed = 0
    for day in days:
        try:
            ids = race_ids(day)
        except SystemExit as ex:
            print(f"  {day}: レース一覧が取れず ({ex})", flush=True)
            continue
        todo = [r for r in ids if r not in seen]
        if not todo:
            skipped += len(ids)
            continue
        buf = []
        for rid in todo:
            try:
                rows = race_rows(rid)
            except SystemExit:
                failed += 1
                continue
            if not rows:
                failed += 1
                continue
            for r in rows:
                r["date"] = day
            buf += rows
            seen.add(rid)
            got += 1
            time.sleep(args.sleep)
        if buf:
            append(day[:7], buf)
        print(f"  {day}: +{len(todo)}レース（累計 取得{got} / 既存{skipped} / 失敗{failed}）", flush=True)
    print(f"完了: 取得{got} / 既存スキップ{skipped} / 失敗{failed}", flush=True)


if __name__ == "__main__":
    main()
