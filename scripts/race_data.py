#!/usr/bin/env python3
"""レース結果ページ1枚から、モデル学習用の1行×出走頭数を作る。

`fetch_result.py` は買い目の的中判定が目的なので着順・払戻しか取らない。
こちらは**オッズを使わない確率モデル**を作るための素材集めで、走破タイム・
上がり3F・通過順・馬体重・斤量・騎手・馬場状態まで取る。

なぜ別ファイルにするか: fetch_result.py は毎週の精算で使っている。壊すと
その日の収支が出せなくなるので触らない。

  from race_data import race_rows
  rows = race_rows("202606040611")
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch_odds import JYO, _get   # noqa: E402

COLS = ["race_id", "date", "venue", "race_no", "race_name", "surface", "distance",
        "turn", "weather", "going", "race_class", "field_size", "prize1",
        "chaku", "waku", "umaban", "horse", "sex", "age", "kinryo", "jockey",
        "time_sec", "margin", "ninki", "odds", "agari", "passage", "trainer",
        "weight", "weight_diff", "status"]

SCRATCH = ("除外", "取消", "中止")


def _txt(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).replace("&nbsp;", " ").strip()


def _sec(t):
    """1:23.4 → 83.4 秒。取れなければ None。"""
    m = re.match(r"(?:(\d+):)?(\d+)\.(\d)$", (t or "").strip())
    if not m:
        return None
    mi = int(m.group(1) or 0)
    return round(mi * 60 + int(m.group(2)) + int(m.group(3)) / 10, 1)


def _num(s):
    m = re.search(r"-?\d+(?:\.\d+)?", (s or "").replace(",", ""))
    return float(m.group()) if m else None


def race_rows(race_id):
    html = _get(f"https://race.netkeiba.com/race/result.html?race_id={race_id}").decode("utf-8", "replace")
    def block(name):
        m = re.search(name + r'"[^>]*>(.*?)</div>', html, re.S)
        return _txt(m.group(1)) if m else ""

    d1, d2 = block("RaceData01"), block("RaceData02")
    nm = re.search(r'class="RaceName"[^>]*>\s*([^<\n]+)', html)

    course = re.search(r"(芝|ダ|障)\s*(\d+)m\s*\(?\s*(右|左|直線)?", d1)
    base = {
        "race_id": race_id,
        "date": "",                                  # 呼び出し側が入れる
        "venue": JYO.get(race_id[4:6], ""),
        "race_no": int(race_id[10:12]),
        "race_name": _txt(nm.group(1)) if nm else "",
        "surface": course.group(1) if course else "",
        "distance": int(course.group(2)) if course else None,
        "turn": (course.group(3) or "") if course else "",
        "weather": (re.search(r"天候:\s*(\S+)", d1).group(1) if re.search(r"天候:\s*(\S+)", d1) else ""),
        "going": (re.search(r"馬場:\s*(\S+)", d1).group(1) if re.search(r"馬場:\s*(\S+)", d1) else ""),
        "race_class": d2,
        "field_size": (int(re.search(r"(\d+)頭", d2).group(1)) if re.search(r"(\d+)頭", d2) else None),
        # 本賞金は「6700,2700,1700,1000,670万円」と1〜5着分がカンマ区切り。
        # 1着分だけ取る（カンマを桁区切りと誤読しないこと）。単位は万円。
        "prize1": (float(re.search(r"本賞金:(\d+)", d2).group(1)) if re.search(r"本賞金:(\d+)", d2) else None),
    }

    out = []
    for row in re.findall(r'<tr[^>]*class="[^"]*HorseList[^"]*"[^>]*>(.*?)</tr>', html, re.S):
        # クラス名が重複する（Time が3つある）ので位置で取る
        tds = [_txt(v) for v in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(tds) < 11:
            continue
        label = tds[0]
        sexage = re.match(r"([牡牝セせん]+)\s*(\d+)", tds[4] or "")
        wt = re.match(r"(\d+)\s*\(([-+]?\d+)\)", tds[14] if len(tds) > 14 else "")
        r = dict(base)
        r.update({
            "chaku": int(label) if label.isdigit() else None,
            "status": "" if label.isdigit() else label,
            "waku": int(tds[1]) if tds[1].isdigit() else None,
            "umaban": int(tds[2]) if tds[2].isdigit() else None,
            "horse": tds[3],
            "sex": sexage.group(1) if sexage else "",
            "age": int(sexage.group(2)) if sexage else None,
            "kinryo": _num(tds[5]),
            "jockey": tds[6],
            "time_sec": _sec(tds[7]),
            "margin": tds[8],
            "ninki": int(tds[9]) if tds[9].isdigit() else None,
            "odds": _num(tds[10]),
            "agari": _num(tds[11]) if len(tds) > 11 else None,
            # 通過順(PassageRate)はこのページではJS描画で、HTMLには入っていない。
            # 列は残すが常に空。必要になったら別ページから取る。
            "passage": tds[12] if len(tds) > 12 else "",
            "trainer": tds[13] if len(tds) > 13 else "",
            "weight": int(wt.group(1)) if wt else None,
            "weight_diff": int(wt.group(2)) if wt else None,
        })
        if r["umaban"] is None:
            continue
        out.append(r)
    return out


if __name__ == "__main__":
    import json
    for r in race_rows(sys.argv[1])[:3]:
        print(json.dumps(r, ensure_ascii=False))
