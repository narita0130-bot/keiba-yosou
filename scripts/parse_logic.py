#!/usr/bin/env python3
"""Logic@競馬の無料note（注目馬リスト）を馬番付きのJSONに変換する。

noteの本文は「競馬場,レース番号,馬名」の1行1頭。馬番は書かれていないので、
netkeibaの出馬表を引いて馬名→馬番を解決する。

  python3 scripts/parse_logic.py --text scratchpad/logic0919.txt \
      --ev data/2026-09-19.ev.json --out data/2026-09-19.logic.json

race_id は 非馬の ev.json から「その日そのコースの接頭10桁」を借りて組み立てる
（回次・日目は同じ開催なら全レース共通）。非馬がそのコースを1鞍も扱っていない日は
接頭辞が取れないので、そのコースは取りこぼす。取りこぼしは最後に一覧で出す。

**馬名が出馬表と一致しなかった馬は捨てずに unresolved に残す。** 推測で馬番を
埋めない（docs/handoff.md の原則）。
"""
import argparse
import collections
import json
import os
import re
import sys
import time
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch_odds import JYO, race_info   # noqa: E402

VENUES = "|".join(JYO.values())
LINE = re.compile(rf"^({VENUES}),\s*(\d+)\s*,\s*(\S+)\s*$")
JYO_CODE = {v: k for k, v in JYO.items()}

# 濁音・拗音・長音の表記ゆれを吸収して馬名を突き合わせるための正規化。
_FOLD = str.maketrans(
    "ッャュョィェォァヮガギグゲゴザジズゼゾダヂヅデドバビブベボパピプペポヴ",
    "ツヤユヨイエオアワカキクケコサシスセソタチツテトハヒフヘホハヒフヘホウ")


def norm(s):
    return unicodedata.normalize("NFKC", s or "").translate(_FOLD).replace("ー", "")


def parse_text(path):
    """テキスト → {(競馬場, R): [馬名, ...]}"""
    out = collections.defaultdict(list)
    for ln in open(path, encoding="utf-8"):
        m = LINE.match(ln.strip())
        if m:
            out[(m.group(1), int(m.group(2)))].append(m.group(3))
    return out


def prefixes(ev_files):
    """非馬の ev.json から (競馬場) -> race_id先頭10桁 を集める。"""
    pre = {}
    for f in ev_files:
        for r in json.load(open(f, encoding="utf-8"))["races"]:
            rid = r["race_id"]
            pre[JYO.get(rid[4:6], "")] = rid[:10]
    return pre


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True, help="noteから抜いたテキスト")
    ap.add_argument("--ev", required=True, nargs="+", help="同日の非馬 ev.json")
    ap.add_argument("--date", help="省略時は --out / --text のファイル名から拾う")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    date = args.date
    if not date:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(args.out))
        date = m.group(1) if m else ""

    named = parse_text(args.text)
    pre = prefixes(args.ev)

    races, unresolved, skipped = [], [], []
    for (venue, no), names in sorted(named.items()):
        if venue not in pre:
            skipped.append(f"{venue}{no}R（非馬の ev.json にこのコースが無く race_id を組めない）")
            continue
        rid = pre[venue] + f"{no:02d}"
        try:
            info = race_info(rid)
        except SystemExit as e:
            skipped.append(f"{venue}{no}R（出馬表が取れず: {e}）")
            continue
        by = {norm(x["name"]): x["umaban"] for x in info["rows"]}
        horses = []
        for n in names:
            u = by.get(norm(n))
            if u is None:
                unresolved.append(f"{venue}{no}R {n}")
                horses.append({"name": n, "umaban": None})
            else:
                horses.append({"name": n, "umaban": u})
        races.append({"race_id": rid, "venue": venue, "race_no": no, "horses": horses})
        time.sleep(0.3)

    doc = {"date": date, "source": "Logic@競馬", "races": races}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    n = sum(len(r["horses"]) for r in races)
    ok = sum(1 for r in races for h in r["horses"] if h["umaban"])
    print(f"wrote {args.out}  {len(races)}レース / {n}頭（馬番解決 {ok}頭）")
    for s in skipped:
        print(f"  スキップ: {s}")
    for u in unresolved:
        print(f"  馬番不明: {u}")


if __name__ == "__main__":
    main()
