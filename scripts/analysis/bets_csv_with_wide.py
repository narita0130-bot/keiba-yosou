"""build_bets_csv.py をそのまま使い、ワイドだけ除外リストから外して呼ぶ（試算用。本体は変えない）。"""
import sys
sys.path.insert(0, "/home/user/keiba-yosou/scripts"); sys.path.insert(0, "/home/user/keiba-yosou/engine")
import build_bets_csv as b
b.SKIP_KINDS = tuple(k for k in b.SKIP_KINDS if k != "ワイド")
b.main()
