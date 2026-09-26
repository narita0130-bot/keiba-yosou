#!/usr/bin/env python3
"""印（ev.json の marks）から買い目定義（orders.json）を機械的に組む。

非馬のテンプレート。本人の想定馬券が note にある場合は対象外で、手で書く。

  馬連  : ◎軸流し、相手 = ◯▲△          （☆は入れない）
  馬単  : ◎1着固定流し、相手 = ◯▲△☆    （☆も入れる）
  3連複 : ◎1軸流し、相手 = ◯▲△☆ 全員    （C(n,2) 全点。☆同士のペアも残す）

☆を馬連から外し、馬単には入れるのは note 本文の記述どおり。
「☆は基本的に3連系用でつけています。(本命馬からの馬単の相手には流す可能性あり)」
8/1 に当たったのは、まさにこの 馬単◎→☆ だった（docs/handoff.md の8/1勝因分析）。
△にはそうした断りがないので ▲ と同格に扱う。

3連複を ▲の有無で分岐させない。相手集合は印そのもので決まり、
別の印（▲）が付いているかどうかで ☆ の格が変わる理由がないため。
実運用でも 9/5 札幌10R・中山9R は ☆同士のペアを含む C(n,2) で出している。

  python3 scripts/build_orders.py --ev data/2026-09-06.ev.json --out data/2026-09-06.orders.json
"""
import argparse
import json

UMAREN_PARTNERS = ("◯", "▲", "△")           # 馬連の相手（☆は入れない）
UMATAN_PARTNERS = ("◯", "▲", "△", "☆")      # 馬単の相手（◎からの流しなら☆も可）
FUKU_PARTNERS = ("◯", "▲", "△", "☆")        # 3連複の相手


def partners(marks, allowed):
    """印の強い順に相手の馬番を並べる。"""
    return [int(n) for mk in allowed for n, m in marks.items() if m == mk]


def build_race(marks):
    axis = [int(n) for n, m in marks.items() if m == "◎"]
    if not axis:
        return []                                    # ◎非公開 → 組めない
    o = axis[0]
    ren = partners(marks, UMAREN_PARTNERS)
    tan = partners(marks, UMATAN_PARTNERS)
    fuku = partners(marks, FUKU_PARTNERS)
    orders = []
    if ren:
        orders.append({"kind": "馬連", "method": "nagashi", "axis": [o],
                       "partners": ren, "source": "ref"})
    if tan:
        orders.append({"kind": "馬単", "method": "nagashi_1st", "axis": [o],
                       "partners": tan, "source": "ref"})
    if len(fuku) >= 2:
        orders.append({"kind": "3連複", "method": "nagashi", "axis": [o],
                       "partners": fuku, "source": "ref"})
    return orders


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ev", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--amount", type=int, default=100)
    args = ap.parse_args()

    spec = json.load(open(args.ev, encoding="utf-8"))
    races, skipped = [], []
    for r in spec["races"]:
        orders = build_race(r["marks"])
        if orders:
            races.append({"race_id": r["race_id"], "orders": orders})
        else:
            skipped.append(r["race_id"])

    out = {"date": spec["date"], "source": spec.get("source", ""),
           "default_amount": args.amount, "races": races}
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"wrote {args.out}  {len(races)}レース")
    if skipped:
        print("◎なしで組めず: " + ", ".join(skipped))


if __name__ == "__main__":
    main()
