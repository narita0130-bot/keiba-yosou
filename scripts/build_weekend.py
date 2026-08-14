#!/usr/bin/env python3
"""指定日の全レースについて、出走馬・騎手・オッズを1本のHTMLにまとめる。

枠順確定前でも動く。確定前は netkeiba の出馬表が五十音順・枠/馬番が空欄になるため、
その旨をシート上に明記し、オッズは「予想オッズ」として扱う（馬番ではなく
出馬表の並び順に対応しているため、確定後の馬番とは無関係）。

  python3 scripts/build_weekend.py --date 20260815 --date 20260816 --out /tmp/weekend.html
"""
import argparse
import html
import time
from datetime import datetime, timedelta, timezone

from fetch_odds import JYO, TYPE_TAN_FUKU, list_races, odds_api, race_info

JST = timezone(timedelta(hours=9))

CSS = """
@page { size: A4 portrait; margin: 10mm 8mm 12mm 8mm; }
* { box-sizing: border-box; }
body { font-family: "IPAGothic", "IPAPGothic", sans-serif; font-size: 8pt;
       color: #14171a; margin: 0; line-height: 1.4; }
h1 { font-size: 15pt; margin: 0 0 2mm; }
h2.day { font-size: 12pt; margin: 6mm 0 2mm; padding: 1.2mm 2mm;
         background: #14171a; color: #fff; page-break-before: always; }
h2.day:first-of-type { page-break-before: avoid; }
.sub { font-size: 7.4pt; color: #5b636a; margin: 0 0 1mm; }
.warn { border: .8pt solid #c0392b; background: #fdf2f0; color: #922b21;
        padding: 2mm; margin: 3mm 0 4mm; font-size: 7.8pt; }
.warn b { font-size: 8.4pt; }
table { width: 100%; border-collapse: collapse; }
th, td { border: .4pt solid #c8ced3; padding: .6mm 1mm; }
th { background: #eef1f3; font-weight: bold; font-size: 7.2pt; }
td.num, th.num { text-align: right; }
td.c, th.c { text-align: center; }
.idx { margin: 0 0 4mm; }
.idx td, .idx th { padding: .5mm 1mm; font-size: 7.2pt; }
.race { page-break-inside: avoid; margin-bottom: 4.5mm; }
.race h3 { font-size: 9.5pt; margin: 0 0 .6mm; padding-bottom: .6mm;
           border-bottom: 1pt solid #14171a; }
.race h3 .rid { float: right; font-size: 6.6pt; color: #8b9299; font-weight: normal; }
.cond { font-size: 7pt; color: #5b636a; margin: 0 0 1.2mm; }
tr.top3 td { background: #fdf6e3; font-weight: bold; }
.foot { margin-top: 4mm; padding-top: 1.5mm; border-top: .4pt solid #c8ced3;
        font-size: 7pt; color: #8b9299; }
"""


def esc(s):
    return html.escape(str(s))


def collect(date):
    """1開催日分のレース情報とオッズをまとめて取得する。"""
    out = []
    for rid in list_races(date):
        info = race_info(rid)
        try:
            odds = odds_api(rid, TYPE_TAN_FUKU)
            tan, stamp = odds["odds"].get("1", {}), odds["official_datetime"]
        except SystemExit:
            tan, stamp = {}, ""
        out.append({"rid": rid, "info": info, "tan": tan, "stamp": stamp})
        time.sleep(0.5)
    return out


def render_race(entry):
    info, tan = entry["info"], entry["tan"]
    rid = entry["rid"]
    label = f"{JYO.get(rid[4:6], '')}{int(rid[10:12])}R"
    confirmed = info["draw_confirmed"]
    out = ['<section class="race">']
    out.append(f'<h3><span class="rid">{esc(rid)}</span>{esc(label)} {esc(info["name"])}</h3>')
    out.append(f'<p class="cond">{esc(info["condition"])} ／ {esc(info["class"])}</p>')

    head = '<th class="c">馬番</th>' if confirmed else '<th class="c">並び</th>'
    waku = '<th class="c">枠</th>' if confirmed else ""
    out.append(f'<table><thead><tr>{waku}{head}<th>馬名</th><th class="c">性齢</th>'
               '<th class="num">斤量</th><th>騎手</th><th>厩舎</th>'
               '<th class="num">オッズ</th><th class="num">人気</th></tr></thead><tbody>')

    def sort_key(r):
        o = tan.get(str(r["umaban"])) or tan.get(f"{r['umaban']:02d}")
        return int(o[2]) if o and o[2] else 99

    for h in sorted(info["rows"], key=sort_key):
        o = tan.get(str(h["umaban"])) or tan.get(f"{h['umaban']:02d}")
        ninki = int(o[2]) if o and o[2] else None
        cls = ' class="top3"' if ninki and ninki <= 3 else ""
        wk = f'<td class="c">{esc(h["waku"])}</td>' if confirmed else ""
        out.append(
            f'<tr{cls}>{wk}<td class="c">{h["umaban"]}</td><td>{esc(h["name"])}</td>'
            f'<td class="c">{esc(h["barei"])}</td><td class="num">{esc(h["kinryo"])}</td>'
            f'<td>{esc(h["jockey"])}</td><td>{esc(h["trainer"])}</td>'
            f'<td class="num">{esc(o[0]) if o else "-"}</td>'
            f'<td class="num">{ninki if ninki else "-"}</td></tr>')
    out.append("</tbody></table></section>")
    return "\n".join(out)


def render_day(date, entries):
    d = datetime.strptime(date, "%Y%m%d")
    wd = "月火水木金土日"[d.weekday()]
    confirmed = all(e["info"]["draw_confirmed"] for e in entries)
    stamps = sorted({e["stamp"] for e in entries if e["stamp"]})
    out = [f'<h2 class="day">{d.year}年{d.month}月{d.day}日({wd})　{len(entries)}レース</h2>']

    if not confirmed:
        out.append(
            '<p class="warn"><b>⚠ この開催日は枠順が未確定です。</b><br>'
            'netkeiba の出馬表がまだ五十音順で、枠番・馬番が空欄のため「出走順」は取得できません。'
            '「並び」列は出馬表の掲載順（五十音順）に振られた通し番号で、<b>確定後の馬番とは一致しません</b>。'
            'オッズも馬券発売前の予想オッズであり、この並び順に対応しています。'
            '枠順確定後に取り直せば、馬番付きの正式な出馬表とオッズに差し替えられます。</p>')

    out.append('<table class="idx"><thead><tr><th>R</th><th>レース名</th><th>発走</th>'
               '<th>コース</th><th class="num">頭数</th><th>1番人気</th>'
               '</tr></thead><tbody>')
    for e in entries:
        info, rid = e["info"], e["rid"]
        cond = info["condition"].split("/")
        start = cond[0].strip() if cond else ""
        course = cond[1].strip() if len(cond) > 1 else ""
        fav = ""
        for h in info["rows"]:
            o = e["tan"].get(str(h["umaban"])) or e["tan"].get(f"{h['umaban']:02d}")
            if o and o[2] == "1":
                fav = f'{h["name"]} ({o[0]})'
        out.append(f'<tr><td class="c">{JYO.get(rid[4:6], "")}{int(rid[10:12])}</td>'
                   f'<td>{esc(info["name"])}</td><td>{esc(start)}</td><td>{esc(course)}</td>'
                   f'<td class="num">{len(info["rows"])}</td><td>{esc(fav)}</td></tr>')
    out.append("</tbody></table>")

    if stamps:
        out.append(f'<p class="sub">オッズ確定時刻：{esc(stamps[0])} 〜 {esc(stamps[-1])}</p>')
    out += [render_race(e) for e in entries]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", action="append", required=True, help="YYYYMMDD（複数可）")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    body = [f'<h1>中央競馬 週末まとめ（出走馬・オッズ）</h1>',
            f'<p class="sub">netkeiba 公開情報より作成　{esc(now)} JST 時点</p>']
    for date in args.date:
        entries = collect(date)
        body.append(render_day(date, entries))
        print(f"  {date}: {len(entries)}レース取得")
    body.append('<p class="foot">本紙は公開情報の集計であり、的中を保証するものではありません。'
                'オッズは発走まで変動します。</p>')

    doc = ('<!doctype html><html lang="ja"><head><meta charset="utf-8">'
           f'<title>中央競馬 週末まとめ</title><style>{CSS}</style></head>'
           f'<body>{"".join(body)}</body></html>')
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
