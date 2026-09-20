#!/usr/bin/env python3
"""学習期間のデータ健全性を確認する。**検証期間には一切触れない。**

docs/prereg_model.md の分割にしたがい、2026-03-31 までのデータだけを読む。
壊れたデータで作ったモデルを信じないために、モデルを書く前に必ず通す。

  python3 scripts/data_check.py
"""
import argparse
import collections
import csv
import glob
import statistics as st

TRAIN_END = "2026-03-31"


def load(end=TRAIN_END):
    rows = []
    for f in sorted(glob.glob("data/races/*.csv")):
        with open(f, encoding="utf-8-sig") as fh:
            rows += [r for r in csv.DictReader(fh) if r["date"] <= end]
    return rows


def pct(n, d):
    return f"{n/d*100:5.1f}%" if d else "    -"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--end", default=TRAIN_END)
    args = ap.parse_args()
    rows = load(args.end)
    races = {r["race_id"] for r in rows}
    print(f"【学習期間 〜{args.end}】{len(races):,}レース / {len(rows):,}行")
    print(f"  期間 {min(r['date'] for r in rows)} 〜 {max(r['date'] for r in rows)}\n")

    print("■ 欠損率（空欄の割合）")
    for c in ("chaku", "waku", "umaban", "sex", "age", "kinryo", "jockey", "time_sec",
              "ninki", "odds", "agari", "weight", "weight_diff", "trainer",
              "distance", "going", "weather", "field_size", "prize1", "passage"):
        miss = sum(1 for r in rows if not r.get(c))
        flag = "  ← 常に空（取得不可）" if miss == len(rows) else ""
        print(f"   {c:<12}{pct(miss, len(rows))}  ({miss:,}行){flag}")

    print("\n■ 出走状態")
    stat = collections.Counter(r["status"] or "出走" for r in rows)
    for k, v in stat.most_common():
        print(f"   {k:<8}{v:>8,}行 {pct(v, len(rows))}")

    print("\n■ 馬場・コース")
    print("   surface:", dict(collections.Counter(r["surface"] for r in rows)))
    print("   going  :", dict(collections.Counter(r["going"] for r in rows).most_common(8)))
    ds = [int(r["distance"]) for r in rows if r["distance"]]
    print(f"   distance: {min(ds)}〜{max(ds)}m  中央値{int(st.median(ds))}m")
    fs = [int(r["field_size"]) for r in rows if r["field_size"]]
    print(f"   field_size: {min(fs)}〜{max(fs)}頭  中央値{int(st.median(fs))}頭")

    print("\n■ 走破タイムの妥当性（出走馬のみ）")
    run = [r for r in rows if r["time_sec"] and r["distance"] and not r["status"]]
    sp = [(int(r["distance"]) / float(r["time_sec"]), r) for r in run]
    v = [x for x, _ in sp]
    print(f"   平均速度 {st.mean(v):.2f} m/s  中央値 {st.median(v):.2f}  範囲 {min(v):.2f}〜{max(v):.2f}")
    bad = [r for x, r in sp if x < 12 or x > 20]
    print(f"   明らかな異常（12m/s未満 or 20m/s超）: {len(bad)}行")
    for r in bad[:5]:
        print(f"     {r['date']} {r['venue']}{r['race_no']}R {r['horse']} "
              f"{r['distance']}m {r['time_sec']}秒")

    print("\n■ 同じ馬が何走ぶん取れているか（馬名をキーにした場合）")
    byh = collections.Counter(r["horse"] for r in rows if r["horse"])
    n = collections.Counter(byh.values())
    print(f"   のべ {len(byh):,}頭")
    for k in sorted(n)[:6]:
        print(f"     {k}走のみ {n[k]:>6,}頭")
    print(f"     2走以上   {sum(v for k, v in n.items() if k >= 2):>6,}頭 "
          f"({sum(v for k,v in n.items() if k>=2)/len(byh)*100:.0f}%)")

    print("\n■ 馬名の同名衝突の疑い（性別が途中で変わる／年齢が逆行する）")
    rec = collections.defaultdict(list)
    for r in rows:
        if r["horse"] and r["age"]:
            rec[r["horse"]].append((r["date"], r["sex"], int(r["age"])))
    susp = []
    for h, xs in rec.items():
        xs.sort()
        sexes = {s for _, s, _ in xs if s}
        # セン馬化(牡→セ)は正常なのでそれ以外の変化だけ拾う
        odd_sex = len(sexes) > 1 and sexes != {"牡", "セ"}
        ages = [a for _, _, a in xs]
        if odd_sex or any(b < a for a, b in zip(ages, ages[1:])):
            susp.append((h, xs[0], xs[-1], sexes))
    print(f"   疑いあり {len(susp)}頭 / {len(rec):,}頭")
    for h, a, b, s in susp[:5]:
        print(f"     {h}: {a} → {b}  性別{s}")

    print("\n■ 騎手")
    j = collections.Counter(r["jockey"] for r in rows if r["jockey"])
    print(f"   のべ {len(j):,}人  上位: {', '.join(f'{k}({v:,})' for k, v in j.most_common(5))}")
    print(f"   100騎乗以上: {sum(1 for v in j.values() if v >= 100)}人")


if __name__ == "__main__":
    main()
