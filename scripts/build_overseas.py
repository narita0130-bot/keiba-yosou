#!/usr/bin/env python3
"""JRA が馬券を発売する海外レースの出馬表・オッズ・予想を1枚にまとめる。

国内レースと違い netkeiba のオッズAPIが使えないため、出馬表・オッズは
JRA報道室のPDFや JRA-VAN Ver.World の画面から手で起こした JSON を入力にする。

  python3 scripts/build_overseas.py --spec ../data/2026-08-16_jlm.json --out /tmp/jlm.html
"""
import argparse
import html
import json

MARK_CLASS = {"◎": "m-honmei", "◯": "m-taiko", "▲": "m-tanana", "△": "m-hoshi", "穴": "m-ana"}

CSS = """
@page { size: A4 portrait; margin: 12mm 10mm 14mm 10mm; }
* { box-sizing: border-box; }
body { font-family: "IPAGothic", "IPAPGothic", sans-serif; font-size: 8.6pt;
       color: #14171a; margin: 0; line-height: 1.5; }
h1 { font-size: 16pt; margin: 0 0 1.5mm; }
.race { font-size: 8.4pt; color: #34404a; margin: 0 0 .6mm; }
.race b { color: #14171a; }
.sale { font-size: 7.4pt; color: #5b636a; margin: 1.5mm 0 0; }
.src { font-size: 7.2pt; color: #8b9299; margin: 1.5mm 0 4mm;
       border-top: .4pt solid #c8ced3; padding-top: 1.2mm; }
h2 { font-size: 10.5pt; margin: 5mm 0 1.5mm; padding-bottom: .7mm;
     border-bottom: 1.1pt solid #14171a; }
table { width: 100%; border-collapse: collapse; }
th, td { border: .4pt solid #c8ced3; padding: .8mm 1.2mm; }
th { background: #eef1f3; font-weight: bold; font-size: 7.4pt; }
td.num, th.num { text-align: right; }
td.c, th.c { text-align: center; }
tr.marked td { background: #fdf6e3; }
tr.jpn td { border-top: .9pt solid #c0392b; border-bottom: .9pt solid #c0392b; }
tr.jpn td:first-child { border-left: .9pt solid #c0392b; }
tr.jpn td:last-child { border-right: .9pt solid #c0392b; }
.mark { font-weight: bold; font-size: 9.5pt; }
.m-honmei { color: #c0392b; } .m-taiko { color: #1f6fb2; }
.m-tanana { color: #1e8449; } .m-hoshi { color: #b7791f; } .m-ana { color: #6c3483; }
.gap-hi { color: #1e8449; font-weight: bold; }
.gap-lo { color: #c0392b; font-weight: bold; }
.pred td { vertical-align: top; }
.pred .why { font-size: 7.8pt; line-height: 1.45; }
.cmt { font-size: 7.8pt; margin: 0 0 2mm; }
.cmt b { display: block; font-size: 7.6pt; color: #5b636a; }
ul.notes { font-size: 7.4pt; color: #5b636a; margin: 1.5mm 0 0; padding-left: 4mm; }
ul.notes li { margin-bottom: .8mm; }
.foot { margin-top: 5mm; padding-top: 1.5mm; border-top: .4pt solid #c8ced3;
        font-size: 7pt; color: #8b9299; }
"""


def esc(s):
    return html.escape(str(s))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    s = json.load(open(args.spec, encoding="utf-8"))
    r = s["race"]

    out = [f'<h1>{esc(s["title"])}</h1>',
           f'<p class="race"><b>{esc(r["name"])}</b>　{esc(r["en"])}</p>',
           f'<p class="race">{esc(r["course"])}　{esc(r["cond"])}</p>',
           f'<p class="race">{esc(r["prize"])}</p>',
           f'<p class="race"><b>{esc(r["start"])}</b></p>',
           f'<p class="sale">{esc(r["sale"])}</p>',
           f'<p class="src">{esc(s["source"])}</p>']

    out.append("<h2>出馬表・オッズ</h2>")
    out.append('<table><thead><tr><th class="c">印</th><th class="c">馬番</th>'
               '<th class="c">ゲート</th><th class="c">Rt</th><th>馬名</th>'
               '<th class="c">性齢</th><th class="num">斤量</th><th>騎手</th><th>調教師</th>'
               '<th class="num">JRA単勝</th><th class="num">人気</th>'
               '<th class="num">PMU</th><th class="num">JRA/PMU</th></tr></thead><tbody>')
    for h in sorted(s["horses"], key=lambda x: x["ninki"]):
        gap = h["jra"] / h["pmu"]
        cls = [c for c in (("marked" if h.get("mark") else ""), ("jpn" if h.get("jpn") else "")) if c]
        tr = f' class="{" ".join(cls)}"' if cls else ""
        gcls = "gap-hi" if gap >= 1.3 else ("gap-lo" if gap <= 0.77 else "")
        mk = (f'<span class="mark {MARK_CLASS.get(h["mark"], "")}">{esc(h["mark"])}</span>'
              if h.get("mark") else "")
        out.append(
            f'<tr{tr}><td class="c">{mk}</td><td class="c">{h["num"]}</td>'
            f'<td class="c">{h["gate"]}</td><td class="c">{h["rt"]}</td>'
            f'<td>{esc(h["name"])}<br><span style="font-size:6.8pt;color:#8b9299">{esc(h["en"])}</span></td>'
            f'<td class="c">{esc(h["sexage"])}</td><td class="num">{esc(h["kin"])}</td>'
            f'<td>{esc(h["jockey"])}</td><td>{esc(h["trainer"])}</td>'
            f'<td class="num">{h["jra"]:.1f}</td><td class="num">{h["ninki"]}</td>'
            f'<td class="num">{h["pmu"]:.1f}</td>'
            f'<td class="num"><span class="{gcls}">{gap:.2f}</span></td></tr>')
    out.append("</tbody></table>")
    out.append('<ul class="notes">' + "".join(f"<li>{esc(n)}</li>" for n in s["notes"]) + "</ul>")

    out.append("<h2>着順予想</h2>")
    out.append('<table class="pred"><thead><tr><th class="c">予想</th><th class="c">印</th>'
               '<th>馬</th><th>根拠</th></tr></thead><tbody>')
    for p in s["prediction"]:
        mk = f'<span class="mark {MARK_CLASS.get(p["mark"], "")}">{esc(p["mark"])}</span>'
        out.append(f'<tr><td class="c">{esc(p["rank"])}</td><td class="c">{mk}</td>'
                   f'<td style="white-space:nowrap">{p["num"]} {esc(p["name"])}</td>'
                   f'<td class="why">{esc(p["why"])}</td></tr>')
    out.append("</tbody></table>")

    if s.get("comments"):
        out.append("<h2>日本馬 関係者コメント</h2>")
        for c in s["comments"]:
            out.append(f'<p class="cmt"><b>{esc(c["who"])}</b>「{esc(c["text"])}」</p>')

    out.append('<p class="foot">本紙は公開情報の集計と個人的な予想であり、的中を保証するものではありません。'
               'オッズは発走まで変動します。</p>')

    doc = ('<!doctype html><html lang="ja"><head><meta charset="utf-8">'
           f'<title>{esc(s["title"])}</title><style>{CSS}</style></head>'
           f'<body>{"".join(out)}</body></html>')
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"wrote {args.out} ({len(s['horses'])}頭)")


if __name__ == "__main__":
    main()
