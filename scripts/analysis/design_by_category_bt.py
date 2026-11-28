"""予算上限なしなら何を推すか（11/28）。Logicとの関係×組み方ごとの回収率。事後の比較なので仮説扱い。"""
import csv, json, math, os, sys, itertools
from collections import defaultdict
R = "/home/user/keiba-yosou"
sys.path.insert(0, f"{R}/scripts/analysis")
from logic_variants import hiuma, by
S = "/tmp/claude-0/-home-user-ika-tensuhyo-r8/30549f72-b78e-5602-85dc-603e8682d1ff/scratchpad"
cache = json.load(open(f"{S}/result_cache.json"))
rows = list(csv.DictReader(open(f"{R}/data/marks_record.csv", encoding="utf-8-sig")))
H, L, meta = defaultdict(dict), defaultdict(list), {}
for r in rows:
    if r["source"] == "非馬":
        H[r["race_id"]][int(r["umaban"])] = r["mark"]
        if r["mark"] == "◎": meta[r["race_id"]] = r
    elif r["source"].startswith("Logic"):
        u = int(r["umaban"])
        if u not in L[r["race_id"]]: L[r["race_id"]].append(u)
ORD = {"馬単", "3連単"}
key = lambda k, n: "".join(f"{x:02d}" for x in (n if k in ORD else sorted(n)))
def star(s):
    for k, v in (("★★★", 3), ("★★", 2), ("★", 1)):
        if s.startswith(k): return v
    return 0
def designs(hm):
    o = by(hm, "◎")[0]; t = hiuma(hm)
    m1, m2, m3 = by(hm, "◯"), by(hm, "▲"), by(hm, "◯▲△")
    oth = by(hm, "◯▲△☆")
    d = {"全部入り": t,
         "馬連だけ": [b for b in t if b[0] == "馬連"],
         "馬単だけ": [b for b in t if b[0] == "馬単"],
         "3連複だけ": [b for b in t if b[0] == "3連複"],
         "馬単抜き": [b for b in t if b[0] != "馬単"],
         "馬連抜き": [b for b in t if b[0] != "馬連"],
         "単勝◎": [("単勝", [o])], "複勝◎": [("複勝", [o])],
         "ワイド◎流し(◯▲△)": [("ワイド", [o, p]) for p in m3]}
    if m1: d["ワイド◎-◯"] = [("ワイド", [o, m1[0]])]
    if m1 and m2:
        d["ワイド◎◯▲box"] = [("ワイド", list(c)) for c in itertools.combinations([o, m1[0], m2[0]], 2)]
        d["3連複◎◯▲1点"] = [("3連複", [o, m1[0], m2[0]])]
    d["3連単◎→◯▲△→◯▲△☆"] = [("3連単", [o, a, b]) for a in m3 for b in oth if a != b]
    return d
acc = defaultdict(lambda: defaultdict(list))
for rid in H:
    if rid not in cache or not cache[rid]["finished"] or rid not in meta: continue
    if list(H[rid].values()).count("◎") != 1 or "◯" not in H[rid].values(): continue
    o = by(H[rid], "◎")[0]; c = cache[rid]
    cat = "重なり" if rid in L and o in L[rid] else "重ならず" if rid in L else "指名なし"
    st = star(meta[rid]["stars"])
    for name, bets in designs(H[rid]).items():
        I = P = 0
        for k, n in bets:
            if set(n) & set(c["scr"]): continue
            p = c["payouts"].get(k, {}).get(key(k, n)); I += 100; P += p["yen"] if p else 0
        if I:
            for g in (cat, "全体", f"{cat}★{st}"):
                acc[g][name].append((I, P))
def line(name, l):
    I = sum(a for a, b in l); P = sum(b for a, b in l); r = P / I
    se = math.sqrt(sum((b - r * a) ** 2 for a, b in l)) / I
    top = max(b for a, b in l); hit = sum(1 for a, b in l if b) / len(l)
    return f"  {name:<22}{len(l):>4}R {I/len(l)/100:4.1f}点 {r*100:5.0f}%±{se*100:<4.0f}最大除く{(P-top)/I*100:5.0f}% 的中R{hit*100:3.0f}%"
for g in ["全体", "重なり", "重ならず", "指名なし"] + sorted(k for k in acc if "★" in k and k.startswith("指名なし")):
    print(g)
    for name, l in acc[g].items(): print(line(name, l))
