#!/usr/bin/env python3
"""非馬の印から WIN5 の買い目を組む。

WIN5 は5レースの1着を連続で当てる券種で、JRAで 100円 が数百万〜数千万円になりうる
唯一の買い方。本線の馬券（馬連・馬単・3連複）とは別会計で扱うこと。

対象レースは ev.json の stars に "WIN5" を含むものを発走時刻順に並べて特定する。
各レースで買う頭数を --marks で指定する（既定は ◎◯ の2頭）。

  python3 scripts/build_win5.py --ev data/2026-09-13.ev.json --marks ◎◯

実績（8/8〜9/13の88レース）にもとづく成功確率:
  ◎のみ   1着率12.5%  → 32,768回に1回
  ◎◯     1着率31.8%  →     307回に1回（29点前後・約2,900円）
  ◎◯▲    1着率43.2%  →      67回に1回（145点前後・約14,500円）
  印すべて  1着率52.3%  →      26回に1回（569点前後・約57,000円）

**当たる見込みを示すものではない。外れ続ける前提の買い方。**
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch_odds import JYO, race_info  # noqa: E402

ORDER = "◎◯▲△☆"


def win5_races(spec):
    """stars に WIN5 を含むレースを発走時刻順に返す。"""
    out = []
    for r in spec["races"]:
        if "WIN5" not in (r.get("stars") or ""):
            continue
        info = race_info(r["race_id"])
        out.append({"race_id": r["race_id"], "marks": r["marks"],
                    "post": info["condition"].split("発走")[0].strip(),
                    "name": info["name"],
                    "horses": {str(h["umaban"]): h["name"] for h in info["rows"]}})
    out.sort(key=lambda x: x["post"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ev", required=True)
    ap.add_argument("--marks", default="◎◯", help="各レースで買う印（既定 ◎◯）")
    ap.add_argument("--out", help="買い目をJSONで書き出す")
    args = ap.parse_args()

    spec = json.load(open(args.ev, encoding="utf-8"))
    races = win5_races(spec)
    if len(races) != 5:
        print(f"※ WIN5対象が {len(races)}レースしか特定できない。"
              f"ev.json の stars に『WIN5対象』が入っているか確認すること。")
        if not races:
            return 1

    total = 1
    print(f"【WIN5 買い目】{spec['date']}　対象印: {args.marks}\n")
    for i, r in enumerate(races, 1):
        rid = r["race_id"]
        picks = [int(n) for mk in args.marks
                 for n, v in r["marks"].items() if v == mk]
        total *= max(1, len(picks))
        label = f"{JYO.get(rid[4:6], '')}{int(rid[10:12])}R"
        print(f"  ({i}) {r['post']}  {label} {r['name']}")
        for n in picks:
            mk = r["marks"][str(n)]
            print(f"        {mk} {n:>2} {r['horses'].get(str(n), '')}")

    print(f"\n  組み合わせ {total:,}点 = {total*100:,}円")
    if args.out:
        json.dump({"date": spec["date"], "marks": args.marks, "points": total,
                   "races": [{"race_id": r["race_id"], "post": r["post"],
                              "picks": [int(n) for mk in args.marks
                                        for n, v in r["marks"].items() if v == mk]}
                             for r in races]},
                  open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"  wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
