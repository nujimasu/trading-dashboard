# ロジック全面改修 設計仕様書（v1.0 / 2026-06-14）

> 本書は `/codex-build` 実装の入力仕様。確定済みのユーザー意思決定に基づく。
> 推測で仕様を埋めない。曖昧点は実装前にユーザーへ確認すること。

## 0. ゴール（確定事項）

| ロジック | 変更 | 新名称 | 要点 |
|---|---|---|---|
| ロジック1 | **全面刷新（100%ファンダ・グロース）** | **ファンダ重視** | 全ユニバースを成長ファンダでランク付け＋押し目タイミング注記 |
| ロジック2 | **維持＋出口改訂** | **厳選押し目買いv1** | 入口(4H厳格トリガー)は維持。出口を「高値ターゲット＋RRゲート＋一部トレール」へ |
| ロジック3 | **完全削除** | — | nav/route/scan/guide/backtest/DBテーブル すべて撤去 |
| ロジック4 | **v3確定版へ強化** | **厳選押し目買いv2** | 決算7日除外/レジサポ加点/VIX慎重フラグ/レバETF動的除外を追加 |

- 内部ID（`logic1`/`logic2`/`logic4`）は据え置き、**表示ラベルのみ新名称**に変更（DB/route churn回避）。
- メニュー順: `ファンダ重視` → `厳選押し目買いv1` → `厳選押し目買いv2`。
- 利確/損切り/RRはロジックごとに下記の確定仕様へ調整する。

---

## 1. ロジック1 →「ファンダ重視（グロース）」

### 1.1 方針（ユーザー確定）
- **哲学**: グロース（成長重視）。CANSLIM の C（当期EPS成長）/A（年次成長）/I（機関投資家）の**ファンダ部分**を yfinance 取得項目へ写像。
- **母集団**: 全ユニバース（≈628銘柄）を対象。テクニカルでの事前足切りは**しない**（真の100%ファンダ）。
- **抽出の厳しさ**: **ハイブリッド** = 最低限の成長ゲート通過銘柄のみを、成長スコアで順位付け。
- **売買プラン**: **ファンダ順位＋押し目タイミング注記**。SL/TP は「押し目圏内」のときだけ提示。

### 1.2 データソース拡張（`backend/services/fundamentals.py` + `fundamentals` テーブル）
既存列: `sector, industry, market_cap, pe_ratio, eps_growth_yoy, revenue_growth_yoy, earnings_surprise_pct, roe, description, updated_at`

**追加列**（`fundamentals` に `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`、`db_postgres.py` の CREATE にも追記）:
| 列 | 型 | yfinance .info ソース | 用途 |
|---|---|---|---|
| `eps_growth_q` | REAL | `earningsQuarterlyGrowth`（小数→%） | C成分（当期四半期EPS成長・優先） |
| `operating_margin` | REAL | `operatingMargins`（小数→%） | 質（利益率） |
| `profit_margin` | REAL | `profitMargins`（小数→%） | 質（利益率） |
| `inst_own_pct` | REAL | `heldPercentInstitutions`（小数→%） | I成分（機関投資家） |
| `debt_to_equity` | REAL | `debtToEquity` | 財務健全性ガード（任意減点） |

- 取得失敗時は `None`。7日キャッシュ（既存仕様）を踏襲。
- `_fetch_from_yfinance` の戻り dict / INSERT / UPDATE に上記を追加。

### 1.3 グロース・スコアカード（0–100・**ファンダのみ**）
> CANSLIM 準拠（earnings最重視）。各項目は線形/階段スケールで満点に正規化し合算。

| 項目 | 配点 | 満点条件 | スケール例 |
|---|---|---|---|
| 当期EPS成長 (`eps_growth_q` 優先、無ければ`eps_growth_yoy`) | **30** | ≥50% | 30–49%→24, 18–29%→18, 8–17%→12, 0–7%→6, ≤0→ゲート落ち |
| 売上成長 (`revenue_growth_yoy`) | **15** | ≥30% | 20–29%→12, 10–19%→9, 0–9%→4, <0→0 |
| 決算サプライズ (`earnings_surprise_pct`) | **15** | >10% | 5–10%→11, 0–5%→7, <0→0, データ無→7(中立) |
| ROE (`roe`) | **15** | ≥30% | 20–29%→12, 15–19%→9, 0–14%→線形, <0→0 |
| 利益率 (`operating_margin` 優先) | **15** | ≥25% | 15–24%→11, 5–14%→7, 0–4%→3, <0→0, データ無→7(中立) |
| 機関投資家保有率 (`inst_own_pct`) | **10** | 30–70% | 20–30%/70–85%→7, それ以外→4, データ無→5(中立) |
| 財務健全性ガード (`debt_to_equity`) | 減点 | — | D/E>200 で −5（任意・下限0） |

**合計 0–100**。

### 1.4 最低限の成長ゲート（ハイブリッド・全て満たすこと）
1. `eps_growth_q`（無ければ`eps_growth_yoy`）> 0
2. `revenue_growth_yoy` > 0
3. 黒字（`pe_ratio` > 0 もしくは EPS陽性が確認できる）
4. `market_cap` ≥ **$1B**（マイクロキャップ除外）
5. ファンダデータが取得済み（`sector` 等が存在）

→ ゲート不通過銘柄は weekly_picks に載せない。

### 1.5 判定（verdict / tier）
- スコア帯: `≥80 強い成長` / `65–79 良好` / `50–64 平均的成長` / `<50（ゲート通過）成長やや弱め`
- `fundamental_verdict` 列にこの帯を格納。
- `verdict` 列（既存BUY/WATCH互換）: **押し目圏内 かつ score≥65 → "BUY"**、それ以外 → "WATCH"。
- `tier`: score≥80→`Tier1`, ≥65→`Tier2`, else `Tier3`。

### 1.6 押し目タイミング注記（テクニカル・**スコアには非加算**）
`price_data`（≥200本）から算出:
- 上昇トレンド判定: `close > EMA200` かつ `EMA50 > EMA200`
- `EMA20`/`EMA50` からの乖離%（`ema20_dist`, `ema50_dist`）、`above_ema200`(bool)
- **zone_flag**:
  - `押し目圏内` = 上昇トレンド かつ（20 or 50EMA の **±3%以内**）
  - `やや高所（押し目待ち）` = 上昇トレンド かつ 20EMA より +3%超
  - `トレンド外（様子見）` = 上昇トレンドでない
- **押し目圏内のときのみ**スイング執行プランを算出し weekly_picks に格納:
  - `entry_price` = 直近終値
  - `stop_price` = 直近20日押し安値 − 0.1×ATR（= 1R）
  - `tp1_price` = entry + 1.5R
  - `target_price` = entry + 3.0R（参考）
  - `risk_reward` = 1.5
  - それ以外の zone では entry/stop/tp1/target/risk_reward は **NULL**。
- **クロスタグ**: 当日の `logic2_picks` / `logic4_picks` に同一 ticker があれば signals に「v1/v2 にも出現（買い場一致）」を付与。
- `holding_days_est`: グロース投資想定で既定 **45**。

`technical_summary`(JSON) に格納する項目: `ema20_dist, ema50_dist, above_ema200, zone_flag, in_pullback(bool), cross_tag(list), growth_breakdown(各項目の獲得点)`。
`fundamental_summary`(JSON): 既存形式＋ `eps_growth_q, operating_margin, profit_margin, inst_own_pct, growth_score`。

### 1.7 新スキャン `pipeline/logic1_scan.py`（新規）
責務:
1. `universe` から price_data≥200本の銘柄を取得。
2. 各銘柄: `get_or_fetch_fundamentals`（7日キャッシュ）→ ゲート判定 → グロース・スコア算出。
3. 押し目注記＋（圏内のみ）執行プラン算出。
4. ゲート通過銘柄をスコア降順で並べ、**上位 N=60 件**を `weekly_picks` に upsert（`DELETE FROM weekly_picks` → INSERT）。
   - 上限60の理由: `daily_adjustment` が weekly_picks 全件を yfinance DL するため件数を抑制。
5. 押し目圏内（entry/stop あり）の picks のみ `signal_log("logic1", ...)` へ記録（評価可能なシグナルのみ）。
6. `compute_market_health` は **Stage3 が既に書込済**のため本スキャンでは呼ばない（重複回避）。

**weekly_picks スキーマは変更しない**（既存列に収まる）。`composite_score` = グロース・スコア。

### 1.8 フロントエンド
- `app.js`: ラベル `ロジック１（ファンダ考慮）` → **`ファンダ重視`**。`loadLogic1` の `renderPickList` タイトルを「🎯 ファンダ重視（グロース）」に。データ取得は現状の `/api/weekly-picks` + `/api/daily-picks` マージを踏襲。
- `components/strategy-guide.js`（ロジック1の説明）: グロース方針・スコアカード・押し目注記の説明へ全面刷新。
- `components/pick-list.js` + `utils/pick-normalizer.js`（type=`hybrid-entry`）: グロース・スコア、主要成長指標（EPS成長/売上成長/ROE/利益率）、zone_flag バッジ、クロスタグを表示。押し目圏外は「押し目待ち/トレンド外」を表示し SL/TP 行は出さない。

### 1.9 パイプライン結線（`run_pipeline.py`）
- **run_full**: `Stage1 → Stage2 → Stage3` の後、**Stage4/5/6 を撤去**し **`logic1_scan.run()`** を実行。続けて `logic2_scan` / `logic4_scan` / `news`。
  - Stage3 は `technical_screen` と `market_health` 生成のため**残す**。
  - `detailed_analysis` は参照元が Stage6 のみのため孤立する（他参照なし＝確認済）。テーブルは当面 DROP せず温存。
- **run_daily_full**: 同様に Stage4/5/6 を `logic1_scan` に置換、logic3 撤去。
- **run_daily_light**: 変更なし（logic3 参照なし）。
- `_collect_daily_price_tickers`: `SELECT ticker FROM logic3_picks` の行を削除。

---

## 2. ロジック2 →「厳選押し目買いv1」（出口改訂）

### 2.1 入口（維持）
`logic2_scan.py` の 4H厳格トリガー判定・「押し目待ち」除外・サポート検出（`_find_support_level`）は**変更しない**。

### 2.2 出口（確定仕様・`_calc_rr` 周辺を改訂）
| 項目 | 仕様 |
|---|---|
| SL | サポート/押し安値の少し下に**固定** = 1R（ATRバッファ。`sl = support − 0.1×ATR` 程度、現行のサポート基準を流用しつつ1R定義を明確化） |
| TP1 | 直近スイング高値の手前 ×0.99 で **2/3 を利確**（高勝率の源泉） |
| 残り1/3 | **20日EMA を終値で割るまでトレール** |
| RRゲート | TP1 までの **RR < 1.5 は不採用**（verdict を「対象外」へ格下げ＝リストに出さない or 最下位）。利小損大を構造的に防止 |
| 保有上限 | **8営業日**経過で含み損なら全決済（signals に明記） |

- `tp1_price` = 直近高値×0.99、`target_price` = 同高値（参考上限）、`stop_price` = 1R下、`risk_reward` = (tp1−entry)/(entry−sl)。
- 利確割合（2/3）と残りトレールは `signals_json` に運用ルールとして明記（自動執行はしない＝注記）。
- `holding_days_est`: 上限8に整合（現行ATR算出は残しても上限8でクランプ）。

### 2.3 フロント
- `app.js`: ラベル → **`厳選押し目買いv1`**、`renderPickList` タイトル「🔥 厳選押し目買いv1」。
- `components/logic2-strategy-guide.js`: タイトル「厳選押し目買い**v1**」、出口説明を 2.2 に更新。出口で v2 との違い（v1=高値利確・高勝率 / v2=利大損小・トレール）を明記。

---

## 3. ロジック3 → 完全削除

撤去対象（全て削除）:
- `pipeline/logic3_scan.py`
- `backend/routes/logic3.py`
- `frontend/js/components/logic3-strategy-guide.js`
- `backend/app.py`: logic3 router の import / `include_router` 解除
- `frontend/js/app.js`: SECTIONS の `logic3` エントリ、`loadLogic3`、`renderLogic3StrategyGuide` import 削除
- `frontend/js/components/backtest.js`: logic3 選択肢（line 18 周辺）削除
- `backend/routes/backtest.py`: Query description の `logic3` 言及削除
- `pipeline/run_pipeline.py`: run_full / run_daily_full の logic3 ブロック、`_collect_daily_price_tickers` の logic3_picks クエリ削除
- `backend/db_postgres.py`: `logic3_picks` の CREATE TABLE（line 335付近 と 534付近の重複定義）削除＋ **migration に `DROP TABLE IF EXISTS logic3_picks`** 追加
- `backend/db.py`: logic3 関連の定義があれば整理
- `frontend/js/components/pick-list.js` / `tech-picks-table.js` / `utils/pick-normalizer.js`: logic3 参照を削除/無害化
- `signal_log`: `DELETE FROM signal_log WHERE logic_name = 'logic3'`（履歴も撤去）

> 注意: 削除後に grep で `logic3` 残存参照ゼロを確認する。

---

## 4. ロジック4 →「厳選押し目買いv2」（v3確定版へ強化）

`/Users/junusami/Downloads/押し目買いロジックv3.md` を正とする。現 `logic4_scan.py` に**4項目を追加実装**（既存の地合い/トレンド/EMAタッチ/出来高枯れ/1R・+1.5R・20EMAトレール・8日上限は維持）。

### 4.1 決算7日以内の銘柄を除外（v3 B項）
- 対象: トレンド通過後の候補のみ（件数を絞ってAPIコスト抑制）。
- 次回決算日取得: `yfinance` の `Ticker(t).calendar` または `get_earnings_dates()`。取得不可時は**除外しない**（保守）。
- 判定: 次回決算まで **7日以内**なら除外（リストから外す）。除外理由をログに出す。

### 4.2 レジサポ転換の重なりを加点（v3 D項・任意加点）
- 検出: 採用EMA（タッチ対象の20 or 50EMA）価格の **±2%以内**に「過去のスイング高値（直近120日内の局所高値で、現値がそれを上抜けている＝レジ→サポ転換）」が存在するか。
- 該当時: `reji_sapo = "confirmed"`、`confluence += 1`、`confidence += 0.05`、`support_reasons` に「レジサポ転換の節目と重なり」を追加。
- 非該当: 現行どおり `reji_sapo = "none"`。

### 4.3 VIX急騰週は慎重フラグ（v3 A項・非ブロック）
- `_check_market_regime` を拡張し `^VIX` を取得。
- 条件: `VIX > 25`（高ボラ）**または** 直近5営業日で VIX が **+30%以上**急騰 → `vix_caution = True`。
- 該当時: 候補は出すが `signals` に「⚠️VIX急騰週：反発足は『陽線＋翌日も前日高値超え』までダマシ確認を厚く」を追加。verdict はブロックしない。
- VIX取得失敗時はフラグ無し（保守）。

### 4.4 高額レバETF >$100 の動的除外（v3 D項）
- `LEVERAGED_ETF`（キュレーション集合・既存 EXCLUDE_TICKERS のレバ系を母体に拡充）を定義。
- ルール: 当該集合の銘柄は **価格 > $100 で除外**、**価格 < $30 は許容**、$30–$100 は格下げ（verdict 据置だが confidence 微減）。
- 既存の暗号資産マイニング小型株の固定除外は維持。

### 4.5 フロント
- `app.js`: ラベル → **`厳選押し目買いv2`**、`renderPickList` タイトル「💎 厳選押し目買いv2」。
- `components/logic4-strategy-guide.js`: タイトル「厳選押し目買い**v2**」、追加4フィルタ（決算除外/レジサポ加点/VIX慎重/レバ動的除外）の説明追記。v1 との違い（出口の性格）を明記。
- `backend/routes/logic4.py`: `fundamental_verdict` 等の文言を「テクニカルのみ（厳選押し目買いv2）」へ。

---

## 5. v1 / v2 の差別化（ドキュメント・UI 明記）

| | v1（厳選押し目買い） | v2（厳選押し目買い） |
|---|---|---|
| 入口 | 4H厳格トリガー（反発確認済み寄り） | 日足フィルタ＋当日反発足を本人確認（ウォッチ型） |
| 出口 | **高値ターゲットで2/3利確＋残りトレール**（高勝率・利確早め） | **+1.5Rで半分→20EMAトレール**（利大損小・伸ばす） |
| RRゲート | TP1までRR≥1.5 | SL=1R前提、+1.5R基準 |
| 上限 | 8営業日 | 8営業日 |
| 向く局面 | レジスタンス明確なレンジ気味スイング | トレンド継続ランナー |

---

## 6. backtest / signal_log への影響
- `signal_log` の `logic_name` は `logic1`（押し目圏内picks）/`logic2`/`logic4` が記録対象（logic3 は削除）。
- `backtest.js` の選択肢から logic3 を削除し、表示名を新名称（ファンダ重視 / 厳選押し目買いv1 / v2）へ更新。
- logic2/logic4 が現状 signal_log へ記録しているかは実装時に確認し、未記録なら各 scan 末尾に `log_signals` を追加（任意・別PR可）。

---

## 7. 懸念点・リスク
1. **yfinance 全ユニバース取得（≈628 .info コール）の信頼性**: GHA（データセンターIP）から大量 .info は**レート制限/ブロック**の恐れ。対策: 銘柄ごと try/except でスキップ＋7日キャッシュで網羅率を蓄積、控えめスロットル。網羅率が落ちる場合は将来 FMP キー併用を検討（本改修では yfinance 維持）。
2. **週次GHA 実行時間**: Polygon で価格は軽量化済。ファンダ ≈628コールで +10〜20分想定。180分以内だが yfinance 遅延次第。要・初回計測。
3. **weekly_picks 件数増（≈12→最大60）**: `daily_adjustment` の yfinance DL 増。上限60でクランプし、entry/stop が NULL の行は RR 計算をスキップする耐性を `daily_adjustment` に持たせる（NULLガード確認）。
4. **Stage4/5/6 撤去**: `detailed_analysis` 孤立（参照は Stage6 のみで確認済）。万一の参照に備えテーブルは DROP せず温存。
5. **既存ローカルWIP**: 本改修着手前にローカル git 状態の整理が必要（§9）。

---

## 8. 実装順序（codex-build 推奨フェーズ）
1. **DB**: `fundamentals` 列追加 / `logic3_picks` DROP migration（`db_postgres.py` + `db.py`）。
2. **ロジック3 完全削除**（コード/route/nav/backtest/参照クリーンアップ）→ grep でゼロ確認。
3. **fundamentals サービス拡張**（新項目取得）。
4. **`logic1_scan.py` 新規**＋ run_pipeline 結線（Stage4/5/6 置換）。
5. **ロジック2 出口改訂**。
6. **ロジック4 v3強化4項目**。
7. **フロント**: ラベル/ガイド/pick表示更新（app.js のバージョンクエリ `?v=` も bump）。
8. **検証**: `python3 -m py_compile` 全Python、ローカルで `run_full`（または `--skip-download` で Stage3→logic1→2→4）を本番DBに繋がずローカルSQLiteで実行→各テーブル生成確認。

> 検証時は `DATABASE_URL` 未設定（ローカルSQLite）で行い、本番Supabaseへは書き込まない。

---

## 9. git / デプロイ上の注意（実装後・ユーザー関与必須）
- ローカル `main` は `ef0a338`（origin/main は Polygon merge `dae084e` で先行）。作業ツリーに **Polygon コード＋UI改修6項目WIP**（sparkline/economic next-release/news URL/chart+TP-SLライン等）が未コミットで同居。
- 本改修のコミット/プッシュ前に git ベースを整理（fetch→origin/main 取込→WIP仕分け）すること。**勝手にコミット/プッシュ/GHA実行はしない**（ユーザー承認必須）。push は `gh auth switch --user nujimasu` 後、専用 credential helper 経由。
- 機密（DATABASE_URL / POLYGON_API_KEY）は `.env`（gitignore済）のみ。コード/ドキュメントに値を書かない。
