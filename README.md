# 競馬予想メモ・オッズ集計

購読している予想note（PDF）の印に、netkeiba の公開オッズを突き合わせて日次でまとめるためのリポジトリ。

## ファイル構成

| パス | 役割 |
|---|---|
| `scripts/fetch_odds.py` | netkeiba の公開オッズ取得スクリプト（依存なし・標準ライブラリのみ） |
| `scripts/build_sheet.py` | 出馬表・オッズ・買い目の1枚ものHTMLを組み立てる |
| `data/YYYY-MM-DD.sheet.json` | その日のレース構成・印・買い目の定義（`build_sheet.py` の入力） |
| `data/YYYY-MM-DD.md` | その日のまとめ（印・単複・想定馬券のオッズ） |
| `data/YYYY-MM-DD_出馬表オッズ買い目.pdf` | 生成した予想シート |

## 使い方

```bash
# 開催日の全レースの race_id 一覧（--date 省略時は本日JST）
python3 scripts/fetch_odds.py races --date 20260808

# 1レースの単勝・複勝（印を付けると先頭にまとめて出る）
python3 scripts/fetch_odds.py odds --race 202601010510 \
    --mark "4=◎" --mark "8=◯" --mark "1=▲" --mark "3=☆"

# 組み合わせオッズ（馬連 / ワイド / 馬単 / 3連複 / 3連単）
python3 scripts/fetch_odds.py combo --race 202607020507 \
    --bet "馬連:1-6" --bet "馬単:6>3" --bet "3連単:6>1>3"
```

`>` はシェルのリダイレクトと解釈されるので、`--bet` の値は必ずクォートで囲むこと。

### 予想シート（出馬表・オッズ・買い目）のPDF化

`data/YYYY-MM-DD.sheet.json` に、その日のレースID・印・買い目を書いてから実行する。

```bash
cd scripts
python3 build_sheet.py --spec ../data/2026-08-08.sheet.json --out /tmp/sheet.html

# Chromium で PDF 化（IPAGothic が入っていれば日本語もそのまま出る）
/opt/pw-browsers/chromium-1194/chrome-linux/chrome --headless --no-sandbox \
    --disable-gpu --no-pdf-header-footer \
    --print-to-pdf=../data/2026-08-08_出馬表オッズ買い目.pdf file:///tmp/sheet.html
```

起動時に D-Bus 関連の ERROR が出るが、PDF は正常に生成されるので無視してよい。

買い目の `source` は `note`（note本文に書かれていた買い目）と `ref`（印から機械的に組んだ参考）を
区別する。PDF 上でも「note記載」「参考」として別表示になるので、予想者の推奨と自分で足したものを
混同しないこと。

### race_id の構成

`2026` `01` `01` `05` `10` = 年 + 競馬場 + 回次 + 日次 + レース番号。
競馬場コードは 01札幌 / 02函館 / 03福島 / 04新潟 / 05東京 / 06中山 / 07中京 / 08京都 / 09阪神 / 10小倉。
回次・日次は開催によって変わるので、`races` サブコマンドで実際の ID を引くのが確実。

## 運用メモ

- 実行環境は claude.ai/code の **`競馬リサーチ用`** 環境（`env_01WYLXKRaY7kqZs5FRhp3RGK`）。
  この環境は egress で `race.netkeiba.com` へ到達できることを確認済み。
- 予想note の PDF はチャットに添付して渡す（本リポジトリには置かない）。
- オッズは発走まで変動するため、まとめには必ず API の `official_datetime`（確定時刻）を併記する。

## 注意

- netkeiba の公開ページ・公開 API のみを利用し、取得間隔を空けて負荷をかけないこと。
- 出力はあくまで公開オッズの集計であり、馬券の的中を保証するものではない。
