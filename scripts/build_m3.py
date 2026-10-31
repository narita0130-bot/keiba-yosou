#!/usr/bin/env python3
"""「◎◯3点版」の買い目定義を作る（2026-10-25 事前登録、docs/prereg_hiuma_3pt.md）。

  馬連 ◎-◯ ／ 馬単 ◎→◯ ／ 3連複 ◎◯▲（▲がいなければ3連複なし）
  ◎が1頭でない・◯がいないレースは対象外。各100円。

  python3 scripts/build_m3.py --ev data/2026-10-25.all.ev.json --out data/2026-10-25.m3.orders.json
"""
import argparse
import json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ev", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    ev = json.load(open(args.ev))
    races = []
    for r in ev["races"]:
        m = r["marks"]
        hon = [int(u) for u, k in m.items() if k == "◎"]
        tai = [int(u) for u, k in m.items() if k == "◯"]
        tan = [int(u) for u, k in m.items() if k == "▲"]
        if len(hon) != 1 or not tai:
            continue
        o, t = hon[0], tai[0]
        orders = [{"kind": "馬連", "method": "normal", "combo": [o, t], "source": "m3"},
                  {"kind": "馬単", "method": "normal", "combo": [o, t], "source": "m3"}]
        if tan:
            orders.append({"kind": "3連複", "method": "normal", "combo": sorted([o, t, tan[0]]), "source": "m3"})
        races.append({"race_id": r["race_id"], "orders": orders})
    json.dump({"date": ev["date"], "default_amount": 100, "races": races},
              open(args.out, "w"), ensure_ascii=False, indent=1)
    print(f"wrote {args.out}  {len(races)}レース {sum(len(x['orders']) for x in races)}点")


if __name__ == "__main__":
    main()
