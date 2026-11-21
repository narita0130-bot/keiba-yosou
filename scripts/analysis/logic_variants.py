"""非馬の印とLogicの注目馬から、Logic◎版・Logic◯版・ワイド版の買い目を組む（今日の分と過去検証で共用）。
hm: {馬番: 非馬の印}, lg: [Logicの注目馬の馬番]"""
import itertools

def by(m, ks): return [u for k in ks for u, x in sorted(m.items()) if x == k]

def _dedupe(bets):
    seen, out = set(), []
    for k, n in bets:
        key = (k, tuple(n) if k == "馬単" else tuple(sorted(n)))
        if key not in seen: seen.add(key); out.append((k, list(n)))
    return out

def hiuma(hm, lg=None):
    """非馬テンプレート：馬連◎-◯▲△／馬単◎→◯▲△☆／3連複◎+相手2頭"""
    o = by(hm, "◎")[0]; ren, oth = by(hm, "◯▲△"), by(hm, "◯▲△☆")
    return [("馬連", [o, p]) for p in ren] + [("馬単", [o, p]) for p in oth] + \
           [("3連複", [o, a, b]) for a, b in itertools.combinations(oth, 2)]

def logic_hon(hm, lg):
    """Logic◎版（11/8と同じ組み方）：Logicの注目馬を軸、相手＝非馬の印の馬＋Logicの他の注目馬。
    馬連は軸から相手（非馬☆だけの馬は除く）、馬単は軸から相手全員、3連複は軸＋相手2頭。"""
    bets = []
    for ax in lg:
        partners = list(dict.fromkeys([n for n in list(by(hm, "◎◯▲△☆")) + lg if n != ax]))
        ren = [n for n in partners if n in lg or hm.get(n) in ("◎", "◯", "▲", "△")]
        bets += [("馬連", [ax, p]) for p in ren] + [("馬単", [ax, p]) for p in partners] + \
                [("3連複", [ax, a, b]) for a, b in itertools.combinations(partners, 2)]
    return _dedupe(bets)

def logic_tai(hm, lg):
    """Logic◯版：軸は非馬の◎のまま、Logicの注目馬を◯として相手に入れる（非馬の◯▲△☆も残す）。"""
    o = by(hm, "◎")[0]
    L = [n for n in lg if n != o]
    ren = list(dict.fromkeys(L + by(hm, "◯▲△")))
    oth = list(dict.fromkeys(L + by(hm, "◯▲△☆")))
    return _dedupe([("馬連", [o, p]) for p in ren] + [("馬単", [o, p]) for p in oth] +
                   [("3連複", [o, a, b]) for a, b in itertools.combinations(oth, 2)])

def to_wide(bets):
    """2頭の券種（馬連・馬単）の組をワイドに置き換え、同じ2頭は1点。3連複は外す。"""
    return _dedupe([("ワイド", sorted(n)) for k, n in bets if k in ("馬連", "馬単")])

VARIANTS = {"非馬": hiuma, "Logic◎": logic_hon, "Logic◯": logic_tai}


def original(hm, lg):
    """オリジナル版「2人の意見が一致した馬で組む」（2026-11-21 ユーザー依頼で作成）。
    対象は非馬の◎をLogicも挙げたレースだけ（それ以外は空リスト）。
    軸＝その◎。本線＝非馬とLogicの両方が印を付けた他の馬。相手＝どちらか一方だけが印を付けた馬。
      ワイド 軸-本線・軸-非馬◯ ／ 馬連 軸-本線 ／ 3連複 軸+本線+相手1頭
    本線がいないときは 軸-非馬◯ のワイド・馬連と、軸+非馬◯+Logicの最上位馬 の3連複。"""
    hon = by(hm, "◎")
    if len(hon) != 1 or hon[0] not in lg:
        return []
    c = hon[0]
    tai = [u for u in by(hm, "◯") if u != c]
    main = [u for u in by(hm, "◯▲△☆") if u in lg and u != c]
    others = [u for u in list(dict.fromkeys(by(hm, "◯▲△☆") + list(lg))) if u != c and u not in main]
    bets = []
    if main:
        bets += [("ワイド", [c, m]) for m in main] + [("ワイド", [c, t]) for t in tai]
        bets += [("馬連", [c, m]) for m in main]
        bets += [("3連複", [c, m, o]) for m in main for o in others]
        bets += [("3連複", [c, a, b]) for a, b in itertools.combinations(main, 2)]
    else:
        lg_top = [u for u in lg if u != c][:1]
        bets += [("ワイド", [c, t]) for t in tai] + [("馬連", [c, t]) for t in tai]
        bets += [("3連複", [c, t, l]) for t in tai for l in lg_top if l != t]
    return _dedupe(bets)
