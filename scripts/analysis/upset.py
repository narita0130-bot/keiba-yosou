import csv, glob, re, math
from collections import defaultdict
races = defaultdict(list)
for f in sorted(glob.glob('data/races/*.csv')):
    for r in csv.DictReader(open(f, encoding='utf-8-sig')):
        if r['surface'] == '障': continue
        races[r['race_id']].append(r)
def feats(r0, n):
    rc = r0['race_class']
    cls = next((k for k in ['新馬','未勝利','１勝','２勝','３勝','オープン'] if k in rc), '他')
    wt = next((k for k in ['ハンデ','別定','定量','馬齢'] if k in rc), '他')
    age = '2歳' if '２歳' in rc else ('3歳' if '３歳 ' in rc or rc.count('３歳')==1 and '以上' not in rc else '古馬')
    fs = '≤11頭' if n <= 11 else ('12-15頭' if n <= 15 else '16-18頭')
    d = int(r0['distance']); db = '〜1400' if d <= 1400 else ('1500-1800' if d <= 1800 else '1900〜')
    return {'クラス': cls, '斤量': wt, '年齢': age, '頭数': fs, '芝ダ': r0['surface'], '距離': db,
            '馬場': r0['going'] if r0['going'] in ('良','稍','重','不') else '他', '牝限定': '牝限定' if '牝' in rc.split('[')[0][-6:] else '混合', '場': r0['venue']}
stats = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0.0, 0]))   # races, upsets, longshot bets, longshot return, longshot wins
for rid, rs in races.items():
    rs = [x for x in rs if x['chaku'].isdigit() and x['ninki'].isdigit() and x['odds']]
    if len(rs) < 8: continue
    top = sorted(rs, key=lambda x: int(x['chaku']))[:3]
    if len(top) < 3: continue
    s = sum(int(x['ninki']) for x in top)
    upset = s >= 25
    period = '2024-25' if rs[0]['date'] < '2026' else '2026'
    f = feats(rs[0], len(rs))
    longs = [x for x in rs if int(x['ninki']) >= 10]
    for k, v in list(f.items()) + [('全体', '全体')]:
        st = stats[(k, v)][period]
        st[0] += 1; st[1] += upset
        st[2] += len(longs); st[3] += sum(float(x['odds']) for x in longs if x['chaku'] == '1'); st[4] += sum(1 for x in longs if x['chaku'] == '1')
print('条件 | レース数(24-25/26) | 大荒れ率(上位3頭の人気合計≥25) 24-25 / 26 | 10番人気以下の単勝回収率 24-25 / 26')
for key in sorted(stats, key=lambda k: (k[0], k[1])):
    a = stats[key]['2024-25']; b = stats[key]['2026']
    if a[0] < 150: continue
    ra = a[3] / a[2] if a[2] else 0; rb = b[3] / b[2] if b[2] else 0
    print(f'{key[0]}:{key[1]:10} {a[0]:5}/{b[0]:4}  大荒れ {a[1]/a[0]:5.1%} / {b[1]/max(1,b[0]):5.1%}   穴単勝 {ra:5.0%} / {rb:5.0%}  (穴馬数 {a[2]}/{b[2]})')
