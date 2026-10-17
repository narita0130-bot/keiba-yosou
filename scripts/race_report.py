#!/usr/bin/env python3
"""1レース分の結果と、買い目ファイルごとの当否を出す（買わずに見るだけの日の通知用）。

  python3 scripts/race_report.py --race 202608040406 \
      --ev data/2026-10-11.all.ev.json \
      --bets 全部入り=data/2026-10-11.all.bets.csv \
      --bets 30倍以下=data/2026-10-11.pick.bets.csv \
      --state data/2026-10-11.paper.json

- 結果が未確定なら「未確定」とだけ出して終了コード 2。
- 確定していれば着順・印の着順・買い目ファイルごとの的中と払戻を出し、
  --state にレース単位で書き足して、その時点までの累計も出す。
- 最後の行 `NOTIFY:` はスマホ通知用の1行（200字以内）。
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_odds import JYO                      # noqa: E402
from fetch_result import ORDERED, race_result   # noqa: E402


def combo_nums(combo):
    return [int(x) for x in combo.replace(">", "-").split("-") if x.strip()]


def combo_key(bet_type, combo):
    nums = combo_nums(combo)
    seq = nums if bet_type in ORDERED else sorted(nums)
    return "".join(f"{n:02d}" for n in seq)


def race_label(race_id):
    return f"{JYO.get(race_id[4:6], race_id[4:6])}{int(race_id[10:12])}R"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--race", required=True)
    ap.add_argument("--ev", help="印の定義（印の着順を出す）")
    ap.add_argument("--bets", action="append", default=[], help="ラベル=買い目CSV（複数可）")
    ap.add_argument("--state", required=True, help="レースごとの結果を貯めるJSON")
    args = ap.parse_args()

    rid = args.race
    res = race_result(rid)
    if not res["finished"]:
        print(f"{race_label(rid)} 未確定")
        sys.exit(2)

    order = res["order"]
    by_uma = {h["umaban"]: h for h in order}
    scratched = {h["umaban"] for h in res.get("scratched", [])}
    top = order[:3]
    print(f"# {race_label(rid)}  {rid}")
    for h in top:
        print(f"  {h['chaku']}着 {h['umaban']:>2} {h['name']}（{h['ninki']}人気）")

    marks_line = ""
    if args.ev:
        ev = json.load(open(args.ev))
        race = next((r for r in ev["races"] if r["race_id"] == rid), None)
        if race:
            parts = []
            for u, mk in race["marks"].items():
                u = int(u)
                if u in scratched:
                    pos = "取消"
                elif u in by_uma:
                    pos = f"{by_uma[u]['chaku']}着"
                else:
                    # 確定直後の結果ページは上位数頭しか載らないことがあるので「中止」とは書かない
                    pos = "圏外"
                parts.append(f"{mk}{u}→{pos}")
            marks_line = " ".join(parts)
            print(f"  印: {marks_line}")

    state = json.load(open(args.state)) if os.path.exists(args.state) else {"races": {}}
    rec = {"top3": [[h["umaban"], h["name"], h["ninki"]] for h in top], "marks": marks_line, "books": {}}

    notify_parts = []
    for spec in args.bets:
        label, path = spec.split("=", 1)
        rows = [r for r in csv.DictReader(open(path, encoding="utf-8-sig")) if r["race_id"] == rid]
        invest = payout = refund = 0
        hits = []
        for r in rows:
            amt = int(r["amount"])
            if scratched & set(combo_nums(r["combo"])):
                refund += amt
                continue
            invest += amt
            p = res["payouts"].get(r["bet_type"], {}).get(combo_key(r["bet_type"], r["combo"]))
            if p:
                y = p["yen"] * amt // 100
                payout += y
                hits.append(f"{r['bet_type']}{r['combo']} {y:,}円")
        rec["books"][label] = {"points": len(rows), "invest": invest, "payout": payout,
                               "refund": refund, "hits": hits}
        if rows:
            body = "、".join(hits) if hits else "ハズレ"
            print(f"  [{label}] {len(rows)}点 {invest:,}円 → {payout:,}円（{payout - invest:+,}円） {body}")
            notify_parts.append(f"{label}{'的中' if hits else 'ハズレ'}{payout - invest:+,}円")
        else:
            print(f"  [{label}] 買い目なし")

    state["races"][rid] = rec
    json.dump(state, open(args.state, "w"), ensure_ascii=False, indent=1)

    totals = {}
    for r in state["races"].values():
        for label, b in r["books"].items():
            t = totals.setdefault(label, [0, 0, 0])
            if b["points"]:
                t[0] += b["invest"]
                t[1] += b["payout"]
                t[2] += 1
    print(f"  累計（{len(state['races'])}レース確定）:")
    tot_txt = []
    for label, (inv, pay, n) in totals.items():
        print(f"    {label}: {inv:,}円 → {pay:,}円（{pay - inv:+,}円）")
        tot_txt.append(f"{label}{pay - inv:+,}")

    win = top[0] if top else None
    head = f"{race_label(rid)} 1着{win['umaban']}{win['name']}({win['ninki']}人気)" if win else race_label(rid)
    msg = f"{head}｜{marks_line}｜{' '.join(notify_parts)}｜累計 {' '.join(tot_txt)}（買わず）"
    print("NOTIFY:" + msg[:200])


if __name__ == "__main__":
    main()
