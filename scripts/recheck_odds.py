#!/usr/bin/env python3
"""発走直前にオッズを取り直し、朝に作った買い目の期待値とトリガミを確かめる。

払戻は締切時点のオッズで決まるので、朝のオッズで出したEVは甘めに出やすい
（10/17〜11/7 の的中12件では、確定配当が買ったときのオッズより下がったのが9件、
中央値 −8%）。発走10〜15分前に取り直して、外す候補を並べる。
外すかどうかはユーザーが決める。このスクリプトは買い目ファイルを書き換えない。

  python3 scripts/recheck_odds.py --bets data/2026-11-08.all.bets.csv \
      --ev data/2026-11-08.all.ev.json --race 202605050201 \
      --log data/2026-11-08.recheck.json

外す候補（⚠）にするのは次のどちらか:
  - トリガミ: 今のオッズ × その買い目の金額 < そのレースの合計金額
  - 判定が下がった: 朝 🟢買い → 今 🟡見かけ/❌見送り、または 朝 🟡 → 今 ❌
朝から ❌ だった買い目はテンプレートの判断で入っているので、外す候補にはしない
（件数だけ出す）。オッズが取れない買い目は「不明」とし、推測で埋めない。

最後の行 `NOTIFY:` はスマホ通知用の1行。`--paste` で拡張機能に貼る形も出す。
"""
import argparse
import csv
import datetime
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "engine"))

import fetch_odds                                            # noqa: E402
from build_bets_csv import BET_SPEC, WD, odds_key, to_odds  # noqa: E402

SLEEP = 0.45            # netkeiba への連続呼び出しは 0.4 秒以上あける（AGENTS.md §6）
JUDGE_SYM = {"buy": "🟢", "apparent": "🟡", "pass": "❌", "": "－"}
JUDGE_RANK = {"buy": 2, "apparent": 1, "pass": 0}
RAW_TO_KEY = {"🟢買い": "buy", "🟡見かけ": "apparent", "❌見送り": "pass"}


def _throttled(fn):
    def wrap(*a, **kw):
        time.sleep(SLEEP)
        return fn(*a, **kw)
    return wrap


odds_api = _throttled(fetch_odds.odds_api)


def combo_nums(combo):
    return [int(x) for x in combo.replace(">", "-").split("-") if x.strip()]


def now_odds_map(rid, kinds):
    """式別ごとの今のオッズ表。ワイド・複勝は下限（保守側、run_ev.real_odds と同じ）。"""
    out, stamp = {}, ""
    for kind in kinds:
        spec = BET_SPEC.get(kind)
        if not spec or spec["odds_type"] is None:
            out[kind] = {}
            continue
        try:
            res = odds_api(rid, spec["odds_type"])
            stamp = res.get("official_datetime") or stamp
            out[kind] = res["odds"].get(spec["odds_key"] or str(spec["odds_type"]), {})
        except (SystemExit, KeyError) as exc:
            print(f"  {kind} のオッズが取れない: {exc}", file=sys.stderr)
            out[kind] = {}
    return out, stamp


def build_engine(rid, marks):
    """run_ev.build_engine をそのまま使う。中の netkeiba 呼び出しだけ間隔をあける。"""
    import run_ev
    run_ev.race_info = _throttled(fetch_odds.race_info)
    run_ev.odds_api = odds_api
    return run_ev.build_engine(rid, marks)[1], run_ev.judge


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bets", required=True, help="朝に作った買い目CSV（build_bets_csv の standard 形式）")
    ap.add_argument("--ev", help="印の定義（EVを出し直す場合）")
    ap.add_argument("--race", action="append", default=[], help="対象レース（省略時はファイル内の全レース）")
    ap.add_argument("--log", help="確認結果を貯めるJSON（後で、外す候補が本当に悪かったかを検証する）")
    ap.add_argument("--paste", action="store_true", help="拡張機能に貼る形（残す分）も出す")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.bets, encoding="utf-8-sig")))
    races = args.race or sorted({r["race_id"] for r in rows})
    marks_by_race = {}
    if args.ev:
        marks_by_race = {r["race_id"]: r["marks"]
                         for r in json.load(open(args.ev, encoding="utf-8"))["races"]}
    log = {}
    if args.log and os.path.exists(args.log):
        log = json.load(open(args.log, encoding="utf-8"))
    log.setdefault("bets_file", args.bets)
    log.setdefault("races", {})

    notify = []
    for rid in races:
        rr = [r for r in rows if r["race_id"] == rid]
        if not rr:
            print(f"{rid}: 買い目ファイルにこのレースが無い")
            continue
        venue, rno, post = rr[0]["venue"], int(rr[0]["race_no"]), rr[0]["post_time"]
        total = sum(int(r["amount"]) for r in rr)
        kinds = sorted({r["bet_type"] for r in rr})
        omap, stamp = now_odds_map(rid, kinds)

        eng = judge = None
        if rid in marks_by_race:
            try:
                eng, judge = build_engine(rid, marks_by_race[rid])
            except (SystemExit, Exception) as exc:      # numpy が無い環境の ImportError も含む
                print(f"  エンジンを組めない（EVは出さない）: {exc}", file=sys.stderr)

        out = []
        for r in rr:
            kind, nums, amt = r["bet_type"], combo_nums(r["combo"]), int(r["amount"])
            raw = omap.get(kind, {}).get(odds_key(kind, nums))
            try:
                now = to_odds(raw[0]) if raw else None
                if now is not None and now <= 0:        # 0.0 は未発売・取消
                    now = None
            except ValueError:
                now = None
            am = float(r["odds"]) if r.get("odds") else None
            ev_now = lo_now = None
            j_now = ""
            if eng is not None and now is not None:
                try:
                    ev_now = eng.ev(kind, nums, actual_odds=now)[0]
                    lo_now = eng.ev_robust(kind, nums, actual_odds=now)[0]
                    j_now = RAW_TO_KEY[judge(lo_now, ev_now)]
                except Exception:
                    ev_now = lo_now = None
                    j_now = ""
            j_am = r.get("judge", "")
            flags = []
            if now is None:
                flags.append("不明")
            else:
                if now * amt < total:
                    flags.append("トリガミ")
                if j_am in JUDGE_RANK and j_now in JUDGE_RANK and JUDGE_RANK[j_now] < JUDGE_RANK[j_am]:
                    flags.append("判定↓")
            out.append({"bet_type": kind, "combo": r["combo"], "nums": nums, "amount": amt,
                        "odds_am": am, "odds_now": now,
                        "ev_am": float(r["ev"]) if r.get("ev") else None,
                        "ev_now": round(ev_now, 3) if ev_now is not None else None,
                        "ev_low_now": round(lo_now, 3) if lo_now is not None else None,
                        "judge_am": j_am, "judge_now": j_now, "flags": flags})

        drop = [o for o in out if {"トリガミ", "判定↓"} & set(o["flags"])]
        unknown = [o for o in out if "不明" in o["flags"]]
        chg = [o["odds_now"] / o["odds_am"] - 1 for o in out if o["odds_now"] and o["odds_am"]]
        avg = sum(chg) / len(chg) if chg else None
        below1 = sum(1 for o in out if o["ev_now"] is not None and o["ev_now"] < 1.0)

        am_time = rr[0].get("odds_time", "")
        print(f"# {venue}{rno}R（{post}発走）直前オッズ確認")
        print(f"朝のオッズ {am_time[-8:-3] or '?'} → 今 {stamp[-8:-3] or '?'}　{len(out)}点 {total:,}円")
        print()
        print("| 買い目 | 金額 | オッズ 朝→今 | 変化 | 判定 朝→今 | |")
        print("|---|---|---|---|---|---|")
        for o in out:
            sep = "→" if BET_SPEC.get(o["bet_type"], {}).get("ordered") else "-"
            c = sep.join(str(n) for n in o["nums"])
            od = f"{o['odds_am']:.1f}→{o['odds_now']:.1f}" if o["odds_am"] and o["odds_now"] else \
                 f"{o['odds_am'] or '?'}→不明"
            ch = f"{(o['odds_now'] / o['odds_am'] - 1) * 100:+.0f}%" if o["odds_am"] and o["odds_now"] else ""
            jd = f"{JUDGE_SYM.get(o['judge_am'], '－')}→{JUDGE_SYM.get(o['judge_now'], '－')}"
            mark = "⚠ " + "・".join(f for f in o["flags"] if f != "不明") if drop and o in drop else \
                   ("不明" if "不明" in o["flags"] else "")
            print(f"| {o['bet_type']} {c} | {o['amount']}円 | {od} | {ch} | {jd} | {mark} |")
        print()
        avg_s = f"{avg * 100:+.0f}%" if avg is not None else "不明"
        print(f"外す候補 {len(drop)}点（トリガミ {sum('トリガミ' in o['flags'] for o in drop)}・"
              f"判定↓ {sum('判定↓' in o['flags'] for o in drop)}）／オッズ平均 {avg_s}"
              + (f"／今のEV1未満 {below1}点（朝から❌を含む）" if eng is not None else "")
              + (f"／オッズ不明 {len(unknown)}点" if unknown else ""))

        if args.paste:
            ds = rr[0].get("date", "")
            wd = WD[datetime.date(int(ds[:4]), int(ds[4:6]), int(ds[6:8])).weekday()] if len(ds) == 8 else ""
            keep = [o for o in out if o not in drop]
            print()
            print(f"拡張機能に貼る形（外す候補を除いた {len(keep)}点 {sum(o['amount'] for o in keep):,}円。"
                  "全部買うなら朝のCSVのまま）:")
            print("```")
            print("競馬場,レース,式別,馬番1,馬番2,馬番3,金額")
            for o in keep:
                n = o["nums"] + ["", "", ""]
                print(f"{venue}({wd}),{rno},{o['bet_type']},{n[0]},{n[1]},{n[2]},{o['amount']}")
            print("```")

        notify.append(f"{venue}{rno}R直前 {len(out)}点中 外す候補{len(drop)}点"
                      + (f"(トリガミ{sum('トリガミ' in o['flags'] for o in drop)}"
                         f"・判定↓{sum('判定↓' in o['flags'] for o in drop)})" if drop else "")
                      + f"｜オッズ平均{avg_s}")
        log["races"].setdefault(rid, []).append({
            "checked_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
                          .strftime("%Y-%m-%d %H:%M:%S"),
            "odds_time": stamp, "post_time": post, "total": total, "rows": out})

    if args.log:
        with open(args.log, "w", encoding="utf-8") as fh:
            json.dump(log, fh, ensure_ascii=False, indent=1)
    print()
    print("NOTIFY:" + "／".join(notify))


if __name__ == "__main__":
    main()
