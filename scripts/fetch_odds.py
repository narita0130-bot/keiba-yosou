#!/usr/bin/env python3
"""netkeiba の公開オッズを取得して、印付きの一覧を出力する。

使い方:
  # その日の開催・レースID一覧
  python3 scripts/fetch_odds.py races --date 20260808

  # 1レースの出馬表＋単勝/複勝（印を付けると先頭にまとめて表示）
  python3 scripts/fetch_odds.py odds --race 202601010510 --mark 4=◎ --mark 8=◯ --mark 1=▲ --mark 3=☆

  # 組み合わせオッズ（馬連/ワイド/馬単/3連複/3連単）
  python3 scripts/fetch_odds.py combo --race 202601010510 --bet 馬単:4>8 --bet 3連複:3-4-8 --bet 3連単:4>8>1
"""
import argparse
import json
import re
import sys
import time
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# netkeiba の api_get_jra_odds.html の type 番号
TYPE_TAN_FUKU = 1   # レスポンス内 "1"=単勝, "2"=複勝
TYPE_UMAREN = 4
TYPE_WIDE = 5       # [下限, 上限, 人気]
TYPE_UMATAN = 6     # 着順あり
TYPE_SANRENPUKU = 7
TYPE_SANRENTAN = 8  # 着順あり

BET_TYPES = {
    "馬連": (TYPE_UMAREN, False),
    "ワイド": (TYPE_WIDE, False),
    "馬単": (TYPE_UMATAN, True),
    "3連複": (TYPE_SANRENPUKU, False),
    "3連単": (TYPE_SANRENTAN, True),
}

JYO = {"01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
       "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉"}


def _get(url, referer=None):
    headers = {"User-Agent": UA}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(req, timeout=30).read()


def _strip(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).replace("&nbsp;", " ").strip()


def list_races(date):
    """開催日の全レースの race_id を返す。"""
    body = _get(f"https://race.netkeiba.com/top/race_list_sub.html?kaisai_date={date}").decode("utf-8", "replace")
    ids = sorted(set(re.findall(r"shutuba\.html\?race_id=(\d+)", body)))
    return ids


def race_info(race_id):
    """出馬表から レース名・条件・馬番→馬名 を取得する。"""
    html = _get(f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}").decode("utf-8", "replace")
    name = re.search(r'class="RaceName"[^>]*>\s*([^<\n]+)', html)
    d1 = re.search(r'RaceData01">(.*?)</div>', html, re.S)
    d2 = re.search(r'RaceData02">(.*?)</div>', html, re.S)
    horses = {}
    for row in re.findall(r'<tr class="HorseList" id="tr_\d+">(.*?)</tr>', html, re.S):
        num = re.search(r'Umaban\d*[^>]*>\s*(\d+)', row)
        horse = re.search(r'class="HorseName"><a[^>]*title="([^"]+)"', row)
        if num and horse:
            horses[int(num.group(1))] = horse.group(1)
    return {
        "race_id": race_id,
        "name": (name.group(1).strip() if name else ""),
        "condition": _strip(d1.group(1) if d1 else "").replace("--> ", ""),
        "class": _strip(d2.group(1) if d2 else ""),
        "horses": horses,
    }


def odds_api(race_id, type_):
    url = (f"https://race.netkeiba.com/api/api_get_jra_odds.html"
           f"?type={type_}&race_id={race_id}&action=init")
    res = json.loads(_get(url, referer=f"https://race.netkeiba.com/odds/index.html?race_id={race_id}").decode())
    if res.get("status") == "NG":
        raise SystemExit(f"オッズ未発売または取得不可 (race_id={race_id}, type={type_}): {res.get('reason')}")
    return res["data"]


def cmd_races(args):
    ids = list_races(args.date)
    if not ids:
        raise SystemExit(f"{args.date} の開催が見つかりません")
    for rid in ids:
        print(f"{rid}  {JYO.get(rid[4:6], rid[4:6])}{int(rid[10:12])}R")


def cmd_odds(args):
    info = race_info(args.race)
    data = odds_api(args.race, TYPE_TAN_FUKU)
    tan, fuku = data["odds"]["1"], data["odds"]["2"]
    marks = dict(m.split("=", 1) for m in args.mark)
    marks = {int(k): v for k, v in marks.items()}

    print(f"# {JYO.get(args.race[4:6], '')}{int(args.race[10:12])}R {info['name']}")
    print(f"{info['condition']} / {info['class']}")
    print(f"オッズ確定時刻: {data['official_datetime']}\n")

    def line(num):
        t, f = tan[f"{num:02d}"], fuku[f"{num:02d}"]
        mark = marks.get(num, "")
        return f"| {mark} | {num} {info['horses'].get(num, '?')} | {t[0]} | {t[2]} | {f[0]}-{f[1]} |"

    header = "| 印 | 馬番・馬名 | 単勝 | 人気 | 複勝 |\n|---|---|---|---|---|"
    if marks:
        print("## 印")
        print(header)
        for num in marks:
            print(line(num))
        print()
    print("## 全頭（人気順）")
    print(header)
    for num in sorted(tan, key=lambda k: int(tan[k][2])):
        print(line(int(num)))


def _key(bet_type, legs):
    """買い目文字列 -> API のキー。着順なしの式別は昇順に正規化する。"""
    type_, ordered = BET_TYPES[bet_type]
    nums = [int(n) for n in re.split(r"[>\-]", legs)]
    if not ordered:
        nums = sorted(nums)
    return type_, "".join(f"{n:02d}" for n in nums)


def cmd_combo(args):
    info = race_info(args.race)
    print(f"# {JYO.get(args.race[4:6], '')}{int(args.race[10:12])}R {info['name']}\n")
    print("| 買い目 | オッズ | 人気 |")
    print("|---|---|---|")
    cache = {}
    stamp = None
    for bet in args.bet:
        bet_type, legs = bet.split(":", 1)
        if bet_type not in BET_TYPES:
            raise SystemExit(f"未対応の式別: {bet_type} (対応: {', '.join(BET_TYPES)})")
        type_, key = _key(bet_type, legs)
        if type_ not in cache:
            cache[type_] = odds_api(args.race, type_)
            stamp = cache[type_]["official_datetime"]
            time.sleep(1)
        row = cache[type_]["odds"][str(type_)].get(key)
        names = "-".join(info["horses"].get(int(key[i:i + 2]), "?") for i in range(0, len(key), 2))
        if row:
            print(f"| {bet_type} {legs} ({names}) | {row[0]} | {row[2]} |")
        else:
            print(f"| {bet_type} {legs} ({names}) | 取得不可 | - |")
    if stamp:
        print(f"\nオッズ確定時刻: {stamp}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    p_races = sub.add_parser("races", help="開催日の race_id 一覧")
    p_races.add_argument("--date", required=True, help="YYYYMMDD")
    p_races.set_defaults(func=cmd_races)

    p_odds = sub.add_parser("odds", help="単勝・複勝オッズ")
    p_odds.add_argument("--race", required=True)
    p_odds.add_argument("--mark", action="append", default=[], metavar="馬番=印")
    p_odds.set_defaults(func=cmd_odds)

    p_combo = sub.add_parser("combo", help="組み合わせオッズ")
    p_combo.add_argument("--race", required=True)
    p_combo.add_argument("--bet", action="append", required=True, metavar="式別:買い目",
                         help="例) 馬単:4>8 / 3連複:3-4-8 / 3連単:4>8>1")
    p_combo.set_defaults(func=cmd_combo)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
