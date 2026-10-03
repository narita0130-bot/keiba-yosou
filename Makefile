# 競馬予想 1人会社 ── 殿の仕事（ワンコマンドランナー）
#
# 使い方:
#   make 始業点検          エンジン回帰テスト + 日時確認（毎回必須）
#   make 情報部            今日のレース一覧を表示
#   make 情報部全          今日の全レース出馬表 + ev.jsonテンプレートを生成
#   make 分析部            EV計算（data/TODAY.ev.json が必要）
#   make 判断部            最新オッズで買い目を再評価（data/TODAY.bets.json が必要）
#   make 経理部            投資記録の集計サマリー
#
# 日付を上書きする場合:
#   make 情報部 DATE=20261003
#   make 分析部 DATE=20261003

SHELL    := /bin/bash
DATE     ?= $(shell TZ=Asia/Tokyo date +%Y%m%d)
DATE_D   := $(shell python3 -c "d='$(DATE)'; print(d[:4]+'-'+d[4:6]+'-'+d[6:])")
EV_SPEC  := data/$(DATE_D).ev.json
BETS_SPEC:= data/$(DATE_D).bets.json

.PHONY: 始業点検 情報部 情報部全 分析部 判断部 経理部
.PHONY: check info info-all analysis decision accounting

# ── 始業点検（省略禁止）────────────────────────────────────────────────────
始業点検 check:
	@echo "=== 始業点検 ============================================================"
	cd engine && rm -rf __pycache__ && python3 test_engine.py
	@echo ""
	@TZ=Asia/Tokyo date "+%Y-%m-%d(%a) %H:%M JST"
	@echo "========================================================================="

# ── 情報部 ──────────────────────────────────────────────────────────────────
# 一覧のみ（高速。非馬記事でrace_idを調べたいとき）
情報部 info:
	@echo "=== 情報部 =============================================================="
	python3 scripts/morning.py --date $(DATE)

# 全レース出馬表 + ev.jsonテンプレート生成（指定レースのみなら --races で直接呼ぶ）
情報部全 info-all:
	@echo "=== 情報部（全レース出馬表） ============================================"
	python3 scripts/morning.py --date $(DATE) --all

# ── 分析部 ──────────────────────────────────────────────────────────────────
分析部 analysis:
	@echo "=== 分析部 =============================================================="
	@test -f "$(EV_SPEC)" || { \
		echo "⚠️  $(EV_SPEC) が見つかりません"; \
		echo "   先に 'make 情報部全' でテンプレートを生成し、印を入力してください"; \
		exit 1; }
	python3 engine/run_ev.py --spec $(EV_SPEC)

# ── 判断部 ──────────────────────────────────────────────────────────────────
判断部 decision:
	@echo "=== 判断部 =============================================================="
	@test -f "$(BETS_SPEC)" || { \
		echo "⚠️  $(BETS_SPEC) が見つかりません"; \
		echo "   分析部のEV結果をもとに bets.json を作成してください"; \
		exit 1; }
	python3 engine/show_bets.py --spec $(BETS_SPEC)

# ── 経理部 ──────────────────────────────────────────────────────────────────
経理部 accounting:
	@echo "=== 経理部 =============================================================="
	python3 scripts/weekly.py
