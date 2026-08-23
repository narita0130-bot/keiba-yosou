# -*- coding: utf-8 -*-
"""
競馬エンジン 自動検証スクリプト（回帰テスト）
================================================
目的：エンジン改修のたびに実行し、全項目合格を確認してから使用する。
      1つでも不合格なら、そのエンジンで買い目判断をしてはならない。
実行：python3 test_engine.py
================================================
"""
import sys
from keiba_engine_v2 import RaceEngine, PAYOUT_RATE

OK=[]; NG=[]
def check(name, cond, detail=""):
    (OK if cond else NG).append(name)
    print(f"  {'✅' if cond else '❌'} {name}" + (f"  {detail}" if detail else ""))

def make(params_override=None, odds_override=None):
    base=[
     (1,"テスト馬A",3.0, 80,3,3,3,3,3),
     (2,"テスト馬B",5.0, 78,3,3,3,3,3),
     (3,"テスト馬C",8.0, 76,3,3,3,3,3),
     (4,"テスト馬D",15.0,74,3,3,3,3,3),
     (5,"テスト馬E",30.0,70,3,3,3,3,3),
    ]
    rows=[]
    for h in base:
        h=list(h)
        if odds_override and h[0] in odds_override: h[2]=odds_override[h[0]]
        if params_override and h[0] in params_override:
            col,val=params_override[h[0]]; h[col]=val
        rows.append(tuple(h))
    return rows

print("="*60)
print("【検証1】確率の整合性")
print("="*60)
e=RaceEngine(make(), lam=0.25)
s_win=sum(e.p); s_tri=sum(e.tri.values())
check("勝率の合計が100%", abs(s_win-1)<1e-9, f"合計={s_win*100:.6f}%")
check("全着順確率の合計が100%", abs(s_tri-1)<1e-9, f"合計={s_tri*100:.6f}%")
check("複勝率の合計が300%", abs(sum(e.place)-3)<1e-9)

print()
print("="*60)
print("【検証2】パラメータ感応性（読み取りズレの再発防止）")
print("="*60)
# 各列を1頭だけ引き上げたとき、その馬の勝率が必ず上がることを確認する。
# 昨夜のバグ（状態が無反応）はこの検証で必ず検出される。
cols={3:"基礎能力(→90)",4:"距離適性(→5)",5:"コース適性(→5)",6:"騎手(→5)",7:"近走(→5)",8:"状態(→5)"}
base_p = RaceEngine(make(), lam=0.25).p[2]  # テスト馬Cの勝率
for col,label in cols.items():
    val = 90 if col==3 else 5
    e2 = RaceEngine(make(params_override={3:(col,val)}), lam=0.25)
    check(f"{label} を上げると勝率が上がる", e2.p[2] > base_p + 1e-6,
          f"{base_p*100:.2f}%→{e2.p[2]*100:.2f}%")

print()
print("="*60)
print("【検証3】誠実性（幻の妙味を作らない）")
print("="*60)
e0=RaceEngine([(h[0],h[1],h[2]) for h in make()], lam=0)
for kind,nums in [("複勝",(1,)),("ワイド",(1,2)),("馬連",(1,2)),("馬単",(1,2)),("3連複",(1,2,3)),("3連単",(1,2,3))]:
    ev,_,_=e0.ev(kind,nums)
    check(f"市場のみで{kind}のEV＝払戻率{PAYOUT_RATE[kind]}", abs(ev-PAYOUT_RATE[kind])<1e-9, f"EV={ev:.6f}")

print()
print("="*60)
print("【検証4】決定性（同じ入力→毎回同じ答え）")
print("="*60)
ea,eb=RaceEngine(make(),lam=0.25),RaceEngine(make(),lam=0.25)
check("2回実行して全馬の勝率が完全一致", all(abs(a-b)<1e-15 for a,b in zip(ea.p,eb.p)))

print()
print("="*60)
print("【検証5】入力検証（異常値を黙って通さない）")
print("="*60)
bad_cases=[
 ("オッズ1.0以下を拒否", [(1,"A",0.9,80,3,3,3,3,3),(2,"B",5.0,78,3,3,3,3,3)]),
 ("適性6(範囲外)を拒否", [(1,"A",3.0,80,3,3,3,3,6),(2,"B",5.0,78,3,3,3,3,3)]),
 ("馬番重複を拒否",     [(1,"A",3.0,80,3,3,3,3,3),(1,"B",5.0,78,3,3,3,3,3)]),
 ("形式混在を拒否",     [(1,"A",3.0),(2,"B",5.0,78,3,3,3,3,3)]),
]
for name,data in bad_cases:
    try:
        RaceEngine(data); check(name, False, "例外が発生しなかった")
    except ValueError:
        check(name, True)

print()
print("="*60)
print("【検証6】頑健レンジの整合性")
print("="*60)
e=RaceEngine(make(), lam=0.25)
ev,_,_=e.ev("複勝",(2,)); lo,hi=e.ev_robust("複勝",(2,))
check("最小EV ≤ 中心EV ≤ 最大EV", lo<=ev+1e-9<=hi+1e-9, f"[{lo:.3f} ≤ {ev:.3f} ≤ {hi:.3f}]")

print()
print("="*60)
if NG:
    print(f"❌ 不合格 {len(NG)}件：{NG}")
    print("→ このエンジンでの買い目判断を禁止。修正後に再実行すること。")
    sys.exit(1)
print(f"✅ 全{len(OK)}項目合格。エンジンは使用可能な状態。")
