# -*- coding: utf-8 -*-
"""買い目リスト（data/*.bets.json）を最新オッズで再評価して表示する。

締切直前に実行し、実配当の変動を反映した金額傾斜とEVを確認するためのもの。

  python3 engine/show_bets.py --spec data/2026-08-23.bets.json
"""
import argparse, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from run_ev import build_engine                                        # noqa: E402
from fetch_odds import (TYPE_SANRENPUKU, TYPE_UMAREN, TYPE_UMATAN,     # noqa: E402
                        odds_api)

T = {"馬連": TYPE_UMAREN, "馬単": TYPE_UMATAN, "3連複": TYPE_SANRENPUKU}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    args = ap.parse_args()
    s = json.load(open(args.spec, encoding="utf-8"))
    with_amt = any(len(b) > 2 for r in s["races"] for b in r["bets"])
    print(f"{s['source']}\n状態: {s.get('status','')}\n")
    grand = grand_hit = 0
    for r in s["races"]:
        info, eng, names = build_engine(r["race_id"], r["marks"])
        od, stamp = {}, ""
        for k, t in T.items():
            d = odds_api(r["race_id"], t)
            od[k] = d["odds"][str(t)]; stamp = d["official_datetime"]
            time.sleep(0.3)
        print(f"■ {r['label']}    （オッズ {stamp}）")
        head = f"  {'式別':<5}{'買い目':<9}{'配当':>7}{'人気':>5}"
        print(head + (f"{'金額':>7}{'払戻':>9}" if with_amt else "") + "  EV   判定  組み合わせ")
        tot = 0
        for bet in r["bets"]:
            kind, c = bet[0], bet[1]
            amt = bet[2] if len(bet) > 2 else 0
            key = "".join(f"{n:02d}" for n in (c if kind == "馬単" else sorted(c)))
            v = od[kind].get(key)
            if not v:
                print(f"  {kind:<5}{c} 取得不可"); continue
            pay = float(v[0])
            ev, _, _ = eng.ev(kind, tuple(c), actual_odds=pay)
            lo, _ = eng.ev_robust(kind, tuple(c), actual_odds=pay)
            mark = "🟢" if lo >= 1 else ("🟡" if ev >= 1 else "❌")
            arrow = "→" if kind == "馬単" else "-"
            tot += amt
            money = f"{amt:>7,}{int(pay*amt):>9,}" if with_amt else ""
            print(f"  {kind:<5}{arrow.join(map(str,c)):<9}{pay:>7.1f}{v[2]:>5}{money}"
                  f"{ev:>6.2f}  {mark}   {'-'.join(names[n] for n in c)}")
        grand += tot
        print(f"  → {len(r['bets'])}点" + (f" / {tot:,}円" if with_amt else "") + "\n")
    print(f"【合計】{sum(len(r['bets']) for r in s['races'])}点"
          + (f" / {grand:,}円" if with_amt else "（金額は未設定）"))


if __name__ == "__main__":
    main()
