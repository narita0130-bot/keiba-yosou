#!/usr/bin/env python3
"""経理部: 投資記録（data/*.bets.json）を集計して週次サマリーを表示する。

  python3 scripts/weekly.py

  data/YYYY-MM-DD.bets.json の全ファイルを走査し、
  日付・レース数・買い目点数・投資合計を集計する。
  金額が設定されていない点は投資0円として扱う。
"""
import glob
import json
import os
import sys
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BET_TYPE_ORDER = ["馬連", "馬単", "3連複", "3連単", "ワイド", "複勝"]


def load_bets(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print(f"⚠️  読み込み失敗 {path}: {e}", file=sys.stderr)
        return None


def summarize_day(spec):
    races = spec.get("races", [])
    day_bets = 0
    day_invest = 0
    rows = []
    for r in races:
        label = r.get("label") or r.get("race_id", "?")
        bets = r.get("bets", [])
        amt = sum(b[2] for b in bets if len(b) > 2)
        type_counts = {}
        for b in bets:
            type_counts[b[0]] = type_counts.get(b[0], 0) + 1
        type_str = " ".join(
            f"{t}×{type_counts[t]}"
            for t in BET_TYPE_ORDER if t in type_counts
        )
        other = {t for t in type_counts if t not in BET_TYPE_ORDER}
        if other:
            type_str += " " + " ".join(f"{t}×{type_counts[t]}" for t in other)
        rows.append((label, len(bets), amt, type_str))
        day_bets += len(bets)
        day_invest += amt
    return day_bets, day_invest, rows


def main():
    data_dir = os.path.join(REPO_ROOT, "data")
    bets_files = sorted(glob.glob(os.path.join(data_dir, "*.bets.json")))

    print(f"\n=== 経理部 集計 ── {datetime.now(JST).strftime('%Y-%m-%d %H:%M JST')} ===\n")

    if not bets_files:
        print("⚠️  data/*.bets.json が見つかりません")
        print("   bets.json は非馬の型に従って買い目を確定したあとに作成します")
        return

    total_days = 0
    total_bets = 0
    total_invest = 0
    has_amount = False

    for path in bets_files:
        spec = load_bets(path)
        if spec is None:
            continue

        date = spec.get("date", os.path.basename(path).replace(".bets.json", ""))
        source = spec.get("source", "")
        status = spec.get("status", "")
        day_bets, day_invest, rows = summarize_day(spec)

        if day_invest > 0:
            has_amount = True

        invest_str = f"{day_invest:,}円" if day_invest > 0 else "金額未設定"
        print(f"📅 {date}  {len(rows)}レース  {day_bets}点  投資: {invest_str}")
        if source:
            print(f"   出典: {source}")
        if status:
            print(f"   状態: {status}")
        for label, cnt, amt, type_str in rows:
            amt_str = f"  {amt:,}円" if amt > 0 else ""
            print(f"   ・{label}  {cnt}点 ({type_str}){amt_str}")

        total_days += 1
        total_bets += day_bets
        total_invest += day_invest
        print()

    print("─" * 60)
    invest_total = f"総投資 {total_invest:,}円" if has_amount else "金額は未設定"
    print(f"【累計】{total_days}日  {total_bets}点  {invest_total}")

    if not has_amount:
        print("\n💡 金額を記録するには bets.json の各買い目を")
        print('   ["馬連", [3, 8]] → ["馬連", [3, 8], 1200] のように3要素にします')

    print(f"\n💡 払戻・収支は docs/handoff.md §6「実績記録」に記録してください")


if __name__ == "__main__":
    main()
