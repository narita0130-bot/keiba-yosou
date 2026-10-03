#!/usr/bin/env python3
"""情報部: 今日の出馬表を取得してev.jsonテンプレートを生成する。

  # 今日のレース一覧だけ表示（出馬表取得なし・高速）
  python3 scripts/morning.py [--date YYYYMMDD]

  # 指定レースの出馬表を取得してev.jsonテンプレートを生成
  python3 scripts/morning.py --races 202601020208 202604030206

  # 今日の全レースのev.jsonテンプレートを生成（編集して使う）
  python3 scripts/morning.py --all [--date YYYYMMDD]
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_odds import JYO, list_races, race_info  # noqa: E402


def show_list(date_str):
    """開催日のレース一覧だけ表示（出馬表取得なし）。"""
    ids = list_races(date_str)
    d = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    if not ids:
        print(f"⚠️  {d} の開催が見つかりません（非開催日の可能性）")
        return []
    print(f"📋 {d} の開催: {len(ids)} レース\n")
    for rid in ids:
        jyo = JYO.get(rid[4:6], rid[4:6])
        rnum = int(rid[10:12])
        print(f"  {rid}  {jyo}{rnum}R")
    print(f"\nev.jsonテンプレートを生成するには:")
    print(f"  --all                  全レース")
    print(f"  --races {ids[0]} ...  指定レースのみ")
    return ids


def fetch_and_build(race_ids):
    """出馬表を取得して表示し、テンプレートエントリのリストを返す。"""
    templates = []
    total = len(race_ids)
    for i, rid in enumerate(race_ids, 1):
        jyo = JYO.get(rid[4:6], rid[4:6])
        rnum = int(rid[10:12])
        print(f"[{i:02d}/{total}] {jyo}{rnum}R ({rid}) ...", end="", flush=True)
        try:
            info = race_info(rid)
        except SystemExit as e:
            print(f" スキップ: {e}")
            continue

        draw_note = "" if info.get("draw_confirmed") else " ⚠️枠順未確定(tr_N使用)"
        print(f" {info['name']}{draw_note}  {len(info['rows'])}頭")

        horses_ref = {}
        for h in sorted(info["rows"], key=lambda r: r["umaban"]):
            name_jockey = f"{h['name']} ({h['jockey']})"
            horses_ref[str(h["umaban"])] = name_jockey
            print(f"       {h['umaban']:>2}  {h['name']:<16}  {h['jockey']}")
        print()

        templates.append({
            "race_id": rid,
            "stars": "",
            "marks": {},
            "bets": [],
            "memo": "",
            "_name": info["name"] + draw_note,
            "_condition": info.get("condition", ""),
            "_horses": horses_ref,
        })
        if i < total:
            time.sleep(0.6)
    return templates


def save_template(date_dash, templates, source, force=False):
    """data/YYYY-MM-DD.ev.json にテンプレートを保存する。"""
    out_path = os.path.join(REPO_ROOT, "data", f"{date_dash}.ev.json")
    if os.path.exists(out_path) and not force:
        print(f"⚠️  {out_path} は既に存在します。上書きするには --force を指定してください")
        return None
    spec = {
        "date": date_dash,
        "source": source,
        "races": templates,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
    return out_path


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="YYYYMMDD（既定: 本日JST）")
    ap.add_argument("--all", action="store_true", help="全レースのテンプレートを生成")
    ap.add_argument("--races", nargs="+", metavar="RACE_ID", help="指定race_idのみ")
    ap.add_argument("--source", default="非馬@競馬予想 note", help="印の出典")
    ap.add_argument("--force", action="store_true", help="ev.jsonが既存でも上書きする")
    args = ap.parse_args()

    date_str = args.date or datetime.now(JST).strftime("%Y%m%d")
    date_dash = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

    print(f"\n=== 情報部 ── {date_dash} ===\n")

    if args.races:
        race_ids = args.races
    elif args.all:
        race_ids = list_races(date_str)
        if not race_ids:
            print(f"⚠️  {date_dash} の開催が見つかりません")
            sys.exit(1)
        print(f"全 {len(race_ids)} レースを取得します\n")
    else:
        show_list(date_str)
        return

    templates = fetch_and_build(race_ids)
    if not templates:
        print("⚠️  有効なレースがありませんでした")
        sys.exit(1)

    out_path = save_template(date_dash, templates, args.source, args.force)
    if out_path:
        print(f"✅ テンプレート保存: {out_path}")
        print(f"\n【次のステップ（殿の仕事）】")
        print(f"  1. {out_path} を開いて以下を入力:")
        print(f'     "stars": "★★★"  （勝負度）')
        print(f'     "marks": {{"馬番": "◎", "馬番": "◯"}}  （印）')
        print(f"  2. 不要なレース（★なし）のエントリを削除")
        print(f"  3. python3 engine/run_ev.py --spec {out_path}")


if __name__ == "__main__":
    main()
