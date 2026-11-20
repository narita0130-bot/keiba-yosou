"""過去検証：非馬が買ったレース（★以上）でLogicの注目馬がいたレースについて、各版の回収率。"""
import csv, json, math, sys
from collections import defaultdict
S = "/tmp/claude-0/-home-user-ika-tensuhyo-r8/30549f72-b78e-5602-85dc-603e8682d1ff/scratchpad"
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from logic_variants import VARIANTS, to_wide, by
cache = json.load(open(f"{S}/result_cache.json"))
rows = list(csv.DictReader(open("/home/user/keiba-yosou/data/marks_record.csv", encoding="utf-8-sig")))
H, L, meta = defaultdict(dict), defaultdict(list), {}
for r in rows:
    if r["source"] == "非馬":
        H[r["race_id"]][int(r["umaban"])] = r["mark"]
        if r["mark"] == "◎": meta[r["race_id"]] = r
    elif r["source"].startswith("Logic"):
        u = int(r["umaban"])
        if u not in L[r["race_id"]]: L[r["race_id"]].append(u)
key = lambda k, n: "".join(f"{x:02d}" for x in (n if k == "馬単" else sorted(n)))
use = [rid for rid in sorted(H) if rid in cache and cache[rid]["finished"] and rid in L and rid in meta
       and list(H[rid].values()).count("◎") == 1 and "◯" in H[rid].values() and meta[rid].get("stars")]
print(f"対象 {len(use)}レース（{min(meta[r]['date'] for r in use)}〜{max(meta[r]['date'] for r in use)}、非馬★以上・Logic注目馬あり）")
res = defaultdict(list)
for rid in use:
    hm, lg, c = H[rid], L[rid], cache[rid]
    for name, fn in VARIANTS.items():
        b = fn(hm, lg)
        for vname, bets in ((name, b), (name + "ワイド", to_wide(b))):
            inv = pay = 0
            for k, n in bets:
                if set(n) & set(c["scr"]): continue
                p = c["payouts"].get(k, {}).get(key(k, n)); inv += 100; pay += p["yen"] if p else 0
            res[vname].append((rid, inv, pay))
print(f"{'版':<12}{'点数':>6}{'投資':>9}{'払戻':>9}{'回収率':>8}  当たり  最大を除く")
for v, lst in res.items():
    I = sum(x[1] for x in lst); P = sum(x[2] for x in lst); R = P / I
    se = math.sqrt(sum((x[2] - R * x[1]) ** 2 for x in lst)) / I
    hit = sum(1 for x in lst if x[2] > 0); top = max(x[2] for x in lst)
    print(f"{v:<12}{I//100:>6}{I:>9,}{P:>9,}{R*100:>6.0f}%±{se*100:.0f}  {hit:>3}R  {(P-top)/I*100:>4.0f}%")
json.dump(res, open(f"{S}/logic_bt.json", "w"), ensure_ascii=False)
