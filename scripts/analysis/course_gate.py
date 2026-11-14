import csv, glob, math
from collections import defaultdict
def grp(w): return '内(1-2枠)' if w <= 2 else ('外(7-8枠)' if w >= 7 else '中(3-6枠)')
def nkg(n): return '全体' if n is None else ('人気(1-3)' if n <= 3 else ('中穴(4-9)' if n <= 9 else '大穴(10-)'))
D = defaultdict(lambda: {'24-25': [], '26': []})
for f in sorted(glob.glob('data/races/*.csv')):
    for r in csv.DictReader(open(f, encoding='utf-8-sig')):
        if r['surface'] == '障' or not r['chaku'].isdigit() or not r['odds'] or not r['ninki'].isdigit(): continue
        per = '24-25' if r['date'] < '2026' else '26'
        y = float(r['odds']) * 100 if r['chaku'] == '1' else 0.0
        course = f"{r['venue']}{r['surface']}{r['distance']}"
        g = grp(int(r['waku'])); nk = int(r['ninki'])
        for band in ('全体', nkg(nk)):
            D[(course, g, band)][per].append(y)
def roi(v):
    n = len(v); m = sum(v) / n; sd = math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1)) if n > 1 else 0
    return m, sd / math.sqrt(n), n
tests = 0; picked = []
for key, d in D.items():
    a = d['24-25']
    if len(a) < 200: continue
    tests += 1
    m, se, n = roi(a)
    if m >= 110 and (m - 100) / se >= 2:
        picked.append((key, m, se, n))
print(f'発見期間（2024-25）で調べた条件: {tests}個 → 「回収率110%以上かつ100%より2SE以上上」: {len(picked)}個')
print(f'（偶然だけでも約{tests*0.023:.0f}個は引っかかる計算）')
tot_a = [0, 0]; tot_b = [0, 0]
for key, m, se, n in sorted(picked, key=lambda x: -x[1]):
    b = D[key]['26']; mb, seb, nb = roi(b) if len(b) > 1 else (0, 0, 0)
    tot_b[0] += sum(b); tot_b[1] += len(b)
    print(f'{key[0]:12} {key[1]:9} {key[2]:8}  24-25: {m:4.0f}% ±{se:3.0f} (n={n})  →  2026: {mb:4.0f}% ±{seb:3.0f} (n={nb})')
if tot_b[1]: print(f'選ばれた条件を2026年にまとめて買うと: 回収率 {tot_b[0]/tot_b[1]:.0f}%（{tot_b[1]}頭）')
print()
rows = []
for key, d in D.items():
    a, b = d['24-25'], d['26']
    if len(a) < 200 or len(b) < 60: continue
    rows.append((roi(a)[0], roi(b)[0], key, len(a), len(b), roi(a)[1]))
rows.sort(reverse=True)
print('発見期間の回収率 上位12条件 → 2026年')
for ma, mb, key, na, nb, se in rows[:12]:
    print(f'{key[0]:12} {key[1]:9} {key[2]:8}  {ma:4.0f}% ±{se:3.0f} (n={na}) → {mb:4.0f}% (n={nb})')
n = len(rows); xa = [r[0] for r in rows]; xb = [r[1] for r in rows]
ma = sum(xa)/n; mb = sum(xb)/n
cov = sum((p-ma)*(q-mb) for p, q in zip(xa, xb)); va = sum((p-ma)**2 for p in xa); vb = sum((q-mb)**2 for q in xb)
print(f'\n全{n}条件で、2024-25年の回収率と2026年の回収率の相関: {cov/math.sqrt(va*vb):.2f}')
top = rows[:20]; bot = rows[-20:]
print(f'2024-25年の上位20条件 → 2026年平均 {sum(r[1] for r in top)/20:.0f}%　／　下位20条件 → 2026年平均 {sum(r[1] for r in bot)/20:.0f}%')
