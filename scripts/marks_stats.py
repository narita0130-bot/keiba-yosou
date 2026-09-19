#!/usr/bin/env python3
"""蓄積した印の記録から、予想家別・印別・人気帯別の成績を出す。

  python3 scripts/marks_stats.py

**人気で層別するのが要点。** 非馬は◎に人気薄、◯に手堅い馬を置く傾向があるため、
印別の生の数字を比べると◯のほうが良く見える。それは印の優劣ではなく人気の差。
市場を上回れているかは「同じ人気帯の平均と比べてどうか」でしか判断できない。

参考: 単勝の理論的な勝率は 控除率0.20 を踏まえて おおよそ 0.8/オッズ。
      実測勝率がこれを上回っていれば、その印はその人気帯で買う価値がある。

Logic@競馬（source=Logic）は印の区別が無いので mark="L" の1種類。非馬の印と
突き合わせて「非馬も印を打った馬」「非馬が無印の馬」に分けて出す。後者が
市場を上回り続けるなら買い目に足す価値がある、というのが検証したい仮説。
**まだ決めない。** 5日分の時点では28頭で +9.1pt、誤差と区別できない。

後半で単勝・複勝を全点100円で買った場合の回収率も出す。**複勝を見ること。**
同じ点数なら複勝は単勝の1/3程度の標準誤差で測れる（170点で SE±14 対 ±43）ので、
結論が先に出る。ランダムに買えば控除率ぶん80%に沈むので、比較対象は100%ではなく80%。
"""
import argparse
import csv
import collections
import math
import statistics

BANDS = [(1, 1, "1人気"), (2, 3, "2-3人気"), (4, 6, "4-6人気"),
         (7, 9, "7-9人気"), (10, 99, "10人気以下")]
ORDER = "◎◯▲△☆"


def band(n):
    for lo, hi, lab in BANDS:
        if lo <= n <= hi:
            return lab
    return "?"


def line(lab, rows, indent=0, sd=False):
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
    tail = ""
    if sd and exp:
        p = exp / 100
        se = math.sqrt(p * (1 - p) / n) * 100          # 勝率の標準誤差
        tail = f"  ({edge / se:+.1f}SD)" if se else ""
    print(f"{'  '*indent}{lab:<14}{n:>5}{w/n*100:>8.1f}%{p2/n*100:>9.1f}%{p3/n*100:>9.1f}%"
          f"{exp:>10.1f}%{edge:>+9.1f}pt{tail}")


HEAD = f"{'':14}{'頭数':>5}{'勝率':>8}{'2着内':>9}{'3着内':>9}{'市場想定':>10}{'差':>9}"


def ret(lab, rows, key, indent=0):
    """全点100円で買ったときの回収率。key は "fuku"（複勝）か "tan"（単勝）。"""
    v = []
    for r in rows:
        if key == "fuku":
            if r["fuku"] == "":      # 複勝が発売されないレース（4頭以下）は除く
                continue
            v.append(float(r["fuku"]))
        else:
            v.append(round(float(r["odds"]) * 100) if r["chaku"] == "1" and r["odds"] else 0.0)
    n = len(v)
    if n < 2:
        return None
    m = statistics.mean(v)
    se = statistics.stdev(v) / math.sqrt(n)
    hits = sum(1 for x in v if x > 0)
    print(f"{'  '*indent}{lab:<14}{n:>5}{m:>9.1f}%{se:>8.1f}{m-se:>8.0f}〜{m+se:<5.0f}"
          f"{(m-80)/se:>+8.1f}SD{hits/n*100:>9.1f}%")
    return n, m, se


def returns(hima, logic):
    covered = {r["race_id"] for r in hima}
    marked = {(r["race_id"], r["umaban"]) for r in hima}
    only = [r for r in logic if r["race_id"] in covered
            and (r["race_id"], r["umaban"]) not in marked]
    print("\n\n【全点100円で買った場合の回収率】")
    print(f"{'':14}{'点数':>5}{'回収率':>9}{'SE':>8}{'±1SE':>13}{'ランダム比':>11}{'的中率':>9}")
    for key, name in (("fuku", "複勝"), ("tan", "単勝")):
        print("-" * 70 + f"  {name}")
        gate = ret("Logic 全部", logic, key)
        ret("非馬は無印", only, key, indent=1)
        for mk in ORDER:
            sub = [r for r in hima if r["mark"] == mk]
            if len(sub) >= 10:
                ret(f"非馬 {mk}", sub, key)
        ret("非馬 全印", hima, key)
        if key == "fuku" and gate:
            n, m, se = gate
            ok = n >= 300 and m - se > 100
            print(f"\n  採用条件: 300点以上 かつ 複勝回収率の −1SE が100%超")
            print(f"  いま: {n}点 / 回収率 {m:.1f}% / −1SE = {m-se:.0f}%")
            if ok:
                print("  → **条件を満たした。買い方の変更を検討してよい。**")
            else:
                # SE は 1/√n でしか縮まないので「あと何点」は300点ではなく
                # 今の回収率から逆算する。108%なら約510点、104%なら約2000点必要。
                sd = se * math.sqrt(n)
                need = (sd / (m - 100)) ** 2 if m > 100 else None
                if need is None:
                    print("  → 回収率が100%を下回っているので、点数を増やしても条件は満たせない。")
                else:
                    print(f"  → まだ。いまの回収率が続くとして必要な点数は約{need:.0f}点"
                          f"（あと{max(0, need-n):.0f}点）。")
                    print(f"     300点はあくまで下限。SEは1/√nでしか縮まないので、"
                          f"回収率が100%に近いほど必要点数は急に増える。")
    print("\n  ※ ランダムに買うと控除率ぶんで80%に沈む。比較対象は100%ではなく80%。")
    print("  ※ 複勝を見ること。単勝は同じ点数でも誤差が3倍あり、上位1本で符号が変わる。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", default="data/marks_record.csv")
    args = ap.parse_args()
    all_rows = [r for r in csv.DictReader(open(args.record, encoding="utf-8-sig"))
                if not r["scratched"] and r["chaku"]]
    for r in all_rows:
        r.setdefault("source", "非馬")
        if not r["source"]:
            r["source"] = "非馬"

    hima = [r for r in all_rows if r["source"] == "非馬"]
    logic = [r for r in all_rows if r["source"] == "Logic"]

    races = len({r["race_id"] for r in hima})
    print(f"【非馬の印 実測成績】{races}レース / {len(hima)}頭\n")
    print(HEAD)
    print("-" * 66)
    for mk in ORDER:
        sub = [r for r in hima if r["mark"] == mk]
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
    print("-" * 66)
    line("全印", hima)

    if logic:
        # 非馬が印を打ったレースに限定しないと「非馬は無印」の意味が変わる
        # （そもそも非馬が扱っていないレースが混ざる）。
        covered = {r["race_id"] for r in hima}
        marked = {(r["race_id"], r["umaban"]) for r in hima}
        sub = [r for r in logic if r["race_id"] in covered]
        both = [r for r in sub if (r["race_id"], r["umaban"]) in marked]
        only = [r for r in sub if (r["race_id"], r["umaban"]) not in marked]
        print(f"\n\n【Logic@競馬 注目馬】{len({r['race_id'] for r in sub})}レース / {len(sub)}頭"
              f"（非馬が印を打ったレースに限定。記録全体では {len(logic)}頭）\n")
        print(HEAD)
        print("-" * 66)
        line("注目馬 全部", sub, sd=True)
        line("非馬も印", both, indent=1, sd=True)
        line("非馬は無印", only, indent=1, sd=True)
        print("\n※ SDは「市場想定どおりなら偶然でこのくらいズレる」を1とした目安。")
        print("  ±2SDを超えて、かつ50頭以上貯まるまでは買い目に反映しない。")
        n = len(only)
        need = max(0, 50 - n)
        print(f"  いまの『非馬は無印』は {n}頭。判断まであと {need}頭。"
              if need else f"  『非馬は無印』は {n}頭。頭数の条件は満たした。")

        returns(hima, logic)

    print("\n「市場想定」= 単勝オッズから控除率20%を戻した勝率の平均。")
    print("「差」がプラスなら、その印はその人気帯で市場を上回っている。")
    print("※ 各行 30頭を切るうちは誤差のほうが大きい。数字を動かさず貯めること。")


if __name__ == "__main__":
    main()
