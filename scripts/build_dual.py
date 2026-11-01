#!/usr/bin/env python3
"""「両◎軸版」の買い目定義を作る（2026-11-01 事前登録、docs/prereg_dual_axis.md）。

  3連複のみ。軸 = 非馬の◎ と Logic の◎（印つきの厳選・最終結論がある場合だけ）、
  相手 = 非馬の印の馬 と Logic の指名馬（無料noteの注目馬も含む）の和集合。
  軸ごとに「軸 + 残りから2頭」を全部組み、重複は1点にまとめる。各100円。
  Logic の指名が1頭も無いレースは対象外（テンプレートの3連複と変わらないため）。
  トリガミ除外：そのレースの点数×100円より払戻が少ない組（オッズ < 点数）を外す。
  外すと点数が減るので、残りがすべて条件を満たすまで繰り返す。オッズは作成時点の値。

  python3 scripts/build_dual.py --ev data/2026-11-08.all.ev.json \
      --logic data/2026-11-08.logic.json [--logic data/2026-11-08.logic_gensen.json] \
      --out data/2026-11-08.dual.orders.json
"""
import argparse
import itertools
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_odds import odds_api   # noqa: E402


def logic_marks(paths):
    out = {}
    for p in paths:
        for r in json.load(open(p))["races"]:
            for h in r["horses"]:
                if h.get("umaban"):
                    out.setdefault(r["race_id"], {})[int(h["umaban"])] = h.get("mark", "L")
    return out


def odds_of(table, combo):
    v = table.get("".join(f"{x:02d}" for x in sorted(combo)))
    if not v or v[0] in ("", "0.0"):
        return None
    return float(v[0].replace(",", ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ev", required=True)
    ap.add_argument("--logic", action="append", default=[])
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    ev = json.load(open(args.ev))
    lg = logic_marks(args.logic)
    races = []
    for r in ev["races"]:
        m = {int(u): k for u, k in r["marks"].items()}
        hon = [u for u, k in m.items() if k == "◎"]
        L = lg.get(r["race_id"], {})
        if len(hon) != 1 or not L:
            continue
        axes = {hon[0]} | {u for u, k in L.items() if k == "◎"}
        union = set(m) | set(L)
        combos = sorted({tuple(sorted((a, x, y))) for a in axes
                         for x, y in itertools.combinations(sorted(union - {a}), 2)})
        table = odds_api(r["race_id"], "7")["odds"]["7"]
        time.sleep(0.5)
        unknown = [c for c in combos if odds_of(table, c) is None]
        while True:
            bad = [c for c in combos if c not in unknown and odds_of(table, c) < len(combos)]
            if not bad:
                break
            combos = [c for c in combos if c not in bad]
        races.append({"race_id": r["race_id"],
                      "orders": [{"kind": "3連複", "method": "normal", "combo": list(c), "source": "dual"}
                                 for c in combos]})
        lo = min((odds_of(table, c) for c in combos if c not in unknown), default=None)
        print(f"{r['race_id']} 軸{sorted(axes)} 相手{sorted(union)} → {len(combos)}点"
              f"（最低 {lo}倍{'、オッズ不明 ' + str(unknown) if unknown else ''}）")
    json.dump({"date": ev["date"], "default_amount": 100, "races": races},
              open(args.out, "w"), ensure_ascii=False, indent=1)
    print(f"wrote {args.out}  {len(races)}レース {sum(len(x['orders']) for x in races)}点")


if __name__ == "__main__":
    main()
