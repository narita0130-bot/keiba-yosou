#!/usr/bin/env python3
"""買い目CSVとレース結果を突き合わせて収支を出す。

build_bets_csv.py が出したCSV（1行1点）に対し、netkeiba の確定払戻を引いて
的中判定・払戻・回収率を集計する。EV判定（buy/apparent/pass）ごとの回収率も出すので、
エンジンの判定が実際に機能しているかを検証できる。

  python3 scripts/settle.py --bets data/2026-09-05.bets.csv --out data/2026-09-05.settle.csv

--out を省略すると集計だけ表示する。
"""
import argparse
import csv
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch_odds import JYO                      # noqa: E402
from fetch_result import ORDERED, race_result   # noqa: E402

JUDGE_LABEL = {"buy": "🟢買い", "apparent": "🟡見かけ", "pass": "❌見送り", "": "（判定なし）"}


def combo_nums(combo):
    return [int(x) for x in combo.replace(">", "-").split("-") if x.strip()]


def combo_key(bet_type, combo):
    """CSVの combo（"05-09-14" / "08>05>03"）を払戻辞書のキーに合わせる。"""
    nums = combo_nums(combo)
    seq = nums if bet_type in ORDERED else sorted(nums)
    return "".join(f"{n:02d}" for n in seq)


def money(n):
    return f"{n:,}円"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bets", required=True, help="build_bets_csv.py が出した買い目CSV")
    ap.add_argument("--out", help="明細CSVの出力先")
    args = ap.parse_args()

    with open(args.bets, encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise SystemExit("買い目CSVが空です")

    # レースごとに結果を1回だけ取る
    results, pending = {}, []
    for rid in dict.fromkeys(r["race_id"] for r in rows):
        try:
            res = race_result(rid)
        except SystemExit as e:
            res = {"finished": False, "payouts": {}, "order": [], "error": str(e)}
        results[rid] = res
        if not res["finished"]:
            pending.append(rid)
        time.sleep(0.4)

    out_rows = []
    for r in rows:
        rid, kind = r["race_id"], r["bet_type"]
        amount = int(r["amount"] or 0)
        res = results.get(rid, {})
        payouts = res.get("payouts", {}).get(kind, {})
        # 除外・取消の馬を1頭でも含む買い目は全額返還。的中判定にも集計にも入れない。
        scratched = {h["umaban"] for h in res.get("scratched", [])}
        void = scratched & set(combo_nums(r["combo"]))
        hit = None if void else payouts.get(combo_key(kind, r["combo"]))
        # 払戻は100円あたりの金額。購入額に比例させる。
        ret = int(hit["yen"] * amount / 100) if hit else 0
        out_rows.append({**r,
                         "finished": "1" if res.get("finished") else "",
                         "refunded": ",".join(str(n) for n in sorted(void)) if void else "",
                         "hit": "1" if hit else "",
                         "payout_yen": hit["yen"] if hit else "",
                         "payout_ninki": hit.get("ninki") if hit else "",
                         "return": ret,
                         "profit": 0 if void else ret - amount})

    settled = [r for r in out_rows if r["finished"] and not r["refunded"]]
    refunds = [r for r in out_rows if r["refunded"]]
    inv = sum(int(r["amount"]) for r in settled)
    ret = sum(r["return"] for r in settled)
    hits = [r for r in settled if r["hit"]]

    print(f"\n{'='*70}")
    pend = len([r for r in out_rows if not r["finished"]])
    print(f"【総収支】確定 {len(settled)}点 / 返還 {len(refunds)}点 / 未確定 {pend}点")
    if inv:
        print(f"  投資 {money(inv)}  払戻 {money(ret)}  収支 {ret-inv:+,}円  回収率 {ret/inv*100:.1f}%")
        print(f"  的中 {len(hits)}点 / {len(settled)}点（的中率 {len(hits)/len(settled)*100:.1f}%）")

    if refunds:
        print(f"\n【返還】{len(refunds)}点 {money(sum(int(r['amount']) for r in refunds))}"
              f"（除外・取消の馬を含むため投資から除外）")
        for r in refunds:
            print(f"  {r['venue']}{r['race_no']}R  {r['bet_type']:<6}{r['combo']:<12}"
                  f"除外馬 {r['refunded']}番")

    if hits:
        print(f"\n【的中した買い目】")
        for r in sorted(hits, key=lambda x: -x["return"]):
            label = f"{r['venue']}{r['race_no']}R"
            print(f"  {label:<8}{r['bet_type']:<6}{r['combo']:<12}"
                  f"{r['payout_yen']:>8,}円  払戻{r['return']:>7,}円  {JUDGE_LABEL.get(r['judge'],'')}")

    # ここが本題。エンジンの判定が実際に機能しているかを見る。
    by = defaultdict(lambda: {"n": 0, "inv": 0, "ret": 0, "hit": 0})
    for r in settled:
        b = by[r["judge"]]
        b["n"] += 1; b["inv"] += int(r["amount"]); b["ret"] += r["return"]
        b["hit"] += 1 if r["hit"] else 0
    print(f"\n【EV判定別の実績】")
    print(f"  {'判定':<12}{'点数':>5}{'投資':>10}{'払戻':>10}{'回収率':>9}{'的中':>6}")
    for judge in ("buy", "apparent", "pass", ""):
        b = by.get(judge)
        if not b or not b["n"]:
            continue
        rate = f"{b['ret']/b['inv']*100:.1f}%" if b["inv"] else "-"
        print(f"  {JUDGE_LABEL[judge]:<12}{b['n']:>5}{b['inv']:>9,}円{b['ret']:>9,}円{rate:>9}{b['hit']:>6}")

    if pending:
        print(f"\n未確定のレース: " + ", ".join(
            f"{JYO.get(p[4:6],'')}{int(p[10:12])}R" for p in pending))

    if args.out:
        cols = list(rows[0].keys()) + ["finished", "refunded", "hit", "payout_yen",
                                       "payout_ninki", "return", "profit"]
        with open(args.out, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(out_rows)
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    sys.exit(main())
