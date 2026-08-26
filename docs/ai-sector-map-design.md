# AIセクターマップ 設計書

作成: 2026-08-26（同日、ファイナンス系スキル知見による追加要素A〜Fを反映）／ 実装は別セッションで行う。

## 1. 目的

AI関連銘柄をカテゴリー毎（クラウド、半導体チップ、光通信など）に分類し、
**いまどのカテゴリーが好調かを一目で判断できる**ページを追加する。
カテゴリー→個別銘柄へドリルダウンでき、銘柄毎の直近ニュース（日本語要約）も見える。
ユーザーの手法（上昇トレンド中の押し目買い）を支援する情報設計とする:
「強いカテゴリーを見つける → その中の押し目形成中の銘柄を見つける → イベントリスク（決算）を確認する」。

## 2. 決定事項（ユーザー確認済み 2026-08-26）

| 論点 | 決定 |
|---|---|
| カテゴリー分類 | 下記8分類でスタート（銘柄の追加・削除は config で容易に変更可能な設計にする） |
| ニュース粒度 | カテゴリー毎の総括1本 ＋ 前日±3%以上動いた銘柄のみ個別深掘り（上限8銘柄） |
| ニュース保存先 | Supabase 直書き（クラウド実行環境に DATABASE_URL シークレットを設定） |
| 好調の指標 | 期間リターン（等ウェイト平均）＋ SPY比の相対強度（RS）を併記 |
| 追加要素（全採用） | A:押し目スクリーナー連携 / B:決算日バッジ / C:カテゴリー内ブレッドス / D:RSモメンタム矢印 / E:過熱警告 / F:ニュースセンチメントタグ |

追加要素の根拠: sector-analyst（多時間軸確認・overbought概念）、theme-detector（勢いの変化・ナラティブ確認）、
market-breadth-analyzer（参加率）、earnings-calendar（FMP決算カレンダー）の各スキルの手法を簡易化して移植。

## 3. カテゴリー定義

`config.py` に `AI_CATEGORY_MAP: dict[str, list[str]]` を新設（既存 `THEME_MAP` と同形式・別物として共存）。

| カテゴリーID | 表示名 | 銘柄 |
|---|---|---|
| hyperscaler | ハイパースケーラー・クラウド | MSFT, GOOGL, AMZN, META, ORCL, CRWV, NBIS |
| ai_chip | AI半導体（GPU・カスタムチップ） | NVDA, AMD, AVGO, MRVL, ARM, QCOM |
| semi_equip | 半導体製造・装置 | TSM, ASML, AMAT, LRCX, KLAC, TER, ONTO |
| memory | メモリ・ストレージ | MU, WDC, PSTG, NTAP |
| optical | 光通信・ネットワーキング | ANET, COHR, LITE, CIEN, CRDO, ALAB, FN |
| dc_power | データセンター・電力 | VRT, ETN, GEV, VST, CEG, OKLO, SMR, DLR |
| ai_server | AIサーバー | SMCI, DELL, HPE, IBM |
| ai_soft | AIソフトウェア | PLTR, NOW, SNOW, DDOG, CRM |

- 1銘柄は1カテゴリーのみ（表示の重複を避ける。分類変更は config 編集で対応）
- 表示名・銘柄リストは config が唯一の管理場所。フロントは API 経由で受け取る

## 4. 指標定義

期間は 1週間=直近5営業日 / 1ヶ月=21営業日 / 3ヶ月=63営業日（UIトグル、デフォルト1ヶ月）。

### 基本指標
- **銘柄リターン**: `close[最新] / close[最新−N営業日] − 1`
- **カテゴリーリターン**: 所属銘柄リターンの等ウェイト平均
- **RS**: カテゴリーリターン − SPY同期間リターン（%ポイント差。SPY は price_data に取得済み）
- **カテゴリー指数（スパークライン・比較チャート用）**: 各銘柄を期間起点=100に正規化し日次で等ウェイト平均
- **データ不足銘柄**（上場直後で N 営業日分が無い: CRWV/NBIS 等の可能性）: その銘柄を平均から除外し、カード内に「n=6/7」のように計算対象数を表示

### 追加指標（要素C/D/E）
- **C: ブレッドス** = カテゴリー内で `close > EMA20(日足)` の銘柄比率。「71% (5/7)」形式で表示。
  一部大型株だけの見せかけの強さと全員参加の強さを区別する
- **D: RSモメンタム** = 8カテゴリーを 1週間RS と 1ヶ月RS でそれぞれ順位付けし、順位差で判定:
  `1週間順位が1ヶ月順位より2つ以上良い → ↗改善中` / `2つ以上悪い → ↘悪化中` / `それ以外 → →横ばい`。
  期間スケールの異なるRSを直接比較せず順位差を使う（スケール不整合を回避、説明も容易）。閾値は config 定数
- **E: 過熱警告** = カテゴリー指数の直近5営業日リターン ≥ +10% で ⚠表示。
  閾値は `config.AI_OVERHEAT_5D_PCT = 10.0`（調整可能）。「今は追わず押し目を待つ」の判断補助。
  実装メモ: 5営業日リターン＝1週間リターンそのものなので別計算は不要（閾値フラグを付けるだけ）

### 連携指標（要素A）
- **A: 押し目候補バッジ** = swing_picks の最新 scan_date に含まれる銘柄へ 🎯バッジ、
  カテゴリーカードに「押し目候補 n件」を表示。追加データ不要（既存テーブルをJOINするだけ）
- **限界の認識**: swing scan は流動性フィルタ等で対象を絞るため、🎯が無い ＝「押し目でない」とは限らず
  「スキャン対象外」の場合もある。UIのツールチップにその旨を一言入れる
- **基準日ズレの認識**: swing_picks の scan_date と price_data の as_of は別パイプラインのため
  1営業日ズレ得る（実測あり: scan_date=8/25 vs as_of=8/24）。API は `swing_scan_date` も返し、
  ズレている時だけ UI に小さく併記する

## 5. データ準備（実装時に1回だけ実施）

universe / price_data に無い14銘柄を追加する:
`VRT, COHR, CRDO, ALAB, FN, ASML, TSM, ARM, CRWV, NBIS, IREN, APLD, INTC, TER`
（IREN, APLD は当面カテゴリー未所属の予備。追加コストが無いので一緒に入れる）

1. `pipeline/static_universe.py` のリストに追記（既存フォーマットに合わせ sector 等を付与）
   - **注意**: Daily Pipeline (Light) は既存 universe テーブルを読むだけで Stage1（universe再構築）を含まない。
     static ファイルへの追記だけでは**本番テーブルに反映されない**ため、次のバックフィルスクリプトが
     `universe` テーブルへの upsert も行うこと（ticker/name/sector/exchange）
2. バックフィル: Polygon **per-ticker aggs** (`/v2/aggs/ticker/{t}/range/1/day/2025-03-31/{today}`) を1銘柄1コール
   - 無料枠 5コール/分 → 14銘柄で約3分。grouped で日毎に回すより圧倒的に速い
   - 既存 price_data の期間 (2025-03-31〜) に揃える。上場がそれ以降の銘柄は上場日からで良い
   - スクリプトは `scripts/backfill_ai_tickers.py` として保存（再利用可能に）
3. 以後の日次更新は既存 Daily Pipeline (Light) の grouped 取得が universe 全銘柄を拾うため**変更不要**

**副作用の認識**: universe が 688→702 銘柄になるため、市場ヘルスの母数も +14 される
（テック寄り銘柄が増え、スコアが1%前後シフトし得る）。実害はないが、市場ヘルスの数値が
実装前後で微妙に変わることをユーザーが認識しておく

## 6. DBスキーマ追加

### 6.1 `ai_news`（ニュース。両DB実装の init_db に追加）

```sql
CREATE TABLE IF NOT EXISTS ai_news (
    id          SERIAL PRIMARY KEY,          -- sqlite: INTEGER PRIMARY KEY AUTOINCREMENT
    news_date   DATE NOT NULL,               -- 収集ルーチンの対象日（ET基準の前営業日）
    category    TEXT NOT NULL,               -- カテゴリーID（8分類のいずれか）
    ticker      TEXT NOT NULL DEFAULT '',    -- '' = カテゴリー総括行（NULLを使わない: 下記UNIQUE制約のため）
    headline    TEXT NOT NULL,               -- 見出し（日本語）
    summary_ja  TEXT NOT NULL,               -- 3〜4文の日本語要約
    sentiment   TEXT DEFAULT 'neutral',      -- 要素F: positive / negative / neutral
    source_url  TEXT DEFAULT '',
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (news_date, category, ticker)     -- 上書きupsert (ON CONFLICT) の前提。NULLだと両DBで挙動が割れるため ticker は '' を使う
);
CREATE INDEX IF NOT EXISTS idx_ai_news_date ON ai_news (news_date DESC);
```

- API レスポンスでは ticker='' を null に変換して返す（フロントの判定を素直に保つ）

- 保持期間30日: 収集ルーチンが書き込み後に `DELETE FROM ai_news WHERE news_date < 最新-30日`
- 1回の実行で入る行数: カテゴリー総括8行 ＋ 急動銘柄0〜8行

### 6.2 `earnings_dates`（要素B: 決算日。両DB実装の init_db に追加）

```sql
CREATE TABLE IF NOT EXISTS earnings_dates (
    ticker        TEXT PRIMARY KEY,
    earnings_date DATE NOT NULL,             -- 次回決算日
    timing        TEXT DEFAULT '',           -- bmo(寄り前) / amc(引け後) / ''(未定)
    updated_at    TIMESTAMPTZ DEFAULT now()
);
```

- 取得: Daily Pipeline (Light) に1ステージ追加。FMP `/api/v3/earning_calendar?from=今日&to=+30日`
  （1コール）→ AI_CATEGORY_MAP の銘柄のみ upsert。FMP_API_KEY は GHA シークレット設定済み
- **実装前確認**: FMP は新規キー向けに legacy `/api/v3` を段階廃止し `/stable` へ移行中。
  手持ちキーでどちらが通るか curl で1回確認してから実装する（レスポンス形式も微妙に異なる）
- 失敗しても他ステージに影響させない（既存の log_stage + WARN パターン踏襲）

## 7. API（`backend/routes/ai_map.py` 新設）

### GET `/api/ai-map/summary?period=1w|1m|3m`

```jsonc
{
  "as_of": "2026-08-25",            // price_data の最新日
  "swing_scan_date": "2026-08-25",  // 🎯バッジの基準日（as_of と1営業日ズレ得る）
  "price_stale": false,             // as_of が2営業日超前なら true（バナー表示用）
  "period": "1m",
  "benchmark": {"ticker": "SPY", "return_pct": 2.1},
  "categories": [                    // return_pct 降順
    {
      "id": "optical", "label": "光通信・ネットワーキング",
      "return_pct": 12.3, "rs_pct": 10.2,
      "rs_trend": "improving",              // D: improving / worsening / flat
      "breadth_pct": 71.4, "breadth_n": 5,  // C: 20EMA上の銘柄数/比率
      "overheat": false,                    // E: 5日リターン≥+10%
      "swing_pick_count": 2,                // A: 押し目候補数
      "earnings_this_week": 1,              // B: 7日以内に決算の銘柄数
      "n_calc": 7, "n_total": 7,
      "index_series": [{"date": "...", "value": 100.0}, ...],
      "tickers": [
        {"ticker": "ANET", "name": "...", "close": 123.4,
         "chg_1d_pct": 1.2, "return_pct": 15.0,
         "above_ema20": true,
         "in_swing_picks": true,                       // A
         "earnings_date": "2026-08-28", "earnings_timing": "amc",  // B（無ければ null）
         "spark": [ ...30日分のclose... ],
         "tv_url": "https://www.tradingview.com/chart/?symbol=ANET"}
      ]
    }
  ]
}
```

- 実装: 対象銘柄＋SPY を `WHERE ticker = ANY(...) AND date >= 最新-100営業日` の1クエリで取得し pandas で計算。
  swing_picks（最新 scan_date）と earnings_dates は別クエリでJOIN相当のマージ
- swing.py と同じ in-memory キャッシュ（900秒）を踏襲

### GET `/api/ai-map/news?days=7`

```jsonc
{
  "updated_at": "2026-08-26T08:20:00+09:00",  // 最新 created_at
  "stale": false,                              // 最新 news_date が2営業日超前なら true
  "items": [
    {"news_date": "2026-08-25", "category": "optical", "ticker": null,
     "headline": "...", "summary_ja": "...", "sentiment": "positive", "source_url": ""},
    {"news_date": "2026-08-25", "category": "optical", "ticker": "COHR", ...}
  ]
}
```

## 8. フロントエンド（`frontend/js/components/ai-sector-map.js` 新設）

- `app.js` の `SECTIONS` に `{ id: "ai-map", label: "AIセクターマップ", icon: "🤖" }` を追加
- **実装時は `frontend-design` スキルを起動してから着手する**（CLAUDE.md の規約）

構成（上から）:
1. **期間トグル**（1週間/1ヶ月/3ヶ月）— localStorage に保存（swing-screener のプリファレンス実装を踏襲）
2. **カテゴリーカード** — リターン降順のグリッド。カード表示要素:
   表示名 / リターン / RS / **RS矢印↗→↘(D)** / スパークライン / **ブレッドス「71% (5/7)」(C)** /
   **🎯押し目候補n件(A)** / **📅今週決算n件(B)** / **⚠過熱(E)** / n数。リターンの正負でカード色をグラデーション
3. **カテゴリー比較チャート** — lightweight-charts の LineSeries×8（起点=100）。凡例クリックで表示切替
4. **ドリルダウン** — カードクリックで銘柄テーブル展開:
   ticker / 現在値 / 前日比 / 期間リターン / スパークライン / 🎯(A) / 📅決算日+タイミング(B) / TradingView リンク。
   各銘柄行の下に該当ニュース（急動銘柄分）、テーブル上部にカテゴリー総括ニュース。
   ニュースは **センチメントで左ボーダー色分け(F)**: positive=緑 / negative=赤 / neutral=グレー
5. **鮮度表示** — ニュース: `updated_at` を表示し stale なら警告バナー。
   **価格: `price_stale` が true の時も同様の警告バナー**（「価格データが◯日前のものです」）。
   いずれも swing の staleness バナー実装を踏襲

モバイル注意（過去の教訓）: flex/grid の子に `min-width: 0`、横スクロールはコンテナ内に閉じる。

## 9. ニュース収集ルーチン（Claude Code スケジュール実行・クラウド）

- **スケジュール**: 火〜土 JST 8:15（cron `15 23 * * 1-5` UTC）。daily_pipeline(7:30)・swing_scan(7:45) の後
- **セットアップ（ユーザー作業が必要）**:
  1. claude.ai/code のクラウド環境設定に `DATABASE_URL` をシークレットとして登録
     - **Supabase の接続文字列は pooler（IPv4対応）の URI を使う**（direct 接続はIPv6のみで、
       クラウド実行環境から届かない可能性がある。既存GHAで使用中のものと同じでよい）
  2. `/schedule` でルーチン作成（実装セッションで一緒に行う）
  3. **初回は手動実行で検証**: psycopg2 の導入 → Supabase への接続 → INSERT まで通ることを確認
     （クラウド環境からの外部DB接続はここで初めて実証される。書き込みは必ずパラメータ化SQLで行う）
- **ルーチンの処理内容**（プロンプトとして記述する）:
  1. **前営業日の急動銘柄（±3%以上）の特定は Web検索を主体に行う**（finviz等の movers 情報から対象銘柄を抽出）。
     理由: 8:15 JST 時点では Polygon 無料枠の EOD 配信遅延により price_data が前営業日分を
     持っていないことが多い（実測: 8/26 朝時点で as_of=8/24 だった）。DBの前日比は
     `MAX(date)` が前営業日と一致する時のみ裏取りに使う
  2. 米国市場が休場だった朝（祝日・週末明けの特殊日）は「休場のため更新なし」と判断して書き込みをスキップする
  3. Web検索: 各カテゴリー1回（例「optical networking stocks news」＋主要銘柄名）→ 総括を日本語3〜4文で作成
  4. 急動銘柄それぞれ検索（最大8銘柄）→ 動いた理由を日本語で要約（決算/アナリスト/製品発表など）
  5. 各ニュースに **sentiment（positive/negative/neutral）を付与**（要素F）
  6. `ai_news` に INSERT（同一 news_date × category × ticker が既にあれば上書き）
  7. 30日超の行を DELETE
- **失敗時**: ページ側は最終更新表示＋staleバナーで気付ける。リトライはせず翌朝の実行に任せる
- **注意**: 毎朝の実行はクレジットを消費する（1回あたり検索10〜16回＋要約）。止めたくなったら /schedule で無効化

## 10. 実装ステップ（推奨順）

1. `config.py` に `AI_CATEGORY_MAP`・`AI_OVERHEAT_5D_PCT` 等の定数追加
2. `static_universe.py` に14銘柄追記 → `scripts/backfill_ai_tickers.py` でバックフィル → DBで件数検証
3. `ai_news`・`earnings_dates` テーブル追加（両DB実装）
4. Daily Pipeline (Light) に決算日取得ステージ追加（FMP 1コール）→ 手動実行で earnings_dates を初回充填
5. `backend/routes/ai_map.py` 実装（**`backend/app.py` への include_router 登録を忘れない**。
   api/index.py は backend.app を再エクスポートするだけなので触らない）→ ローカルでレスポンス検証
   （リターン・ブレッドス・RS順位は pandas で独立再計算と突き合わせ）
6. 指標計算のユニットテスト追加（`tests/test_ai_map.py`: リターン/ブレッドス/RS順位差/過熱判定/データ不足銘柄の除外。
   既存 tests/ の合成データ方式を踏襲）
7. フロント実装（frontend-design スキル起動）→ モバイル390pxで確認
8. デプロイ（Vercel は git push で自動）
9. クラウド環境シークレット設定 → `/schedule` でルーチン作成 → 手動1回実行して ai_news に行が入ることを確認

## 11. 見送った候補（検討済み・理由付き）

- theme-detector流のライフサイクル5段階判定: FINVIZ依存＋主観要素が強く、RSモメンタム矢印(D)で実用上の目的は満たせる
- 機関投資家フロー・マクロレジーム検知: このページの目的（AIカテゴリーの相対比較）から外れる。市場全体の状況は既存の市場ヘルスページの領分

## 12. 未決事項（実装時に確認）

- 銘柄の日本語社名表示は universe.name（英語）をそのまま使うか
- カード色のグラデーション閾値（±何%で最大彩度か）
- IREN / APLD をどのカテゴリーに入れるか（当面は未所属の予備）
- RSモメンタムの順位差閾値（初期値±2）と過熱閾値（初期値+10%/5日）の実運用チューニング
