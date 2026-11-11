# 相場感（上昇／下降トレンド）判断ガイド

- **対象:** 米国の個別株
- **時間軸:** 日足がメイン（4時間足は補助）
- **保有期間:** 数日〜数週間（スイングトレード）

---

## 1. 結論

- 判断の中心は **①早期警戒（20EMA＋押し安値）** です。
- **200日線は「買っていい相場かどうか」を確認するフィルター**です。売りのサインとしては遅すぎます。
- 使う線は **20EMA・50日線・200日線＋押し安値** の4つで十分です。増やしすぎないでください。

---

## 2. よく使われる基準の評価

| 指標 | 評価 | 理由 |
|---|---|---|
| 4時間足で価格が200EMAを下回る | 中期の崩れのサイン。早期警戒には向かない | 4時間足の200本 ≒ 日足の約100日分（通常取引のみの場合） |
| 日足で25EMA（20EMA）が200EMAを下回る | 転換点を探すには遅すぎる | デッドクロスと同じく、出た時点で既に大きく下げていることが多い |
| 日足の100EMA | この保有期間ではあまり使わない | 米国では50日線・200日線ほど注目されていない。数日〜数週間の取引には遅い |

### 4時間足200EMAの注意点（チャートの設定で意味が変わる）

| 設定 | 1日あたりの4時間足 | 4時間足200EMA ≒ 日足で何日分か |
|---|---|---|
| 通常取引のみ（9:30〜16:00 ET） | 約2本 | **約100日分** |
| 時間外取引を含む（4:00〜20:00 ET） | 約4本 | **約50日分** |

→ 日足と比べやすくするため、**通常取引のみ**の設定がおすすめです（時間外は取引量が少なく、ダマシも出やすい）。

---

## 3. 下降転換を判断する3段階（日足）

米国株では **20 / 50 / 200** が標準です（日本でよく使う25/75はあまり使われません）。
50日線・200日線は、米国では一般に **SMA（単純移動平均）** を指します。EMAと一緒に **SMAも表示** しておくのがおすすめです。

| 段階 | 意味 | 見るポイント |
|---|---|---|
| ① 早期警戒 | 「転換かも？」 | ・終値が **20EMA（または21EMA）を割る**＋20EMAが横ばい〜下向き<br>・**高値更新に失敗** → **直近の押し安値を割る** |
| ② 警戒強化 | 中期の崩れ | ・終値が **50日線を割る**（出来高を伴うと強いサイン）<br>・20EMAが50日線を下抜ける |
| ③ 確認 | 長期の下降トレンド入り | ・価格が **200日線より下**、かつ **200日線が横ばい〜下向き**<br>・50日線と200日線のデッドクロス |

### ポイント
- **200日線は「上か下か」より「向き」が大事です。** 200日線が上向きのまま一時的に割っただけなら、ダマシになりやすいです。
- **一番早く出るサインは価格の形（押し安値割れ）です。** 移動平均は計算の仕組み上、どうしても遅れます。

---

## 4. 個別株で追加するチェック

### 4-1. 相場全体（SPY）の状態
- **SPYが200日線より上か下か、200日線の向きはどうか** を確認します。
- 根拠：多くの個別株は相場全体と同じ方向に動きます（O'Neilの「下落相場では4銘柄中3銘柄が一緒に下がる」という経験則）。
- SPYが悪い（200日線より下、または200日線が下向き）ときは、①が出たら **すぐに動く** 側に寄せます。

### 4-2. 相対力（RSライン）＝株価より先に弱さが出やすい
- 「個別株 ÷ S&P500」の比率です。TradingViewではシンボル欄に `AAPL/SPY` のように入力すると表示できます。
- **警戒する形:**
  - 株価は高値を更新したのに、RSラインは更新しない（ダイバージェンス）
  - RSラインが株価より先に直近の安値を割る

### 4-3. 決算と出来高
- **決算での窓開け急落は特別扱いします。** 窓を開けて50日線を割り、出来高が平均の1.5〜2倍以上なら、①を飛ばして **一気に②〜③とみなします**（1.5〜2倍は実務上の目安で、厳密な根拠はありません）。
- **決算日は事前に確認し、決算をまたぐかどうかをエントリー前に決めておきます。** 窓開けにはEMAでもストップ注文でも対応できません。
- 出来高が少ない日のライン割れは、ダマシになりやすいです。

---

## 5. 数日〜数週間保有向けのルール

| 役割 | 指標 | 使い方 |
|---|---|---|
| 環境の確認（買っていい相場か） | 日足200日線（個別株とSPY） | 価格が200日線より上 **かつ** 200日線が上向きのときだけ買いを検討 |
| 保有を続ける条件 | 日足50日線 | 50日線より下ならスイングの買いは持たない |
| **売りの判断（メイン）** | 日足20EMA＋押し安値 | 終値で20EMAを割り、**直近の押し安値も割ったら手仕舞い**（または半分に減らす） |
| 予兆 | RSライン（`銘柄/SPY`） | 先に崩れたら、①を待たずにポジションを軽くする |
| 細かいタイミング（任意） | 4時間足の20EMA・押し安値 | 日足の①より早く気づける。ただしダマシは増える |

- **損切りの位置:** EMAではなく **直近の押し安値の少し下** に置く（EMAは毎日位置が動くので基準が曖昧になる）。
- **組み合わせ:** 個別株は値動きが荒いので、20EMA割れ単独では判断しない。**「RSラインの悪化」か「SPYの悪化」のどちらかと①が重なったら警戒** するのが現実的。

---

## 6. 毎日のチェックリスト

```
[ ] SPY：200日線より上？ 200日線は上向き？
[ ] 銘柄：200日線より上？ 200日線は上向き？
[ ] 銘柄：50日線より上？
[ ] RSライン（銘柄/SPY）：高値を切り下げていない？ 安値を割っていない？
[ ] 終値で20EMAを割っていない？ 押し安値を割っていない？
[ ] 次の決算日はいつ？ 保有期間中にある？ → 持ち越すか決めた？
[ ] 出来高：ライン割れの日の出来高は平均と比べて多い？
```

---

## 7. 前提として知っておくこと（忖度なし）

- **転換点を正確に当てられる指標はありません。** 早い指標ほどダマシが多く、確実な指標ほど遅い、という関係は避けられません。
- なので **段階ごとにやることを決めておく**（例：①でポジションを減らす、②で手仕舞う、③では新規の買いをしない）のが実用的です。

---

## 7.5 TradingView で現在地を確認する

`pinescript/trend_state.pine`（トレンド現在地）をチャートに追加すると、このガイドの考え方で日足の状態を5段階に色分けします。

| 表示 | 意味 | 目安 |
|---|---|---|
| 🟢 上昇トレンド | 長期線が上向き＋並びが上昇順＋短期線が上向き＋早期警戒なし | ロング候補 |
| 🟡 上昇の失速 | 長期線は上向きだが、並びの崩れや早期警戒あり | 新規ロングは控える |
| ⚪ レンジ | 長期線が横ばいで、並びもはっきりしない | 触らない |
| 🔵 下降の失速 | 長期線は下向きだが、並びの崩れや反発の兆しあり | 新規ショートは控える |
| 🔴 下降トレンド | 長期線が下向き＋並びが下降順＋短期線が下向き＋早期警戒なし | ショート候補 |

さらに、長期線の向きが変わる前の切り返し・崩れを「転換の初動」として優先表示します（設定でオフ可）。

| 表示 | 意味 | 目安 |
|---|---|---|
| 🚀 上昇転換の初動 | 下降・レンジ中に、5本以内で次のうち2つ以上：出来高を伴う上方向の窓／戻り高値の上抜け／長期線の回復。終値は短期線の上 | 試し玉（小さく・損切り必須）。🟢か最初の押し目で買い増し |
| 🔻 下降転換の初動 | 上昇・レンジ中に、上の逆が2つ以上。終値は短期線の下 | ロングの縮小を検討。ショートの試し玉候補 |

※ 売買のシグナルではなく、現在地を把握するための表示です。初動は早い分ダマシも多いので、必ず損切りの位置を決めてから使ってください。

---

## 8. 調べた情報の信頼度

### 比較的信頼できる情報（研究・定評のある解説）
- **Faber（2007）:** 10か月移動平均（≒200日線）のルールは、リターンを上げるというより **値動き（ボラティリティ）を抑える** のが主な効果。本人も目的をそう書いている。
- **Siegel（『Stocks for the Long Run』）:** 200日線ルールはリスクを考えた成績で優位。ただし検証に使った期間と同じ期間で条件を決めている（インサンプル）という限界がある。
- **John Murphy（StockCharts）:** 20日＝短期、50日＝中期、200日＝長期トレンドという定番の分け方。
- **AAII（米国個人投資家協会）:** 「市場が調整すると4銘柄中3銘柄が下がる」というO'Neilの主張を紹介。元の統計データは確認できていない。

### その他（メディア・証券会社・ブログ。手法がバラバラで直接比べられない）
- デッドクロスは遅れて出る指標で、出た時点で既に10〜20%下げていることが多い。
- S&P500の50年間・24回のデッドクロスのうち、その後さらに下げたのは約46%（Reuters、他の記事からの孫引き）。
- 200日線が下向きのときのデッドクロスは、その後の成績がはっきり悪い（BofA、他の記事からの孫引き）。
- RSラインの早期警戒としての使い方は、実務家の経験則が中心。タイミングの精度をきちんと検証した研究は見つからなかった。

### Claudeの知識・意見（データの裏付けなし）
- 米国では100日線は50日線・200日線ほど注目されていない。
- 4時間足の200EMAが日足で何日分にあたるかは、取引時間からの計算（チャートの設定によって変わる）。

---

## 参考リンク

- [Faber timing model (quantstrat docs)](https://www.rdocumentation.org/packages/quantstrat/versions/0.8.2/topics/stratFaber)
- [Faber論文 (SSRN写し)](https://www.scribd.com/doc/116881446/SSRN-id962461)
- [Swedroe: Why Financial Trends Persist (ETF.com)](https://www.etf.com/sections/index-investor-corner/swedroe-why-financial-trends-persist)
- [John Murphy's Law #6 (StockCharts)](https://articles.stockcharts.com/article/stockcharts-insider-john-murphys-law-6-follow-that-average-moving-averages)
- [StockCharts ChartSchool: Price to MA crossovers](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/moving-average-trading-strategies/how-to-trade-price-to-moving-average-crossovers)
- [AAII: The Big Picture – How to Determine the Stock Market's Direction](https://www.aaii.com/journal/article/the-big-picture-how-to-determine-the-stock-market-s-direction)
- [AAII: William O'Neil's CAN SLIM Approach](https://www.aaii.com/journal/article/william-oneil-can-slim-approach-to-selecting-growth-stocks)
- [Nasdaq: Historical perspective on S&P 500 death cross](https://www.nasdaq.com/articles/some-historical-perspective-on-the-sp-500-index-death-cross)
- [What we've learned from 97 years of death crosses](https://proactiveadvisormagazine.com/what-weve-learned-from-97-years-of-death-crosses/)
- [Fisher Investments: Don't fear the death cross](https://www.fisherinvestments.com/en-us/marketminder/dont-fear-the-death-cross)
- [StockCharts: This Relative Strength Signal Can Provide Early Warning Signs](https://articles.stockcharts.com/article/articles-stocktalk-2023-11-this-relative-strength-signal-774/)
- [StockCharts (Arthur Hill): Techniques to Spot Early Signs of Relative Strength](https://stockcharts.com:443/articles/arthurhill/2019/02/techniques-to-spot-early-signs-of-relative-strength.html)
- [Schaeffer's: Relative Strength](https://schaeffersresearch.com/education/expectational-analysis/technical-analysis/relative-strength)

> 本ドキュメントは情報整理を目的としたもので、投資助言ではありません。
