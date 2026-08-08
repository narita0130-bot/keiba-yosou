#!/usr/bin/env python3
"""予想noteの印をもとに「出馬表・オッズ・買い目」の1枚ものHTML/PDFを組み立てる。

レース構成と印・買い目は JSON で渡す（例: data/2026-08-08.sheet.json）。
netkeiba から出馬表と最新オッズを取得し、HTML を出力する。
PDF 化は Chromium の --print-to-pdf に渡す（README 参照）。

  python3 scripts/build_sheet.py --spec data/2026-08-08.sheet.json --out /tmp/sheet.html
"""
import argparse
import html
import json
import time
from datetime import datetime, timedelta, timezone

from fetch_odds import BET_TYPES, JYO, TYPE_TAN_FUKU, _key, odds_api, race_info

JST = timezone(timedelta(hours=9))

MARK_CLASS = {"◎": "m-honmei", "◯": "m-taiko", "▲": "m-tanana", "☆": "m-hoshi", "穴": "m-ana"}

CSS = """
@page { size: A4 portrait; margin: 11mm 9mm 13mm 9mm; }
* { box-sizing: border-box; }
body { font-family: "IPAGothic", "IPAPGothic", sans-serif; font-size: 8.4pt;
       color: #14171a; margin: 0; line-height: 1.45; }
h1 { font-size: 15pt; margin: 0 0 2mm; letter-spacing: .02em; }
.sub { font-size: 7.6pt; color: #5b636a; margin: 0 0 1mm; }
.legend { font-size: 7.4pt; color: #5b636a; border-top: .4pt solid #c8ced3;
          border-bottom: .4pt solid #c8ced3; padding: 1.2mm 0; margin: 2.5mm 0 4mm; }
.race { page-break-inside: avoid; margin-bottom: 6mm; }
.race h2 { font-size: 10.5pt; margin: 0 0 .8mm; padding-bottom: .8mm;
           border-bottom: 1.1pt solid #14171a; }
.race h2 .stars { color: #c0392b; font-size: 9pt; margin-left: 1.5mm; }
.race h2 .rid { float: right; font-size: 7pt; color: #8b9299; font-weight: normal; }
.cond { font-size: 7.4pt; color: #5b636a; margin: 0 0 1.6mm; }
table { width: 100%; border-collapse: collapse; }
th, td { border: .4pt solid #c8ced3; padding: .7mm 1.1mm; }
th { background: #eef1f3; font-weight: bold; font-size: 7.4pt; }
td.num, th.num { text-align: right; }
td.c, th.c { text-align: center; }
tr.marked td { background: #fdf6e3; }
tr.fav td { font-weight: bold; }
.mark { font-weight: bold; font-size: 9.5pt; }
.m-honmei { color: #c0392b; } .m-taiko { color: #1f6fb2; }
.m-tanana { color: #1e8449; } .m-hoshi { color: #b7791f; } .m-ana { color: #6c3483; }
.bets { margin-top: 1.8mm; }
.bets caption { caption-side: top; text-align: left; font-size: 7.8pt;
                font-weight: bold; padding: 0 0 .8mm; }
.bets td, .bets th { padding: .6mm 1.1mm; }
.src-note { background: #eaf3fa; } .src-ref { background: #f4f4f4; }
.memo { font-size: 7.4pt; color: #5b636a; margin: 1.2mm 0 0; }
.foot { margin-top: 4mm; padding-top: 1.5mm; border-top: .4pt solid #c8ced3;
        font-size: 7pt; color: #8b9299; }
"""


def esc(s):
    return html.escape(str(s))


def render_race(spec, info, tan, fuku, stamp):
    marks = {int(k): v for k, v in spec.get("marks", {}).items()}
    rid = spec["race_id"]
    label = f"{JYO.get(rid[4:6], '')}{int(rid[10:12])}R"
    out = ['<section class="race">']
    stars = f'<span class="stars">{esc(spec["stars"])}</span>' if spec.get("stars") else ""
    out.append(f'<h2><span class="rid">{esc(rid)}</span>{esc(label)} {esc(info["name"])}{stars}</h2>')
    out.append(f'<p class="cond">{esc(info["condition"])} ／ {esc(info["class"])}</p>')

    out.append('<table><thead><tr>'
               '<th class="c">印</th><th class="c">枠</th><th class="c">馬番</th><th>馬名</th>'
               '<th class="c">性齢</th><th class="num">斤量</th><th>騎手</th><th>厩舎</th>'
               '<th class="num">単勝</th><th class="num">人気</th><th class="num">複勝</th>'
               '</tr></thead><tbody>')
    for h in sorted(info["rows"], key=lambda r: r["umaban"]):
        n = h["umaban"]
        key = f"{n:02d}"
        t, f = tan.get(key), fuku.get(key)
        mark = marks.get(n, "")
        cls = []
        if mark:
            cls.append("marked")
        if t and t[2] == "1":
            cls.append("fav")
        tr = f' class="{" ".join(cls)}"' if cls else ""
        mk = f'<span class="mark {MARK_CLASS.get(mark, "")}">{esc(mark)}</span>' if mark else ""
        out.append(
            f"<tr{tr}><td class=\"c\">{mk}</td><td class=\"c\">{h['waku']}</td>"
            f"<td class=\"c\">{n}</td><td>{esc(h['name'])}</td>"
            f"<td class=\"c\">{esc(h['barei'])}</td><td class=\"num\">{esc(h['kinryo'])}</td>"
            f"<td>{esc(h['jockey'])}</td><td>{esc(h['trainer'])}</td>"
            f"<td class=\"num\">{esc(t[0]) if t else '-'}</td>"
            f"<td class=\"num\">{esc(t[2]) if t else '-'}</td>"
            f"<td class=\"num\">{esc(f'{f[0]}-{f[1]}') if f else '-'}</td></tr>")
    out.append("</tbody></table>")

    bets = spec.get("bets", [])
    if bets:
        out.append('<table class="bets"><caption>買い目</caption><thead><tr>'
                   '<th>出典</th><th>式別</th><th>買い目</th><th>組み合わせ</th>'
                   '<th class="num">オッズ</th><th class="num">人気</th></tr></thead><tbody>')
        cache = {}
        for b in bets:
            kind, legs, src = b["type"], b["legs"], b.get("source", "note")
            type_, key = _key(kind, legs)
            if type_ not in cache:
                cache[type_] = odds_api(rid, type_)
                time.sleep(0.6)
            row = cache[type_]["odds"][str(type_)].get(key)
            names = "-".join(info["horses"].get(int(key[i:i + 2]), "?") for i in range(0, len(key), 2))
            src_label = "note記載" if src == "note" else "参考"
            out.append(
                f'<tr class="src-{"note" if src == "note" else "ref"}">'
                f'<td class="c">{src_label}</td><td>{esc(kind)}</td><td>{esc(legs)}</td>'
                f'<td>{esc(names)}</td>'
                f'<td class="num">{esc(row[0]) if row else "-"}</td>'
                f'<td class="num">{esc(row[2]) if row else "-"}</td></tr>')
        out.append("</tbody></table>")

    if spec.get("memo"):
        out.append(f'<p class="memo">{esc(spec["memo"])}</p>')
    out.append("</section>")
    return "\n".join(out)


def render_assumed(entries, fetched):
    """note に想定オッズの記載があった馬について、現在の単勝と並べる。"""
    out = ['<table class="bets"><caption>note の想定オッズと現在オッズ</caption>'
           '<thead><tr><th>レース</th><th>馬名</th><th class="num">note想定</th>'
           '<th class="num">現在</th><th class="num">差</th><th>評</th>'
           '</tr></thead><tbody>']
    for e in entries:
        rid, n = e["race_id"], e["umaban"]
        info, tan = fetched[rid]
        cur = tan.get(f"{n:02d}")
        label = f"{JYO.get(rid[4:6], '')}{int(rid[10:12])}R"
        if not cur:
            out.append(f'<tr><td>{esc(label)}</td><td>{esc(info["horses"].get(n, "?"))}</td>'
                       f'<td class="num">{e["assumed"]}</td><td class="num">-</td>'
                       f'<td class="num">-</td><td>-</td></tr>')
            continue
        now = float(cur[0])
        diff = now - e["assumed"]
        judge = "妙味増" if diff > 0.5 else ("想定より人気" if diff < -0.5 else "ほぼ想定通り")
        out.append(f'<tr><td>{esc(label)}</td><td>{esc(info["horses"].get(n, "?"))}</td>'
                   f'<td class="num">{e["assumed"]}</td><td class="num">{cur[0]}</td>'
                   f'<td class="num">{diff:+.1f}</td><td>{esc(judge)}</td></tr>')
    out.append("</tbody></table>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    spec = json.load(open(args.spec, encoding="utf-8"))
    parts, stamps, fetched = [], [], {}
    for race in spec["races"]:
        info = race_info(race["race_id"])
        data = odds_api(race["race_id"], TYPE_TAN_FUKU)
        stamps.append(data["official_datetime"])
        fetched[race["race_id"]] = (info, data["odds"]["1"])
        parts.append(render_race(race, info, data["odds"]["1"], data["odds"]["2"],
                                 data["official_datetime"]))
        time.sleep(0.8)
    if spec.get("assumed_odds"):
        parts.insert(0, render_assumed(spec["assumed_odds"], fetched))

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    body = [
        f'<h1>{esc(spec["title"])}</h1>',
        f'<p class="sub">印の出典：{esc(spec["source"])}</p>',
        f'<p class="sub">オッズ：netkeiba 公開オッズ（確定時刻 {esc(min(stamps))} 〜 {esc(max(stamps))}）'
        f' ／ 本紙作成 {esc(now)} JST</p>',
        '<p class="legend">'
        '★★★＝勝負レース（満額）／★★＝準勝負（半額）／★＝妙味少し　'
        '網掛けの行は印のついた馬、太字は1番人気。'
        '「note記載」はnote本文にあった買い目、「参考」は印から機械的に組んだもので'
        'note の推奨ではありません。オッズは発走まで変動します。</p>',
    ]
    body += parts
    body.append('<p class="foot">本紙は公開オッズの集計であり、的中を保証するものではありません。'
                '最終的な購入判断はご自身でお願いします。</p>')

    doc = ("<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">"
           f"<title>{esc(spec['title'])}</title><style>{CSS}</style></head>"
           f"<body>{''.join(body)}</body></html>")
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"wrote {args.out} ({len(spec['races'])} races)")


if __name__ == "__main__":
    main()
