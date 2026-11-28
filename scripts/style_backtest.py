#!/usr/bin/env python3
"""非馬の印で「買い方」だけを変えて、過去の記録レースで比べる。

  python3 scripts/style_backtest.py --cache <結果キャッシュJSON>

A テンプレート（全点100円）: 馬連◎-◯▲△／馬単◎→◯▲△☆／3連複◎-（◯▲△☆から2頭）
B 本人型（10/18新潟6Rの配分）: 単勝◎1,000／馬連◎-◯・◎-▲ 各300／ワイド◎-◯・◎-▲ 各1,200
C 本人型を全点100円: 単勝◎／馬連◎-◯・◎-▲／ワイド◎-◯・◎-▲
◎が1頭でない・◯がいないレースは対象外。取消を含む買い目は返還（集計から除く）。
"""
import argparse, csv, itertools, json, os, sys, time
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_result import race_result   # noqa: E402

ORDERED = {"馬単"}


def key(kind, nums):
    seq = nums if kind in ORDERED else sorted(nums)
    return "".join(f"{n:02d}" for n in seq)


def bets_A(m):
    o = [u for u, k in m.items() if k == "◎"][0]
    by = lambda ks: [u for k in ks for u, x in sorted(m.items()) if x == k]
    ren, tan, fuku = by("◯▲△"), by("◯▲△☆"), by("◯▲△☆")
    out = [("馬連", [o, p], 100) for p in ren]
    out += [("馬単", [o, p], 100) for p in tan]
    out += [("3連複", [o, a, b], 100) for a, b in itertools.combinations(fuku, 2)]
    return out


def bets_B(m, scale):
    o = [u for u, k in m.items() if k == "◎"][0]
    ps = [u for k in "◯▲" for u, x in m.items() if x == k]
    out = [("単勝", [o], 1000 if scale else 100)]
    out += [("馬連", [o, p], 300 if scale else 100) for p in ps]
    out += [("ワイド", [o, p], 1200 if scale else 100) for p in ps]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--marks", default="data/marks_record.csv")
    ap.add_argument("--cache", required=True)
    args = ap.parse_args()
    rows = [r for r in csv.DictReader(open(args.marks, encoding="utf-8-sig")) if r["source"] == "非馬"]
    races, meta = defaultdict(dict), {}
    for r in rows:
        races[r["race_id"]][int(r["umaban"])] = r["mark"]
        meta[r["race_id"]] = (r["date"], r.get("stars", ""))
    cache = json.load(open(args.cache)) if os.path.exists(args.cache) else {}
    use = {rid: m for rid, m in races.items()
           if list(m.values()).count("◎") == 1 and "◯" in m.values()}
    for rid in sorted(use):
        if rid not in cache:
            res = race_result(rid)
            cache[rid] = {"payouts": res["payouts"], "scr": [h["umaban"] for h in res["scratched"]],
                          "finished": res["finished"]}
            json.dump(cache, open(args.cache, "w"))
            time.sleep(0.5)
    books = {"A テンプレート（全点100円）": lambda m: bets_A(m),
             "B 本人型（新潟6Rの配分）": lambda m: bets_B(m, True),
             "C 本人型を全点100円": lambda m: bets_B(m, False)}
    tot = {k: [0, 0, 0, 0] for k in books}           # 投資, 払戻, 的中レース, レース
    by_kind = {k: defaultdict(lambda: [0, 0]) for k in books}
    top = {k: [] for k in books}
    n = 0
    for rid, m in sorted(use.items()):
        c = cache[rid]
        if not c["finished"]:
            continue
        n += 1
        for name, f in books.items():
            inv = pay = 0
            for kind, nums, amt in f(m):
                if set(nums) & set(c["scr"]):
                    continue
                inv += amt
                p = c["payouts"].get(kind, {}).get(key(kind, nums))
                y = p["yen"] * amt // 100 if p else 0
                pay += y
                by_kind[name][kind][0] += amt
                by_kind[name][kind][1] += y
            t = tot[name]
            t[0] += inv; t[1] += pay; t[2] += pay > 0; t[3] += 1
            top[name].append((pay, rid))
    print(f"対象 {n}レース（{min(meta[r][0] for r in use)}〜{max(meta[r][0] for r in use)}）")
    for name, (inv, pay, hit, rc) in tot.items():
        best = sorted(top[name], reverse=True)[:3]
        bsum = sum(b[0] for b in best)
        print(f"{name}: 投資{inv:,} 払戻{pay:,} 回収率{pay/inv:.1%} 当たったレース{hit}/{rc}"
              f"｜上位3レース除く回収率 {(pay-bsum)/max(1,inv - sum(0 for _ in best)):.1%}")
        for kind, (i, p) in by_kind[name].items():
            print(f"    {kind}: {i:,} → {p:,}（{p/i:.1%}）")
        print("    上位:", [(meta[r][0], r, f"{y:,}") for y, r in best])


if __name__ == "__main__":
    main()
