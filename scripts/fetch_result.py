#!/usr/bin/env python3
"""netkeiba のレース結果ページから、着順と全式別の払戻を取得する。

払戻は「組番 → 払戻金(円/100円あたり)」の辞書で返す。組番の表記は
fetch_odds.py と揃える（ゼロパディング2桁、着順ありは並び順を保持）。

  python3 scripts/fetch_result.py --race 202601020509
"""
import argparse
import re
import sys

from fetch_odds import JYO, _get, _strip

# 結果ページの行クラス → 式別名（fetch_odds.py の BET_TYPES と同じ呼び方）
ROW_CLASS = {
    "Tansho": "単勝",
    "Fukusho": "複勝",
    "Wakuren": "枠連",
    "Umaren": "馬連",
    "Wide": "ワイド",
    "Umatan": "馬単",
    "Fuku3": "3連複",
    "Tan3": "3連単",
}
# 着順が意味を持つ式別。組番を並べ替えずに保持する。
ORDERED = {"馬単", "3連単"}
# 着順欄が数字にならない状態のうち、購入金額が返還されるもの
SCRATCH = ("除外", "取消")
# 1つの組み合わせに含まれる頭数
LEGS = {"単勝": 1, "複勝": 1, "枠連": 2, "馬連": 2, "ワイド": 2, "馬単": 2, "3連複": 3, "3連単": 3}


def _yen(s):
    return int(re.sub(r"[^\d]", "", s)) if re.search(r"\d", s) else None


def _combos(cell_html, kind):
    """Result セルから組番のリストを取り出す。

    単勝・複勝は <div><span>6</span></div> の連続、それ以外は <ul><li> の並び。
    複勝は3頭ぶんが1セルに入るので、頭数で区切って複数の組にする。
    """
    uls = re.findall(r"<ul>(.*?)</ul>", cell_html, re.S)
    if uls:
        out = []
        for ul in uls:
            nums = [int(x) for x in re.findall(r"<span>\s*(\d+)\s*</span>", ul)]
            if nums:
                out.append(nums)
        return out
    nums = [int(x) for x in re.findall(r"<span>\s*(\d+)\s*</span>", cell_html)]
    n = LEGS.get(kind, 1)
    return [nums[i:i + n] for i in range(0, len(nums), n)] if nums else []


def _key(kind, nums):
    seq = nums if kind in ORDERED else sorted(nums)
    return "".join(f"{n:02d}" for n in seq)


def race_result(race_id):
    """着順と払戻を返す。

    payouts: {式別: {組番キー: {"yen": 払戻円, "ninki": 人気}}}
    order:   [{"chaku": 着順, "umaban": 馬番, "name": 馬名}, ...]
    """
    html = _get(f"https://race.netkeiba.com/race/result.html?race_id={race_id}").decode("utf-8", "replace")

    payouts = {}
    for body in re.findall(r"<table[^>]*Payout_Detail_Table[^>]*>(.*?)</table>", html, re.S):
        for cls, row in re.findall(r'<tr class="(\w+)">(.*?)</tr>', body, re.S):
            kind = ROW_CLASS.get(cls)
            if not kind:
                continue
            res = re.search(r'<td class="Result">(.*?)</td>', row, re.S)
            pay = re.search(r'<td class="Payout">(.*?)</td>', row, re.S)
            nin = re.search(r'<td class="Ninki">(.*?)</td>', row, re.S)
            if not (res and pay):
                continue
            combos = _combos(res.group(1), kind)
            yens = [_yen(x) for x in re.split(r"<br\s*/?>", pay.group(1))]
            yens = [y for y in yens if y is not None]
            ninki = [int(x) for x in re.findall(r"(\d+)人気", nin.group(1) if nin else "")]
            d = payouts.setdefault(kind, {})
            for i, nums in enumerate(combos):
                if i < len(yens):
                    d[_key(kind, nums)] = {"yen": yens[i],
                                           "ninki": ninki[i] if i < len(ninki) else None}

    # 着順テーブル。1列目が着順、3列目が馬番、4列目に馬名。
    # 中止・除外は着順が数字にならないので落とす。
    order, scratched = [], []
    # 着順テーブルを先に切り出すと、行内に入れ子の <table> があるページで
    # 非貪欲マッチが途中で止まり上位数頭しか拾えない（9/19 阪神9Rで5頭に切れた）。
    # HorseList 行を本文から直接拾う。
    for row in re.findall(r'<tr[^>]*class="[^"]*HorseList[^"]*"[^>]*>(.*?)</tr>', html, re.S):
        rank = re.search(r'<div class="Rank">\s*([^<]*?)\s*</div>', row)
        nums = re.findall(r'<td class="Num[^"]*">\s*<div>\s*(\d+)\s*</div>', row)
        name = re.search(r'<span class="HorseNameSpan">\s*([^<]+?)\s*</span>', row)
        if not (rank and len(nums) >= 2):
            continue
        umaban, label = int(nums[1]), rank.group(1)
        nm = _strip(name.group(1)) if name else ""
        # 人気と単勝オッズ。クラス名が紛らわしく OddsPeople が人気、Odds_Ninki がオッズ。
        nin = re.search(r'<span[^>]*class="OddsPeople"[^>]*>\s*(\d+)\s*</span>', row)
        # 単勝オッズのspanは人気上位以外クラスが付かないので td 側で拾う
        od = re.search(r'<td class="Odds[^"]*Txt_R"[^>]*>\s*<span[^>]*>\s*([\d.,]+)\s*</span>', row)
        if label.isdigit():
            order.append({"chaku": int(label), "waku": int(nums[0]),
                          "umaban": umaban, "name": nm,
                          "ninki": int(nin.group(1)) if nin else None,
                          "odds": float(od.group(1).replace(",", "")) if od else None})
        elif any(k in label for k in SCRATCH):
            # 除外・取消は全額返還。買い目に1頭でも含まれていれば的中判定の対象外。
            scratched.append({"umaban": umaban, "name": nm, "reason": label})
    order.sort(key=lambda r: r["chaku"])

    return {"race_id": race_id, "payouts": payouts, "order": order,
            "scratched": scratched, "finished": bool(payouts)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--race", required=True)
    args = ap.parse_args()
    r = race_result(args.race)
    rid = args.race
    print(f"# {JYO.get(rid[4:6], '')}{int(rid[10:12])}R  {rid}")
    if not r["finished"]:
        raise SystemExit("結果未確定（払戻が取得できません）")
    if r["scratched"]:
        print("\n## 除外・取消（返還対象）")
        for h in r["scratched"]:
            print(f"  {h['reason']}  {h['umaban']:>2}  {h['name']}")
    print("\n## 着順")
    for h in r["order"][:5]:
        pop = f"{h['odds']:>7.1f}倍 {h['ninki']:>2}人気" if h.get("odds") else ""
        print(f"  {h['chaku']}着  {h['umaban']:>2}  {h['name']:<16}{pop}")
    print("\n## 払戻（100円あたり）")
    for kind, d in r["payouts"].items():
        for key, v in d.items():
            sep = "→" if kind in ORDERED else "-"
            nums = sep.join(str(int(key[i:i + 2])) for i in range(0, len(key), 2))
            print(f"  {kind:<6}{nums:<12}{v['yen']:>8,}円  {v['ninki']}人気")


if __name__ == "__main__":
    sys.exit(main())
