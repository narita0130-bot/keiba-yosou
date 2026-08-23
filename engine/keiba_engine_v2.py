# -*- coding: utf-8 -*-
"""
競馬期待値エンジン v2（改善版）
==================================================
旧方式（正規ノイズ×モンテカルロ5万回）からの改善点：
 (1) 厳密計算    : Plackett-Luce法で全着順確率を数式で算出。乱数誤差ゼロ・毎回同じ結果
 (2) 割引補正    : 2着・3着段階を p^λ で割引（λ2=0.81, λ3=0.65 / Lo & Bacon-Shone研究値）
                   → Harville近似の「人気馬の2・3着過大評価」を修正
 (3) 波乱の復元  : 大穴にも市場確率由来の勝率が残る（旧方式の「大穴勝率0%」を解消）
 (4) 市場を土台  : p = 市場^(1-λ) × モデル^λ のブレンド。実データ検証
                   「モデル単独は市場に負ける(74%<81%)」を踏まえ市場を主軸に
 (5) 券種別払戻率: JRA控除率準拠（複勝0.80/ワイド0.775/3連複0.75/3連単0.725）
 (6) 頑健性判定  : パラメータを揺らしてもEV≥1.0を保つかで「買い」判定
==================================================
【技術制約（未考慮の要素）】以下はモデルに含まれない。判断時に別途考慮すること。
 ・枠順の有利不利（例：小倉1200の7枠複勝率7.4%等の枠データ）
 ・馬場状態（良/稍重/重）への個別適性
 ・展開・脚質の相互作用（ハイペース時の差し有利等）
 ・斤量の増減効果
 ・能力パラメータは人間の主観入力（入力が誤れば出力も誤る）
 ・推定配当は市場確率からの理論値（実配当と乖離しうる。実配当は
   ev(..., actual_odds=実配当) で必ず上書きすること）
==================================================
"""
import numpy as np
from itertools import permutations

# JRA払戻率（1−控除率）
PAYOUT_RATE = {"単勝":0.80,"複勝":0.80,"枠連":0.775,"馬連":0.775,"ワイド":0.775,
               "馬単":0.75,"3連複":0.75,"3連単":0.725}

W_DEFAULT=[1.2,0.8,1.0,1.0,1.0]
def _tf(v): return 0.85+((v-1)/4)*0.30

class RaceEngine:
    def __init__(self, horses, lam=0.25, l2=0.81, l3=0.65):
        """
        horses: (馬番, 馬名, 単勝オッズ) または
                (馬番, 馬名, 単勝オッズ, 基礎能力, 距離, コース, 騎手, 近走, 状態)
        lam   : モデル比重（0=市場のみ, 1=モデルのみ）。既定0.25＝市場が土台
        l2,l3 : 2着・3着段階の割引指数
        """
        self._validate(horses)
        self.horses=list(horses); self.n=len(horses)
        self.num2i={h[0]:i for i,h in enumerate(horses)}
        self.names={h[0]:h[1] for h in horses}
        self.odds=np.array([float(h[2]) for h in horses])
        self.lam, self.l2, self.l3 = lam, l2, l3
        self.p_mkt=(1/self.odds)/np.sum(1/self.odds)
        self.p_model=self._model_prob()
        self._rebuild()

    @staticmethod
    def _validate(horses):
        """入力データの妥当性検証。異常値は例外で停止（黙って計算しない）"""
        if len(horses) < 2:
            raise ValueError("出走馬は2頭以上必要です")
        nums=set()
        for h in horses:
            if len(h) not in (3, 9):
                raise ValueError(f"馬データは3要素(番号,名前,オッズ)または9要素である必要があります: {h}")
            if h[0] in nums:
                raise ValueError(f"馬番が重複しています: {h[0]}")
            nums.add(h[0])
            if not (float(h[2]) > 1.0):
                raise ValueError(f"単勝オッズは1.0超である必要があります: {h[1]}={h[2]}")
            if len(h) == 9:
                if not (0 < float(h[3]) <= 200):
                    raise ValueError(f"基礎能力は0超200以下: {h[1]}={h[3]}")
                for i, nm in zip(range(4, 9), ["距離適性","コース適性","騎手","近走","状態"]):
                    if not (1 <= float(h[i]) <= 5):
                        raise ValueError(f"{nm}は1〜5の範囲: {h[1]}={h[i]}")
        lens={len(h) for h in horses}
        if len(lens) > 1:
            raise ValueError("全馬のデータ形式(3要素/9要素)を統一してください")

    def _model_prob(self):
        """能力パラメータ→勝率。鋭さγは市場分布との情報距離が最小になるよう自動調整
           （モデルは『順序の意見』を提供し、確率の鋭さは市場に合わせる設計）"""
        if len(self.horses[0])<9: return None
        sc=[]
        for h in self.horses:
            pf=1.0
            for k,w in enumerate(W_DEFAULT): pf*=_tf(h[4+k])**w
            sc.append(h[3]*pf)
        sc=np.array(sc)
        def pgamma(g):
            v=sc**g; return v/v.sum()
        def kl(g):
            pm=pgamma(g); return float(np.sum(self.p_mkt*np.log(self.p_mkt/pm)))
        lo,hi=0.5,60.0
        for _ in range(80):
            m1,m2=lo+(hi-lo)/3,hi-(hi-lo)/3
            if kl(m1)<kl(m2): hi=m2
            else: lo=m1
        self.gamma=(lo+hi)/2
        return pgamma(self.gamma)

    def _blend(self, lam):
        if self.p_model is None or lam<=0: return self.p_mkt.copy()
        p=(self.p_mkt**(1-lam))*(self.p_model**lam)
        return p/p.sum()

    def _orders(self, p, l2, l3):
        n=self.n; p2=p**l2; p3=p**l3
        S2=p2.sum(); S3=p3.sum()
        tri={}
        for a in range(n):
            pa=p[a]
            s2=S2-p2[a]
            for b in range(n):
                if b==a: continue
                pb=p2[b]/s2
                s3=S3-p3[a]-p3[b]
                pab=pa*pb
                for c in range(n):
                    if c==a or c==b: continue
                    tri[(a,b,c)]=pab*(p3[c]/s3)
        return tri

    def _rebuild(self):
        self.p=self._blend(self.lam)
        self.tri=self._orders(self.p,self.l2,self.l3)
        self.tri_mkt=self._orders(self.p_mkt,self.l2,self.l3)
        # 複勝(3着以内)確率
        self.place=np.zeros(self.n); self.place_mkt=np.zeros(self.n)
        for k,v in self.tri.items():
            for i in k: self.place[i]+=v
        for k,v in self.tri_mkt.items():
            for i in k: self.place_mkt[i]+=v

    # ---- 確率取得（買い目単位） ----
    def _p_combo(self, tri, kind, nums):
        idx=[self.num2i[x] for x in nums]
        if kind=="複勝":
            a=idx[0]; return sum(v for k,v in tri.items() if a in k)
        if kind=="ワイド":
            a,b=idx;  return sum(v for k,v in tri.items() if a in k and b in k)
        if kind=="馬連":
            a,b=idx;  return sum(v for k,v in tri.items() if set(k[:2])=={a,b})
        if kind=="馬単":
            a,b=idx;  return sum(v for k,v in tri.items() if k[0]==a and k[1]==b)
        if kind=="3連複":
            s=set(idx); return sum(v for k,v in tri.items() if set(k)==s)
        if kind=="3連単":
            return tri.get(tuple(idx),0.0)
        raise ValueError(kind)

    # ---- EV計算 ----
    def ev(self, kind, nums, actual_odds=None):
        """actual_odds: 実際のオッズが分かる場合は指定（推定より優先）"""
        p_hit=self._p_combo(self.tri,kind,nums)
        if actual_odds is not None:
            pay=float(actual_odds)
        else:
            p_m=self._p_combo(self.tri_mkt,kind,nums)
            pay=PAYOUT_RATE[kind]/p_m if p_m>1e-12 else 0.0
        return p_hit*pay, p_hit, pay

    def ev_robust(self, kind, nums, actual_odds=None):
        """パラメータを揺らした最小EV・最大EVを返す（最小EV≥1.0で『買い』）"""
        lams=[max(0,self.lam-0.15), self.lam, min(1,self.lam+0.15)]
        dis=[(1.0,1.0),(self.l2,self.l3),(0.70,0.50)]
        evs=[]
        keep=(self.lam,self.l2,self.l3)
        for lm in lams:
            for (a,b) in dis:
                self.lam,self.l2,self.l3=lm,a,b; self._rebuild()
                evs.append(self.ev(kind,nums,actual_odds)[0])
        self.lam,self.l2,self.l3=keep; self._rebuild()
        return min(evs),max(evs)

    def table(self):
        rows=[]
        for i,h in enumerate(self.horses):
            rows.append((h[0],h[1],self.odds[i],self.p[i]*100,self.place[i]*100,
                         self.p_mkt[i]*100,
                         (self.p_model[i]*100 if self.p_model is not None else None)))
        rows.sort(key=lambda r:-r[3])
        return rows
