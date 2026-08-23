# -*- coding: utf-8 -*-
"""非馬の印から買い目のEVを計算する（引き継ぎ資料 §2 の方式に準拠）。

  基礎能力 = 市場人気順の 50〜80 log正規化ベースライン ＋ 印加点
  他5項目（距離・コース・騎手・近走・状態）は全馬3（中立）で固定
  → 無印馬の乖離をゼロにし、「予想家に乗る」意思だけを数値に反映する

オッズは netkeiba の公開オッズを実配当として使い、EV は必ず実配当で上書きする。

  python3 engine/run_ev.py --spec data/2026-08-23.ev.json
"""
import argparse
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from keiba_engine_v2 import RaceEngine                     # noqa: E402
from fetch_odds import (JYO, TYPE_SANRENPUKU, TYPE_TAN_FUKU,  # noqa: E402
                        TYPE_UMAREN, TYPE_WIDE, odds_api, race_info)

# 引き継ぎ資料 §2 の加点表
MARK_BONUS = {"◎": 8, "◯": 5, "○": 5, "▲": 3, "△": 2, "☆": 2, "★": 2, "穴": 2}
BASE_LO, BASE_HI = 50.0, 80.0


def baseline(odds_list):
    """単勝オッズ → 50〜80 の log 正規化ベースライン（人気馬ほど高い）"""
    ln = [math.log(o) for o in odds_list]
    lo, hi = min(ln), max(ln)
    if hi - lo < 1e-9:
        return [(BASE_LO + BASE_HI) / 2] * len(ln)
    return [BASE_HI - (BASE_HI - BASE_LO) * (x - lo) / (hi - lo) for x in ln]


def build_engine(rid, marks, lam=0.25):
    info = race_info(rid)
    tan = odds_api(rid, TYPE_TAN_FUKU)["odds"]["1"]
    nums, names, odds = [], {}, []
    for h in sorted(info["rows"], key=lambda r: r["umaban"]):
        n = h["umaban"]
        o = tan.get(f"{n:02d}") or tan.get(str(n))
        if not o:
            continue
        nums.append(n); names[n] = h["name"]; odds.append(float(o[0]))
    base = baseline(odds)
    horses = []
    for n, nm_o, b in zip(nums, odds, base):
        bonus = MARK_BONUS.get(marks.get(str(n), marks.get(n, "")), 0)
        horses.append((n, names[n], nm_o, min(200.0, b + bonus), 3, 3, 3, 3, 3))
    return info, RaceEngine(horses, lam=lam), names


def real_odds(rid):
    """実配当（複勝・ワイドは下限を採る＝保守側）"""
    out = {}
    for kind, t in (("ワイド", TYPE_WIDE), ("馬連", TYPE_UMAREN), ("3連複", TYPE_SANRENPUKU)):
        try:
            out[kind] = odds_api(rid, t)["odds"][str(t)]
        except (SystemExit, KeyError):
            out[kind] = {}
        time.sleep(0.35)
    try:
        out["複勝"] = odds_api(rid, TYPE_TAN_FUKU)["odds"]["2"]
    except (SystemExit, KeyError):
        out["複勝"] = {}
    return out


def lookup(od, kind, nums):
    key = "".join(f"{n:02d}" for n in sorted(nums))
    v = od.get(kind, {}).get(key)
    if not v:
        return None
    return float(v[0])          # 複勝・ワイドは下限、馬連・3連複は確定値


def judge(lo, ev):
    if lo >= 1.0:
        return "🟢買い"
    if ev >= 1.0:
        return "🟡見かけ"
    return "❌見送り"


def run_race(spec):
    rid, marks = spec["race_id"], spec["marks"]
    info, eng, names = build_engine(rid, marks)
    od = real_odds(rid)
    label = f"{JYO.get(rid[4:6], '')}{int(rid[10:12])}R"
    honmei = [int(k) for k, v in marks.items() if v == "◎"]
    partners = [int(k) for k, v in marks.items() if v != "◎"]
    print(f"\n{'='*78}\n{label} {info['name']}  {spec.get('stars','')}  "
          f"{info['condition'].split('/')[0].strip()}  {len(info['rows'])}頭")
    if not honmei:
        print("  ◎がないためEV計算を行わない"); return []
    a = honmei[0]
    print(f"  ◎{a} {names[a]}（印: " +
          " ".join(f"{v}{k}{names.get(int(k),'')}" for k, v in marks.items()) + "）")

    cands = [("複勝", (a,))]
    cands += [("ワイド", (a, b)) for b in partners]
    cands += [("馬連", (a, b)) for b in partners]
    for i in range(len(partners)):
        for j in range(i + 1, len(partners)):
            cands.append(("3連複", (a, partners[i], partners[j])))

    rows = []
    for kind, nums in cands:
        pay = lookup(od, kind, nums)
        if pay is None:
            continue
        ev, p_hit, _ = eng.ev(kind, nums, actual_odds=pay)
        lo, hi = eng.ev_robust(kind, nums, actual_odds=pay)
        line = 1 / p_hit if p_hit > 0 else float("inf")
        rows.append({"race": label, "kind": kind, "nums": nums, "pay": pay,
                     "p": p_hit, "ev": ev, "lo": lo, "hi": hi, "line": line,
                     "judge": judge(lo, ev)})
    rows.sort(key=lambda r: -r["lo"])
    print(f"  {'式別':<6}{'買い目':<12}{'実配当':>8}{'的中率':>8}{'EV':>7}"
          f"{'頑健下限':>9}{'買いライン':>10}  判定")
    for r in rows:
        bt = "-".join(str(n) for n in r["nums"])
        print(f"  {r['kind']:<6}{bt:<12}{r['pay']:>8.1f}{r['p']*100:>7.1f}%"
              f"{r['ev']:>7.2f}{r['lo']:>9.2f}{r['line']:>10.1f}  {r['judge']}")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    args = ap.parse_args()
    spec = json.load(open(args.spec, encoding="utf-8"))
    allrows = []
    for r in spec["races"]:
        allrows += run_race(r)
    buys = [r for r in allrows if r["judge"].startswith("🟢")]
    mid = [r for r in allrows if r["judge"].startswith("🟡")]
    print(f"\n{'='*78}\n【総括】検討{len(allrows)}点 → 🟢買い {len(buys)}点 ／ "
          f"🟡見かけ {len(mid)}点 ／ ❌見送り {len(allrows)-len(buys)-len(mid)}点")
    for r in sorted(buys, key=lambda x: -x["lo"]):
        bt = "-".join(str(n) for n in r["nums"])
        print(f"  🟢 {r['race']} {r['kind']} {bt}  実配当{r['pay']:.1f}  "
              f"EV{r['ev']:.2f} 頑健[{r['lo']:.2f}-{r['hi']:.2f}]  買いライン{r['line']:.1f}倍")


if __name__ == "__main__":
    main()
