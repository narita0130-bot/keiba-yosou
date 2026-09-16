#!/usr/bin/env python3
"""蓄積した印の記録から、印別・人気帯別の成績を出す。

  python3 scripts/marks_stats.py

**人気で層別するのが要点。** 非馬は◎に人気薄、◯に手堅い馬を置く傾向があるため、
印別の生の数字を比べると◯のほうが良く見える。それは印の優劣ではなく人気の差。
市場を上回れているかは「同じ人気帯の平均と比べてどうか」でしか判断できない。

参考: 単勝の理論的な勝率は 控除率0.20 を踏まえて おおよそ 0.8/オッズ。
      実測勝率がこれを上回っていれば、その印はその人気帯で買う価値がある。
"""
import argparse
import csv
import collections

BANDS = [(1, 1, "1人気"), (2, 3, "2-3人気"), (4, 6, "4-6人気"),
         (7, 9, "7-9人気"), (10, 99, "10人気以下")]
ORDER = "◎◯▲△☆"


def band(n):
    for lo, hi, lab in BANDS:
        if lo <= n <= hi:
            return lab
    return "?"


def line(lab, rows, indent=0):
    n = len(rows)
    if not n:
        return
    w = sum(1 for r in rows if r["chaku"] == "1")
    p2 = sum(1 for r in rows if r["chaku"] and int(r["chaku"]) <= 2)
    p3 = sum(1 for r in rows if r["chaku"] and int(r["chaku"]) <= 3)
    od = [float(r["odds"]) for r in rows if r["odds"]]
    # 控除率20%を戻した「市場が見込む勝率」の平均
    exp = sum(0.8 / o for o in od) / len(od) * 100 if od else 0
    edge = w / n * 100 - exp
    print(f"{'  '*indent}{lab:<12}{n:>5}{w/n*100:>8.1f}%{p2/n*100:>9.1f}%{p3/n*100:>9.1f}%"
          f"{exp:>10.1f}%{edge:>+9.1f}pt")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", default="data/marks_record.csv")
    args = ap.parse_args()
    rows = [r for r in csv.DictReader(open(args.record, encoding="utf-8-sig"))
            if not r["scratched"] and r["chaku"]]
    races = len({r["race_id"] for r in rows})
    print(f"【非馬の印 実測成績】{races}レース / {len(rows)}頭\n")
    print(f"{'':12}{'頭数':>5}{'勝率':>8}{'2着内':>9}{'3着内':>9}{'市場想定':>10}{'差':>9}")
    print("-" * 64)
    for mk in ORDER:
        sub = [r for r in rows if r["mark"] == mk]
        if not sub:
            continue
        line(mk, sub)
        by = collections.defaultdict(list)
        for r in sub:
            if r["ninki"]:
                by[band(int(r["ninki"]))].append(r)
        for _, _, lab in BANDS:
            if len(by[lab]) >= 5:      # 5頭未満は読まない
                line(lab, by[lab], indent=1)
        print()
    print("-" * 64)
    line("全印", rows)
    print("\n「市場想定」= 単勝オッズから控除率20%を戻した勝率の平均。")
    print("「差」がプラスなら、その印はその人気帯で市場を上回っている。")
    print("※ 各行 30頭を切るうちは誤差のほうが大きい。数字を動かさず貯めること。")


if __name__ == "__main__":
    main()
