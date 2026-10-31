#!/usr/bin/env python3
"""買い目CSVから「買った場合のオッズと払戻」の一覧ページ（HTML）を作る。

  python3 scripts/odds_page.py --bets <最新オッズの bets.csv> --ev data/2026-10-11.all.ev.json \
      --pick data/2026-10-11.pick.bets.csv --out page.html

- 馬番は枠色のチップで出す（出馬表の枠番を netkeiba から取る）
- --pick に入っている買い目には「30倍以下版」の印を付ける
- 賭け金は CSV の amount 列（基本100円。overlap_stake.py で200円にしたレースは札に表示）
"""
import argparse
import csv
import html
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_odds import race_info   # noqa: E402

MARK_ORDER = "◎◯▲△☆"
KIND_ORDER = {"馬連": 0, "馬単": 1, "3連複": 2}
WEEK = "月火水木金土日"

CSS = """
/* 出馬表の紙面：レースごとの札を発走順に縦に並べる。数字は等幅、馬番は枠色 */
:root{
  --bg:#f5f7f4; --card:#ffffff; --ink:#17201b; --muted:#5d6b63; --line:#d9e0db;
  --accent:#1d6a46; --accent-soft:#e3f0e8; --pick:#8a5a00; --pick-soft:#fff2d6;
  --m1:#c0392b; --m2:#1f62a8; --m3:#1e7a46; --m4:#a56a00; --m5:#6c3d93;
  --font-head:"Zen Kaku Gothic New","Hiragino Sans","Yu Gothic",sans-serif;
  --font-body:"BIZ UDPGothic","Hiragino Sans","Yu Gothic",sans-serif;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#0f1512; --card:#161e1a; --ink:#e3ebe6; --muted:#9aaba1; --line:#2b3731;
  --accent:#62c08f; --accent-soft:#1c3328; --pick:#f0b54a; --pick-soft:#33280f;
  --m1:#ff7a6b; --m2:#7fb2ff; --m3:#6fd39b; --m4:#f0b54a; --m5:#c49cf0; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0f1512; --card:#161e1a; --ink:#e3ebe6; --muted:#9aaba1; --line:#2b3731;
  --accent:#62c08f; --accent-soft:#1c3328; --pick:#f0b54a; --pick-soft:#33280f;
  --m1:#ff7a6b; --m2:#7fb2ff; --m3:#6fd39b; --m4:#f0b54a; --m5:#c49cf0; color-scheme:dark}
body{background:var(--bg);color:var(--ink);font-family:var(--font-body);font-size:15px;line-height:1.55}
.wrap{max-width:860px;margin:0 auto;padding-inline:16px;padding-block:20px 48px;display:grid;gap:18px}
h1{font-family:var(--font-head);font-weight:700;font-size:1.45rem;margin:0;text-wrap:balance}
.lead{color:var(--muted);margin:4px 0 0;max-width:62ch}
.sum{display:flex;flex-wrap:wrap;gap:8px}
.chip{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);background:var(--card);
  border-radius:999px;padding:4px 12px;font-size:.85rem}
.chip b{font-variant-numeric:tabular-nums}
.chip.pk{border-color:var(--pick);background:var(--pick-soft);color:var(--pick)}
nav.jump{display:flex;flex-wrap:wrap;gap:6px}
nav.jump a{font-size:.8rem;text-decoration:none;color:var(--accent);border:1px solid var(--line);
  border-radius:6px;padding:3px 8px;background:var(--card);font-variant-numeric:tabular-nums}
nav.jump a:focus-visible,nav.jump a:hover{border-color:var(--accent)}
section.race{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.rh{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 12px;padding:12px 14px 8px;border-bottom:1px solid var(--line)}
.rh .t{font-family:var(--font-head);font-weight:700;font-size:1.25rem;font-variant-numeric:tabular-nums}
.rh .r{font-family:var(--font-head);font-weight:700;font-size:1.05rem}
.rh .n{color:var(--muted);font-size:.9rem}
.rh .st{color:var(--accent);letter-spacing:.08em;font-size:.9rem}
.rh .up{border:1px solid var(--pick);background:var(--pick-soft);color:var(--pick);border-radius:6px;padding:0 6px;font-size:.8rem;font-weight:700}
.rh .ot{margin-left:auto;color:var(--muted);font-size:.75rem;font-variant-numeric:tabular-nums}
.marks{display:flex;flex-wrap:wrap;gap:6px 14px;padding:8px 14px 10px;font-size:.88rem}
.mk{font-weight:700}
.m1{color:var(--m1)}.m2{color:var(--m2)}.m3{color:var(--m3)}.m4{color:var(--m4)}.m5{color:var(--m5)}
.u{display:inline-grid;place-items:center;min-width:1.7em;height:1.7em;padding:0 3px;border-radius:4px;
  font-weight:700;font-size:.82rem;font-variant-numeric:tabular-nums;border:1px solid rgba(0,0,0,.25);vertical-align:middle}
.w1{background:#ffffff;color:#111}.w2{background:#1a1a1a;color:#fff}.w3{background:#d8323c;color:#fff}
.w4{background:#2b62c8;color:#fff}.w5{background:#f2d63b;color:#111}.w6{background:#2f9a4c;color:#fff}
.w7{background:#f08a24;color:#111}.w8{background:#f4a7c0;color:#111}
.tbl{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th,td{padding:7px 10px;border-top:1px solid var(--line);text-align:left;vertical-align:middle}
thead th{border-top:none;color:var(--muted);font-weight:400;font-size:.75rem;letter-spacing:.06em;background:var(--bg)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td.pay{font-weight:700}
td.kind{white-space:nowrap;color:var(--muted)}
.combo{display:flex;align-items:center;gap:4px;flex-wrap:nowrap}
.arw{color:var(--muted);font-size:.8rem}
.names{display:block;color:var(--muted);font-size:.74rem;margin-top:2px}
tr.pk td{background:var(--pick-soft)}
.badge{display:inline-block;margin-left:6px;font-size:.68rem;color:var(--pick);border:1px solid var(--pick);
  border-radius:4px;padding:0 4px;white-space:nowrap}
.foot{color:var(--muted);font-size:.8rem}
@media (prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
"""


def uma_chip(u, waku):
    w = waku.get(u)
    cls = f"w{w}" if w else "w1"
    return f'<span class="u {cls}">{u}</span>'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bets", required=True, help="最新オッズ入りの bets.csv")
    ap.add_argument("--ev", required=True)
    ap.add_argument("--pick", help="30倍以下版の bets.csv（印を付ける）")
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default=None)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.bets, encoding="utf-8-sig")))
    ev = json.load(open(args.ev))
    pick = set()
    if args.pick:
        pick = {(r["race_id"], r["bet_type"], r["combo"])
                for r in csv.DictReader(open(args.pick, encoding="utf-8-sig"))}
    marks = {r["race_id"]: r for r in ev["races"]}

    races = {}
    for r in rows:
        races.setdefault(r["race_id"], []).append(r)

    info = {}
    for rid in races:
        i = race_info(rid)
        info[rid] = {"name": i["name"], "names": i["horses"],
                     "waku": {int(x["umaban"]): int(x["waku"]) for x in i["rows"] if str(x.get("waku", "")).isdigit()}}
        time.sleep(0.5)

    order = sorted(races, key=lambda rid: (races[rid][0]["post_time"], rid))
    d = ev["date"]
    y, m, dd = d.split("-")
    import datetime as dt
    wd = WEEK[dt.date(int(y), int(m), int(dd)).weekday()]
    title = args.title or f"{int(m)}/{int(dd)} 買い目オッズ表"

    n_all = len(rows)
    yen_all = sum(int(r["amount"]) for r in rows)
    pick_rows = [r for r in rows if (r["race_id"], r["bet_type"], r["combo"]) in pick]
    n_pick = len(pick_rows)
    yen_pick = sum(int(r["amount"]) for r in pick_rows)
    times = sorted({r["odds_time"][11:16] for r in rows if r.get("odds_time")})
    t_range = f"{times[0]}〜{times[-1]}" if times else "不明"

    out = [f"<title>{html.escape(title)}</title>",
           '<link rel="preconnect" href="https://fonts.googleapis.com">',
           '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
           '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=BIZ+UDPGothic:wght@400;700&family=Zen+Kaku+Gothic+New:wght@700&display=swap">',
           f"<style>{CSS}</style>", '<main class="wrap">',
           "<header>",
           f"<h1>{int(m)}/{int(dd)}（{wd}）非馬の買い目　オッズと払戻</h1>",
           f'<p class="lead">払戻は、その組み合わせが当たった時に何円になるか（オッズ×賭け金）。'
           f'賭け金は1点100円、非馬の◎をLogicも挙げたレースだけ1点200円。'
           f'オッズは netkeiba の {t_range} 時点の値で、締切までに動く。今日は購入なし（結果の通知と記録のみ）。</p>',
           "</header>",
           '<div class="sum">',
           f'<span class="chip">レース <b>{len(order)}</b></span>',
           f'<span class="chip">全部入り <b>{n_all}点・{yen_all:,}円</b></span>',
           f'<span class="chip pk">30倍以下版 <b>{n_pick}点・{yen_pick:,}円</b></span>',
           "</div>",
           '<nav class="jump" aria-label="レースへ移動">']
    for rid in order:
        r0 = races[rid][0]
        out.append(f'<a href="#r{rid[-6:]}">{r0["post_time"]} {r0["venue"]}{r0["race_no"]}R</a>')
    out.append("</nav>")

    for rid in order:
        rs = races[rid]
        r0 = rs[0]
        mk = marks.get(rid, {})
        waku = info[rid]["waku"]
        names = info[rid]["names"]
        stars = mk.get("stars", "")
        ot = r0.get("odds_time", "")[11:16]
        amt = int(r0["amount"])
        out.append(f'<section class="race" id="r{rid[-6:]}">')
        out.append('<div class="rh">'
                   f'<span class="t">{r0["post_time"]}</span>'
                   f'<span class="r">{r0["venue"]}{r0["race_no"]}R</span>'
                   f'<span class="n">{html.escape(info[rid]["name"])}</span>'
                   f'<span class="st">{stars or "★なし"}</span>'
                   + (f'<span class="up">1点{amt}円（Logic重なり）</span>' if amt != 100 else '') +
                   f'<span class="ot">オッズ {ot} 時点</span></div>')
        mitems = sorted(mk.get("marks", {}).items(), key=lambda kv: (MARK_ORDER.index(kv[1]), int(kv[0])))
        out.append('<div class="marks">')
        for u, m_ in mitems:
            u = int(u)
            ci = MARK_ORDER.index(m_) + 1
            out.append(f'<span><span class="mk m{ci}">{m_}</span> {uma_chip(u, waku)} {html.escape(names.get(u, ""))}</span>')
        out.append("</div>")
        rs = sorted(rs, key=lambda r: (KIND_ORDER.get(r["bet_type"], 9), float(r["odds"] or 1e9)))
        lo = min(float(r["odds"]) for r in rs if r["odds"])
        hi = max(float(r["odds"]) for r in rs if r["odds"])
        out.append('<div class="tbl"><table><thead><tr><th>式別</th><th>組み合わせ</th>'
                   f'<th class="num">オッズ</th><th class="num">{amt}円→払戻</th><th class="num">人気</th></tr></thead><tbody>')
        for r in rs:
            nums = [int(x) for x in r["combo"].replace(">", "-").split("-")]
            sep = '<span class="arw">→</span>' if r["bet_type"] == "馬単" else '<span class="arw">-</span>'
            chips = sep.join(uma_chip(u, waku) for u in nums)
            nm = "・".join(names.get(u, "") for u in nums)
            is_pick = (r["race_id"], r["bet_type"], r["combo"]) in pick
            odds = float(r["odds"]) if r["odds"] else None
            pay = f"{int(round(odds * amt)):,}円" if odds else "不明"
            badge = '<span class="badge">30倍以下版</span>' if is_pick else ""
            out.append(f'<tr class="{"pk" if is_pick else ""}">'
                       f'<td class="kind">{r["bet_type"]}</td>'
                       f'<td><span class="combo">{chips}{badge}</span><span class="names">{html.escape(nm)}</span></td>'
                       f'<td class="num">{odds:.1f}</td><td class="num pay">{pay}</td>'
                       f'<td class="num">{r["ninki"] or "-"}</td></tr>' if odds else
                       f'<tr><td class="kind">{r["bet_type"]}</td><td>{chips}</td>'
                       f'<td class="num">不明</td><td class="num">不明</td><td class="num">-</td></tr>')
        out.append("</tbody></table></div>")
        out.append(f'<div class="marks foot">{len(rs)}点・{sum(int(r["amount"]) for r in rs):,}円　当たった時の払戻 {int(lo*amt):,}円〜{int(hi*amt):,}円</div>')
        out.append("</section>")

    out.append('<p class="foot">組み方は非馬テンプレート（◎から馬連・馬単・3連複）。'
               '★なしのレースは買い目に入れていない。馬番の色は枠色。</p>')
    out.append("</main>")
    open(args.out, "w").write("\n".join(out))
    print(f"wrote {args.out}  {len(order)}レース {n_all}点（30倍以下 {n_pick}点）")


if __name__ == "__main__":
    main()
