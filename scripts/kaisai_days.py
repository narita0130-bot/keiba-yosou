#!/usr/bin/env python3
"""JRAの開催日を列挙し、手元に集めた予想記事に抜けが無いかを突き合わせる。

過去分をさかのぼって集めるとき、**集めた記事が「その期間の全部」であることが
検証の前提**になる。都合の悪い日が抜けていれば、回収率はいくらでも良く見える。

  python3 scripts/kaisai_days.py --from 2026-07-01 --to 2026-09-19
  python3 scripts/kaisai_days.py --from 2026-07-01 --to 2026-09-19 --have "data/*.logic.txt"

--have を渡すと、ファイル名の日付と開催日を突き合わせて欠けている日を出す。
"""
import argparse
import glob
import re
import os
import sys
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch_odds import _get   # noqa: E402


def kaisai_days(y, m):
    html = _get(f"https://race.netkeiba.com/top/calendar.html?year={y}&month={m}").decode("utf-8", "replace")
    return sorted({f"{d[:4]}-{d[4:6]}-{d[6:]}" for d in re.findall(r"kaisai_date=(\d{8})", html)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", required=True)
    ap.add_argument("--to", dest="end", required=True)
    ap.add_argument("--have", help='集めた記事のglob（例 "data/*.logic.txt"）')
    args = ap.parse_args()

    s, e = date.fromisoformat(args.start), date.fromisoformat(args.end)
    days, y, m = [], s.year, s.month
    while (y, m) <= (e.year, e.month):
        days += [d for d in kaisai_days(y, m) if args.start <= d <= args.end]
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        time.sleep(0.4)
    days.sort()

    print(f"{args.start} 〜 {args.end} の JRA開催日: {len(days)}日")
    if not args.have:
        print("  " + " ".join(days))
        return

    have = set()
    for f in glob.glob(args.have):
        mm = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(f))
        if mm:
            have.add(mm.group(1))
    missing = [d for d in days if d not in have]
    extra = sorted(have - set(days))
    print(f"  手元にある: {len(days)-len(missing)}日 / 欠け: {len(missing)}日")
    if missing:
        print("  欠けている日:")
        for d in missing:
            print(f"    {d}")
        print("\n  ※ 欠けがあるまま回収率を出さないこと。"
              "都合の悪い日が抜けているだけで数字は簡単に良く見える。")
    if extra:
        print(f"  開催日でないのに手元にある: {extra}")


if __name__ == "__main__":
    main()
