#!/usr/bin/env python3
"""Logic@競馬の無料note（注目馬リスト）を馬番付きのJSONに変換する。

noteの本文は「競馬場,レース番号,馬名」の1行1頭。馬番は書かれていないので、
netkeibaの出馬表を引いて馬名→馬番を解決する。

  python3 scripts/parse_logic.py --text data/2026-09-20.logic.txt \
      --out data/2026-09-20.logic.json
  # 非馬の ev.json が既にあるならそれを使ってもよい（無くても動く）
  python3 scripts/parse_logic.py --text data/2026-09-19.logic.txt \
      --ev data/2026-09-19.ev.json --out data/2026-09-19.logic.json

race_id は netkeiba の開催一覧（kaisai_date）から「その日そのコースの接頭10桁」を
引いて組み立てる。**非馬のnoteが無い日でも動く。** 非馬が出ない日曜（Xのポストだけ）が
あるので、ev.json に依存させない。--ev を渡した場合はそちらを優先する
（既に手元にある確定情報のほうが確か）。

**馬名が出馬表と一致しなかった馬は捨てずに unresolved に残す。** 推測で馬番を
埋めない（docs/handoff.md の原則）。

--out が既にあれば、そこで解決済みのレースは再取得せずそのまま残す。netkeiba は
叩きすぎると 400 を返すので、取りこぼしたら同じコマンドを流し直せば埋まる。
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

from fetch_odds import JYO, kaisai_prefixes, race_info   # noqa: E402
from fetch_result import race_result   # noqa: E402

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


def name_to_umaban(rid):
    """馬名 -> 馬番。確定済みなら結果ページ1枚で済む（出馬表を引かない）。

    過去分をさかのぼるときに効く。結果ページには馬番・馬名・着順・人気・単勝オッズ・
    複勝払戻が全部載っているので、取得回数が半分になる。
    """
    try:
        res = race_result(rid)
        if res["finished"]:
            rows = list(res["order"]) + list(res.get("scratched", []))
            if rows:
                return {norm(h["name"]): h["umaban"] for h in rows if h.get("name")}
    except SystemExit:
        pass
    return {norm(x["name"]): x["umaban"] for x in race_info(rid)["rows"]}


def prefixes(date, ev_files):
    """競馬場 -> race_id先頭10桁。開催一覧を基本にし、ev.json があれば上書きする。"""
    pre = kaisai_prefixes(date) if date else {}
    for f in ev_files or []:
        for r in json.load(open(f, encoding="utf-8"))["races"]:
            rid = r["race_id"]
            v = JYO.get(rid[4:6])
            if v:
                pre[v] = rid[:10]
    return pre


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True, help="noteから抜いたテキスト")
    ap.add_argument("--ev", nargs="*", default=[],
                    help="同日の非馬 ev.json（任意。無ければ開催一覧から引く）")
    ap.add_argument("--date", help="省略時は --out / --text のファイル名から拾う")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    date = args.date
    for cand in (args.out, args.text):
        if date:
            break
        m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(cand))
        date = m.group(1) if m else ""

    if not date and not args.ev:
        ap.error("--date か --out のファイル名で日付を示すこと（開催一覧の取得に必要）")

    named = parse_text(args.text)
    pre = prefixes(date, args.ev)

    # 既に解決済みのレースは再取得しない（レート制限で取りこぼした分だけ埋める）
    done = {}
    if os.path.exists(args.out):
        for r in json.load(open(args.out, encoding="utf-8")).get("races", []):
            if all(h.get("umaban") for h in r["horses"]):
                done[(r["venue"], r["race_no"])] = r

    races, unresolved, skipped = [], [], []
    for (venue, no), names in sorted(named.items()):
        if (venue, no) in done:
            races.append(done[(venue, no)])
            continue
        if venue not in pre:
            skipped.append(f"{venue}{no}R（この日の開催一覧に {venue} が無く race_id を組めない）")
            continue
        rid = pre[venue] + f"{no:02d}"
        try:
            by = name_to_umaban(rid)
        except SystemExit as e:
            skipped.append(f"{venue}{no}R（馬番を解決できず: {e}）")
            continue
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
    races.sort(key=lambda r: (r["venue"], r["race_no"]))
    n = sum(len(r["horses"]) for r in races)
    ok = sum(1 for r in races for h in r["horses"] if h["umaban"])
    reused = sum(1 for r in races if (r["venue"], r["race_no"]) in done)
    print(f"wrote {args.out}  {len(races)}レース / {n}頭（馬番解決 {ok}頭"
          + (f"、うち {reused}レースは前回の結果を再利用" if reused else "") + "）")
    if skipped:
        print("  ※ 取りこぼしは同じコマンドを流し直せば埋まる（解決済みは再取得しない）")
    for s in skipped:
        print(f"  スキップ: {s}")
    for u in unresolved:
        print(f"  馬番不明: {u}")


if __name__ == "__main__":
    main()
