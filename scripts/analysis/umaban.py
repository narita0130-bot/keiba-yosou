import csv, glob, math
from collections import defaultdict
st = defaultdict(lambda: defaultdict(lambda: [0, 0, 0.0]))  # key -> period -> [n, wins, return]
for f in sorted(glob.glob('data/races/*.csv')):
    for r in csv.DictReader(open(f, encoding='utf-8-sig')):
        if r['surface'] == '障' or not r['chaku'].isdigit() or not r['odds'] or not r['ninki'].isdigit(): continue
        per = '24-25' if r['date'] < '2026' else '26'
        w = r['chaku'] == '1'; od = float(r['odds']) if w else 0
        ub = int(r['umaban']); wk = int(r['waku']); nk = int(r['ninki'])
        for key in [('枠', wk), ('枠×芝ダ', f"{r['surface']}{wk}"), ('馬番', ub)] + ([('穴(10人気〜)枠', wk)] if nk >= 10 else []):
            s = st[key][per]; s[0] += 1; s[1] += w; s[2] += od
def show(kind):
    print(f'--- {kind}: 勝率 / 単勝回収率（2024-25 → 2026）')
    for key in sorted(k for k in st if k[0] == kind):
        a = st[key]['24-25']; b = st[key]['26']
        if a[0] < 300: continue
        print(f'{key[1]!s:>4} n={a[0]:5}/{b[0]:5} 勝率 {a[1]/a[0]:5.1%} → {b[1]/max(1,b[0]):5.1%}  回収 {a[2]*100/(a[0]*100):5.0%} → {b[2]*100/max(1,b[0]*100):5.0%}')
for k in ['枠', '穴(10人気〜)枠', '枠×芝ダ']: show(k)
