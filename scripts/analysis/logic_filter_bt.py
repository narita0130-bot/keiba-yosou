"""Logicを「非馬◎の確認役」に使う規則の過去検証（2026-11-21、ユーザー依頼「Logicとひうまでオリジナルの買い目」）。
非馬テンプレート（全部入りの組み方）の成績を、そのレースでのLogicの指名との関係で分ける。
  重なり   ：Logicがそのレースで注目馬を出し、非馬◎がその中にいる
  重ならず ：Logicがそのレースで注目馬を出したが、非馬◎は入っていない
  指名なし ：Logicがそのレースに触れていない
オリジナル規則 = 重なり（★以上）は買う／重ならずは買わない／指名なしは★★以上だけ買う。
データを見てから作った規則なので、この数字は根拠ではなく仮説。結果キャッシュはスクラッチパッドの result_cache.json。"""
import csv, json, math, os, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from logic_variants import hiuma, by
S = "/tmp/claude-0/-home-user-ika-tensuhyo-r8/30549f72-b78e-5602-85dc-603e8682d1ff/scratchpad"
cache = json.load(open(f"{S}/result_cache.json"))
rows = list(csv.DictReader(open(os.path.join(HERE, "../../data/marks_record.csv"), encoding="utf-8-sig")))
H, L, meta = defaultdict(dict), defaultdict(list), {}
for r in rows:
    if r["source"] == "非馬":
        H[r["race_id"]][int(r["umaban"])] = r["mark"]
        if r["mark"] == "◎": meta[r["race_id"]] = r
    elif r["source"].startswith("Logic"):
        u = int(r["umaban"])
        if u not in L[r["race_id"]]: L[r["race_id"]].append(u)
key = lambda k, n: "".join(f"{x:02d}" for x in (n if k == "馬単" else sorted(n)))
def star(s):
    for k in ("★★★", "★★", "★"):
        if s.startswith(k): return 2 if k != "★" else 1
    return 0
recs = []
for rid in H:
    if rid not in cache or not cache[rid]["finished"] or rid not in meta: continue
    if list(H[rid].values()).count("◎") != 1 or "◯" not in H[rid].values(): continue
    o = by(H[rid], "◎")[0]; c = cache[rid]; I = P = 0
    for k, n in hiuma(H[rid]):
        if set(n) & set(c["scr"]): continue
        p = c["payouts"].get(k, {}).get(key(k, n)); I += 100; P += p["yen"] if p else 0
    recs.append(dict(d=meta[rid]["date"], I=I, P=P, st=star(meta[rid]["stars"]), cov=rid in L, ov=rid in L and o in L[rid]))
def show(name, l):
    I = sum(x["I"] for x in l); P = sum(x["P"] for x in l); R = P / I
    se = math.sqrt(sum((x["P"] - R * x["I"]) ** 2 for x in l)) / I; top = max(x["P"] for x in l)
    mo = defaultdict(lambda: [0, 0])
    for x in l: mo[x["d"][5:7]][0] += x["I"]; mo[x["d"][5:7]][1] += x["P"]
    print(f"{name:<20}{len(l):>4}R {R*100:4.0f}%±{se*100:.0f} 最大を除く{(P-top)/I*100:4.0f}%  " +
          " ".join(f"{m}月{v[1]/v[0]*100:.0f}%" for m, v in sorted(mo.items())))
show("全部", recs)
show("★★以上だけ", [x for x in recs if x["st"] >= 2])
show("重なり★以上", [x for x in recs if x["ov"] and x["st"] >= 1])
show("重ならず", [x for x in recs if x["cov"] and not x["ov"]])
show("重ならず★★以上", [x for x in recs if x["cov"] and not x["ov"] and x["st"] >= 2])
show("指名なし★★以上", [x for x in recs if not x["cov"] and x["st"] >= 2])
show("オリジナル規則", [x for x in recs if (x["ov"] and x["st"] >= 1) or (not x["cov"] and x["st"] >= 2)])
