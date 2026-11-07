#!/usr/bin/env python3
"""地方競馬（nar.netkeiba.com）の出馬表・オッズ・結果を、JRA用と同じ形で返す（2026-11-02、JBC用に追加）。

fetch_odds.race_info / odds_api と fetch_result.race_result は、race_id の場コードが
地方（11以上）ならここへ回す。呼ぶ側（build_bets_csv / race_report / odds_page など）は
JRAと同じまま使える。

  python3 scripts/nar.py races --date 20261103            # その日の地方のレース一覧
  python3 scripts/nar.py odds --race 202646110309         # 単勝と馬連の確認

地方の race_id は 年4+場2+月日4+R2（JRAは 年4+場2+回次2+日目2+R2）。R の位置は同じ。

JRAとの違い:
- オッズAPI（api_get_nar_odds.html）は type を変えても単勝しか返さない。
  組み合わせはオッズページのHTML（index.html?type=b4 など）から読む。
  3連複・3連単は軸馬ごとのページ（odds_get_form.html?…&jiku=N）を全頭ぶん読む。
- 発売前は「予想オッズ」（odds_status=yoso）しか無い。**予想オッズは実オッズとして使わない**
  （オッズを推測で埋めない原則）。発売前は SystemExit にする。
- 組み合わせの人気はページに無いので空欄。官製の更新時刻も取れないので、取得時刻を入れる。
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime

from fetch_odds import JST, NAR_JYO, _get, _strip, is_nar  # noqa: F401

BASE = "https://nar.netkeiba.com"


# fetch_odds の type 番号 → オッズページの type
PAGE_TYPE = {4: "b4", 5: "b5", 6: "b6", 7: "b7", 8: "b8"}
SLEEP = 0.6   # netkeiba への連続アクセスの間隔（AGENTS.md は0.4秒以上）


def list_races(date):
    """{race_id: 一覧の見出し} を返す。date は 20261103 か 2026-11-03。"""
    d = date.replace("-", "")
    html = _get(f"{BASE}/top/race_list_sub.html?kaisai_date={d}").decode("utf-8", "replace")
    out = {}
    for rid, body in re.findall(r'race_id=(\d{12})[^>]*>(.*?)</a>', html, re.S):
        out.setdefault(rid, _strip(body))
    return dict(sorted(out.items()))


def race_info(race_id):
    """出馬表。返り値の形は fetch_odds.race_info と同じ。"""
    html = _get(f"{BASE}/race/shutuba.html?race_id={race_id}").decode("utf-8", "replace")
    name = re.search(r'class="RaceName"[^>]*>\s*([^<\n]+)', html)
    d1 = re.search(r'RaceData01">(.*?)</div>', html, re.S)
    d2 = re.search(r'RaceData02">(.*?)</div>', html, re.S)
    horses, rows = {}, []
    draw_confirmed = True
    for trn, row in re.findall(r'<tr class="HorseList[^"]*" id="tr_(\d+)">(.*?)</tr>', html, re.S):
        num = re.search(r'class="Umaban\d*[^"]*">\s*(\d+)', row)
        horse = re.search(r'class="HorseName"><a[^>]*title="([^"]+)"', row)
        if not horse:
            continue
        umaban = int(num.group(1)) if num else None
        if umaban is None:
            draw_confirmed = False
        key = umaban if umaban is not None else int(trn)
        horses[key] = horse.group(1)

        def cell(pattern):
            m = re.search(pattern, row, re.S)
            return _strip(m.group(1)) if m else ""

        rows.append({
            "umaban": key,
            "index": int(trn),
            "name": horse.group(1),
            "waku": cell(r'<td class="Waku\d*[^"]*">(.*?)</td>'),
            "barei": cell(r'<span class="Age">(.*?)</span>'),
            "kinryo": cell(r'<span class="Age">.*?</td>\s*<td class="Txt_C">(.*?)</td>'),
            "jockey": cell(r'<td class="Jockey">(.*?)</td>'),
            "trainer": cell(r'<td class="Trainer">(.*?)</td>'),
        })
    return {
        "race_id": race_id,
        "name": (name.group(1).strip() if name else ""),
        "condition": _strip(d1.group(1) if d1 else "").replace("--> ", ""),
        "class": _strip(d2.group(1) if d2 else ""),
        "horses": horses,
        "rows": rows,
        "draw_confirmed": draw_confirmed,
    }


def _stamp():
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")


def _tanfuku(race_id):
    url = f"{BASE}/api/api_get_nar_odds.html?type=1&race_id={race_id}&action=init"
    res = json.loads(_get(url, referer=f"{BASE}/odds/index.html?race_id={race_id}").decode())
    if res.get("status") != "OK" or res.get("odds_status") != "real":
        raise SystemExit(f"オッズ未発売（予想オッズのみ、または取得不可） race_id={race_id} "
                         f"status={res.get('status')} odds_status={res.get('odds_status')}")
    # 発売直後は odds_status=real でも全頭 0.0 が並ぶ。0.0 は「まだ付いていない」であって
    # オッズではないので落とす。1頭も残らなければ未発売と同じ扱いにする
    tan = {f"{int(k):02d}": [v["Odds"], "", str(v.get("Ninki", ""))]
           for k, v in res["ary_odds"].items()
           if k.isdigit() and re.match(r"\d", str(v.get("Odds", ""))) and float(v["Odds"]) > 0}
    if not tan:
        raise SystemExit(f"オッズがまだ付いていない（発売直後で全頭0.0） race_id={race_id}")
    time.sleep(SLEEP)
    html = _get(f"{BASE}/odds/index.html?type=b1&race_id={race_id}").decode("utf-8", "replace")
    fuku = {}
    blk = html[html.find("odds_fuku_block"):] if "odds_fuku_block" in html else ""
    for u, lo, hi in re.findall(r'<td class="Waku\d*">\d+</td>\s*<td>(\d+)</td>.*?'
                                r'<span class="Odds[^"]*">\s*([\d.]+)\s*-\s*([\d.]+)', blk, re.S):
        if float(hi) > 0:
            fuku[f"{int(u):02d}"] = [lo, hi, ""]
    return {"1": tan, "2": fuku}


def _combo_page(html, page_type):
    out = {}
    for nums, val in re.findall(rf'id="chk_[^"]*_{page_type}_c\d+_([\d_]+)"[^>]*>\s*([^<]*?)\s*<', html):
        val = val.strip()
        if not val or not re.match(r"[\d.]", val) or not re.search(r"[1-9]", val):
            continue          # 空欄・「---」・発売直後の 0.0 はオッズではない
        key = "".join(f"{int(x):02d}" for x in nums.split("_"))
        if page_type == "b5":
            lo, _, hi = val.partition("-")
            out[key] = [lo.strip(), hi.strip(), ""]
        else:
            out[key] = [val.replace(",", ""), "", ""]
    return out


def odds_api(race_id, type_):
    """返り値の形は fetch_odds.odds_api（JRA）の data 部分と同じ：
       {"odds": {"<type>": {"<組番>": [オッズ, 上限など, 人気]}}, "official_datetime": 取得時刻}"""
    type_ = int(type_)
    if type_ == 1:
        return {"odds": _tanfuku(race_id), "official_datetime": _stamp()}
    pt = PAGE_TYPE.get(type_)
    if not pt:
        raise SystemExit(f"地方は type={type_} に未対応")
    # 発売前（予想オッズのみ）なら組み合わせも出さない
    _tanfuku(race_id)
    time.sleep(SLEEP)
    table = {}
    if type_ in (7, 8):
        n = len(race_info(race_id)["horses"])
        for j in range(1, n + 1):
            time.sleep(SLEEP)
            html = _get(f"{BASE}/odds/odds_get_form.html?type={pt}&race_id={race_id}&jiku={j}").decode(
                "utf-8", "replace")
            table.update(_combo_page(html, pt))
    else:
        html = _get(f"{BASE}/odds/index.html?type={pt}&race_id={race_id}").decode("utf-8", "replace")
        table = _combo_page(html, pt)
    if not table:
        raise SystemExit(f"組み合わせオッズが取れなかった race_id={race_id} type={type_}")
    return {"odds": {str(type_): table}, "official_datetime": _stamp()}


ROW_CLASS = {"Tansho": "単勝", "Fukusho": "複勝", "Wakuren": "枠連", "Umaren": "馬連",
             "Wide": "ワイド", "Umatan": "馬単", "Fuku3": "3連複", "Tan3": "3連単"}
ORDERED = {"馬単", "3連単"}
SCRATCH = ("除外", "取消")
LEGS = {"単勝": 1, "複勝": 1, "枠連": 2, "馬連": 2, "ワイド": 2, "馬単": 2, "3連複": 3, "3連単": 3}


def race_result(race_id):
    """着順と払戻。返り値の形は fetch_result.race_result と同じ。"""
    html = _get(f"{BASE}/race/result.html?race_id={race_id}").decode("utf-8", "replace")
    payouts = {}
    for body in re.findall(r"<table[^>]*Payout_Detail_Table[^>]*>(.*?)</table>", html, re.S):
        for cls, row in re.findall(r'<tr class="(\w+)">(.*?)</tr>', body, re.S):
            kind = ROW_CLASS.get(cls)
            # 地方のページは <td  class="Result"> のように空白が2つ入る
            res = re.search(r'<td\s+class="Result">(.*?)</td>', row, re.S)
            pay = re.search(r'<td\s+class="Payout">(.*?)</td>', row, re.S)
            nin = re.search(r'<td\s+class="Ninki">(.*?)</td>', row, re.S)
            if not (kind and res and pay):
                continue
            uls = re.findall(r"<ul>(.*?)</ul>", res.group(1), re.S)
            if uls:
                combos = [[int(x) for x in re.findall(r"<span>\s*(\d+)\s*</span>", ul)] for ul in uls]
            else:
                nums = [int(x) for x in re.findall(r"<span>\s*(\d+)\s*</span>", res.group(1))]
                k = LEGS[kind]
                combos = [nums[i:i + k] for i in range(0, len(nums), k)]
            yens = [int(re.sub(r"[^\d]", "", y)) for y in re.split(r"<br\s*/?>", pay.group(1))
                    if re.search(r"\d", y)]
            ninki = [int(x) for x in re.findall(r"(\d+)人気", nin.group(1) if nin else "")]
            d = payouts.setdefault(kind, {})
            for i, nums in enumerate(c for c in combos if c):
                if i < len(yens):
                    seq = nums if kind in ORDERED else sorted(nums)
                    d["".join(f"{n:02d}" for n in seq)] = {"yen": yens[i],
                                                         "ninki": ninki[i] if i < len(ninki) else None}

    order, scratched = [], []
    main = re.search(r'id="All_Result_Table"(.*?)</table>', html, re.S)
    for row in re.findall(r"<tr\s*>(.*?)</tr>", main.group(1) if main else "", re.S):
        rank = re.search(r'<div class="Rank">\s*([^<]*?)\s*</div>', row)
        nums = re.findall(r'<td class="Num[^"]*">\s*<div>\s*(\d+)\s*</div>', row)
        name = re.search(r'class="Horse_Name">.*?title="([^"]+)"', row, re.S)
        if not (rank and len(nums) >= 2):
            continue
        umaban, label = int(nums[1]), rank.group(1)
        nm = name.group(1) if name else ""
        nin = re.search(r'class="OddsPeople"[^>]*>\s*(\d+)\s*<', row)
        # 単勝オッズの span は人気上位にしかクラスが付かないので td 側で拾う（JRAと同じ）
        od = re.search(r'<td class="Odds[^"]*Txt_R"[^>]*>\s*<span[^>]*>\s*([\d.,]+)\s*</span>', row)
        if label.isdigit():
            order.append({"chaku": int(label), "waku": int(nums[0]), "umaban": umaban, "name": nm,
                          "ninki": int(nin.group(1)) if nin else None,
                          "odds": float(od.group(1).replace(",", "")) if od else None})
        elif any(k in label for k in SCRATCH):
            scratched.append({"umaban": umaban, "name": nm, "reason": label})
    order.sort(key=lambda r: r["chaku"])
    return {"race_id": race_id, "payouts": payouts, "order": order,
            "scratched": scratched, "finished": bool(payouts)}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("races")
    a.add_argument("--date", required=True)
    b = sub.add_parser("odds")
    b.add_argument("--race", required=True)
    args = ap.parse_args()
    if args.cmd == "races":
        for rid, label in list_races(args.date).items():
            print(rid, NAR_JYO.get(rid[4:6], rid[4:6]), label)
    else:
        info = race_info(args.race)
        print(info["name"], info["condition"])
        tf = odds_api(args.race, 1)["odds"]
        for u, nm in sorted(info["horses"].items()):
            t = tf["1"].get(f"{u:02d}", ["-", "", "-"])
            f = tf["2"].get(f"{u:02d}", ["-", "-"])
            print(f"  {u:>2} {nm:<14} 単{t[0]:>6} ({t[2]}人気)  複{f[0]}-{f[1]}")


if __name__ == "__main__":
    sys.exit(main())
