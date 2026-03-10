# Hyperliquid Position Tracker — 要件定義書

## 1. プロジェクト概要

Hyperliquid DEX（分散型取引所）の上位トレーダー26名のperps（永久先物）ポジションを定期的に取得し、トークンごとのLONG/SHORT センチメント分析を行うシステム。

### 1.1 背景

- Hyperliquidの収益ランキング上位100名から、有名・高勝率のトレーダー26名を選定済み
- 彼らのポジション動向をウォッチすることで、市場のセンチメントやトレンドを把握する

### 1.2 現行システムの課題

現在はCowork（Claude Desktop）のスケジュールタスクで運用しているが、以下の問題がある：

- Chrome拡張経由でAPI呼び出しするため**処理時間が長い**（数分〜十数分）
- Chrome拡張の接続切断で**実行失敗**が頻発（エラーログ3件/10回実行）
- VM環境のプロキシ制限により**直接APIアクセス不可**（Chrome JS経由が必須）
- データ転送時の**チャンク分割**が必要（JS→VM間のサイズ制限）

### 1.3 新システムの方針

macOS上でPythonスクリプトを直接実行し、Hyperliquid APIを直接呼び出す。Chrome/Cowork/VM一切不要。

---

## 2. システム構成

### 2.1 実行環境

| 項目 | 値 |
|------|-----|
| OS | macOS (Apple Silicon) |
| Python | 3.10+ |
| 実行方式 | launchdによる定期実行（cron代替） |
| 外部依存 | requests, openpyxl, pandas（オプション） |
| ネットワーク | インターネット直接接続（プロキシなし） |

### 2.2 ディレクトリ構成

```
/Users/shiroperu/Documents/workspace/HYPE_position/
├── scripts/
│   ├── fetch_positions.py      # Phase1: ポジション取得
│   ├── analyze_sentiment.py    # Phase2: センチメント分析
│   ├── run_all.py              # メインエントリポイント（Phase1+2を順次実行）
│   └── config.py               # トレーダーリスト・設定定数
├── data/
│   ├── hl_positions_YYYY-MM-DD_HH-mm.xlsx    # ポジションスナップショット
│   └── hl_analysis_YYYY-MM-DD_HH-mm.xlsx     # センチメント分析結果
├── logs/
│   └── hl_YYYY-MM-DD_HH-mm.log               # 実行ログ
├── com.dothax.hl-tracker.plist                # launchd設定ファイル
└── REQUIREMENTS.md                             # 本ドキュメント
```

---

## 3. ウォッチ対象トレーダー

### 3.1 トレーダーリスト（26名・4 Tier）

| Tier | Rank | Name | Address | 備考 |
|------|------|------|---------|------|
| ⭐ T1 | 1 | BobbyBigSize | `0x7fdafde5cfb5465924316eced2d3715494c517d1` | Fasanara Capital関連。ショート専門 |
| ⭐ T1 | 8 | x.com/SilkBtc | `0x880ac484a1743862989a441d6d867238c7aa311c` | X(Twitter)アカウント公開済 |
| ⭐ T1 | 17 | Auros | `0x023a3d058020fb76cca98f01b3c48c8938a22355` | 機関マーケットメイカー。取引高$225B |
| ⭐ T1 | 38 | ABC | `0x162cc7c861ebd0c06b3d72319201150482518185` | アルゴトレーダー。取引高$55.8B |
| 🔗 T2 | 4 | thank you jefef | `0xfae95f601f3a25ace60d19dbb929f2a5c57e3571` | Jeff系グループ（合算$316M+） |
| 🔗 T2 | 15 | jefe | `0x51156f7002c4f74f4956c9e0f2b7bfb6e9dbfac2` | Jeff系グループ |
| 🔗 T2 | 43 | fuck jeff gib S3 | `0xa464abbf049fb75585484addcbc00169062e813a` | Jeff系グループ |
| 🔗 T2 | 58 | NMTD -Thank you Jeff | `0xf517639a8872e756ac98d3c65507d2ebc25cc032` | Jeff系グループ |
| 🔗 T2 | 79 | thank you jeffff | `0x5c02f2dfcb6537b83929596fe8a3278e237e3e7c` | Jeff系グループ |
| 🔗 T2 | 88 | thank you JEFF | `0x2d23b731e5f04996a2dfdbe434c7d922afdb5e00` | Jeff系グループ |
| 📊 T3 | 20 | 憨巴小龙 | `0x8e096995c3e4a3f0bc5b3ea1cba94de2aa4d70c9` | 中国語圏の大物 |
| 📊 T3 | 59 | 韦小宝.eth | `0x99b1098d9d50aa076f78bd26ab22e6abd3710729` | ENSユーザー |
| 📊 T3 | 61 | SSS888 | `0x598f9efb3164ec216b4eff33c2b239605be5af8e` | 残高$16→PNL $24M |
| 📊 T3 | 64 | wanyekest | `0x8607a7d180de23645db594d90621d837749408d5` | $13.3M安定残高 |
| 📊 T3 | 65 | Prison Su Zhu | `0xdafc555a97b358bc09fccf4c0e583c1ec5838b16` | Su Zhuパロディ名 |
| 📊 T3 | 67 | EARLY | `0x1da722cfa8b2dfda57cf8d787689039c7a63f049` | HYPE初期参入者 |
| 📊 T3 | 68 | Penision Fund | `0x0ddf9bae2af4b874b96d287a5ad42eb47138a902` | $32.6M安定残高 |
| 📊 T3 | 76 | demo_account | `0x34971bc50eb4484505e4a24516c8db843fbef162` | |
| 📊 T3 | 80 | VidaBWE | `0x71dfc07de32c2ebf1c4801f4b1c9e40b76d4a23d` | $15M安定残高 |
| 📊 T3 | 96 | jez | `0xaa7577a7a27aa7fcf6d0ec481b87df3ad0f6a88e` | |
| 🔍 T4 | 1 | 0xecb6...2b00 | `0xecb63caa47c7c4e77f60f1ce858cf28dc2b82b00` | 全期間PNL 1位 |
| 🔍 T4 | 2 | 0x5b5d...c060 | `0x5b5d51203a0f9079f8aeb098a6523a13f298c060` | |
| 🔍 T4 | 5 | 0x9794...333b | `0x9794bbbc222b6b93c1417d01aa1ff06d42e5333b` | 残高$1,395→PNL $144M |
| 🔍 T4 | 6 | 0x20c2...44f5 | `0x20c2d95a3dfdca9e9ad12794d5fa6fad99da44f5` | |
| 🔍 T4 | 9 | 0x2ea1...23f4 | `0x2ea18c23f72a4b6172c55b411823cdc5335923f4` | 残高$1.99 |
| 🔍 T4 | 10 | 0xbde2...60b1 | `0xbde2ddc49a2e6827300faa6afc93d572114a60b1` | 残高$1.01。ROI最高 |

### 3.2 Tier分類基準

| Tier | 名称 | 基準 |
|------|------|------|
| T1 | 機関・有名 | 身元が特定されている、または機関投資家 |
| T2 | Jeff系グループ | 相互関連する複数ウォレット群 |
| T3 | コミュニティ注目 | ユニークな名前や特徴的な取引パターンを持つ |
| T4 | 匿名高PNL | 名前未設定だがPNLが極めて高い |

---

## 4. Phase 1: ポジション取得（fetch_positions.py）

### 4.1 API仕様

| 項目 | 値 |
|------|-----|
| エンドポイント | `POST https://api.hyperliquid.xyz/info` |
| Content-Type | `application/json` |
| リクエストボディ | `{"type": "clearinghouseState", "user": "<address>"}` |
| レート制限 | 明示なし（1秒間隔推奨） |
| タイムアウト | 15秒/リクエスト |

### 4.2 APIレスポンス構造

```json
{
  "marginSummary": {
    "accountValue": "17303621.345"
  },
  "assetPositions": [
    {
      "position": {
        "coin": "BTC",
        "szi": "42.13843",          // 正=LONG, 負=SHORT
        "leverage": {"type": "cross", "value": 20},
        "entryPx": "67850.0",
        "positionValue": "3022589.58",
        "unrealizedPnl": "163496.44",
        "returnOnEquity": "1.1437",
        "liquidationPx": null,       // null = クロスマージンで清算なし
        "marginUsed": "151129.48",
        "cumFunding": {
          "sinceOpen": "311.71"
        }
      }
    }
  ]
}
```

### 4.3 出力ファイル：hl_positions_YYYY-MM-DD_HH-mm.xlsx

**シート名**: `Positions YYYY-MM-DD`

| 列名 | 型 | 説明 |
|------|-----|------|
| Tier | string | T1〜T4（トレーダーの最初の行のみ、以降は空） |
| Trader | string | トレーダー表示名（最初の行のみ） |
| Acct Value($) | float | アカウント残高 (marginSummary.accountValue) |
| Coin | string | トークンシンボル（例: BTC, ETH） |
| Side | string | `LONG` or `SHORT`（sziの正負で判定） |
| Size | float | ポジション数量（sziの絶対値） |
| Leverage | float | レバレッジ倍率 |
| Entry Px | float | エントリー価格 |
| Pos Value($) | float | ポジション価値（USD） |
| Unrealized PnL($) | float | 未実現損益 |
| ROE(%) | float | returnOnEquity × 100 |
| Liq Px | float | 清算価格（nullの場合は空欄） |
| Margin($) | float | 使用マージン |
| Cum Funding($) | float | 累積ファンディング |

**補足ルール**:
- ポジションなしのトレーダーは `Coin = "(No positions)"` で1行出力
- `szi == 0` のポジションはスキップ
- Tier, Trader, Acct Value列はトレーダーごとの最初の行のみ値を入れ、以降は空（グループ表示）

### 4.4 エラーハンドリング

- API呼び出し失敗時: そのトレーダーをスキップし、ログに記録。他のトレーダーの処理は続行
- 全トレーダー失敗時: エラーログのみ出力し、Excelファイルは生成しない
- リトライ: 1回失敗したら3秒待って1回リトライ

---

## 5. Phase 2: センチメント分析（analyze_sentiment.py）

### 5.1 分析ロジック

Phase 1で生成されたポジションExcelを入力とし、トークンごとに以下を集計する。

#### 5.1.1 トークン別集計項目

| 項目 | 算出方法 |
|------|---------|
| LONG人数 | そのトークンでLONGポジションを持つユニークトレーダー数 |
| SHORT人数 | そのトークンでSHORTポジションを持つユニークトレーダー数 |
| LONG比率 | LONG人数 / (LONG人数 + SHORT人数) |
| SHORT比率 | SHORT人数 / (LONG人数 + SHORT人数) |
| LONG価値 | LONGポジションのpositionValue合計 |
| SHORT価値 | SHORTポジションのpositionValue合計 |
| 合計価値 | LONG価値 + SHORT価値 |
| ネット方向 | LONG価値 - SHORT価値（正=LONG優勢、負=SHORT優勢） |
| LONG PnL | LONGポジションの未実現PnL合計 |
| SHORT PnL | SHORTポジションの未実現PnL合計 |
| 合計PnL | LONG PnL + SHORT PnL |
| 平均レバレッジ | LONG/SHORTそれぞれの平均レバレッジ |

#### 5.1.2 センチメント判定基準

| 判定 | 条件 |
|------|------|
| 🟢 Strong LONG | LONG比率 >= 70% |
| ↗ Lean LONG | LONG比率 55%〜69% |
| ⚖ Neutral | LONG比率 = 50% |
| ↘ Lean SHORT | SHORT比率 55%〜69% |
| 🔴 Strong SHORT | SHORT比率 >= 70% |

#### 5.1.3 前回比較（変動率算出）

同フォルダ内の `hl_positions_*.xlsx` を日付順にソートし、最新の1つ前のファイルと比較する。

| 変動指標 | 算出方法 |
|---------|---------|
| LONG比率変化(pt) | 今回LONG比率 - 前回LONG比率（パーセントポイント差） |
| 価値変動率(%) | (今回合計価値 - 前回合計価値) / 前回合計価値 × 100 |
| トレーダー数変化 | 今回合計トレーダー数 - 前回合計トレーダー数 |

前回ファイルが存在しない場合は、変動率列を空欄とする。

### 5.2 出力ファイル：hl_analysis_YYYY-MM-DD_HH-mm.xlsx

**4シート構成**:

#### Sheet 1: Token Sentiment

トークンごとのLONG/SHORT比率一覧。合計価値の降順でソート。

列: Rank, Token, LONG人数, SHORT人数, 合計, LONG比率, SHORT比率, センチメント, LONG価値($), SHORT価値($), 合計価値($), ネット方向($), LONG PnL($), SHORT PnL($), 合計PnL($), 平均Lev(L/S), LONG比率変化(pt), 価値変動率(%), トレーダー数変化

#### Sheet 2: Top30 Chart

合計価値上位30トークンのLONG vs SHORT 積み上げ棒グラフ（openpyxlのBarChart使用）。

#### Sheet 3: Trader×Token Matrix

行: アクティブトレーダー（ポジション保有者のみ）
列: 合計価値上位30トークン
セル: `L`（LONG）/ `S`（SHORT）/ `―`（ポジションなし）

#### Sheet 4: 凡例・注記

- データ取得日時
- 比較対象ファイル名
- センチメント判定基準
- 対象トレーダー数、総ポジション数

### 5.3 Excelスタイリング

ダークテーマを採用（現行と同一）:

| 要素 | カラーコード |
|------|------------|
| 背景 | `#0D1117` |
| ヘッダー背景 | `#1B2A3D` |
| ヘッダーフォント | 白 `#FFFFFF`, Arial 10pt Bold |
| データフォント | 白系 `#CCCCCC`, Arial 9pt |
| LONG系カラー | 緑 `#00FF88` |
| SHORT系カラー | 赤 `#FF6666` |
| アクセントカラー | ゴールド `#FFD700` |
| PnL正 | 緑 `#00FF88` |
| PnL負 | 赤 `#FF6666` |
| LONG行背景 | `#0A2E1A` |
| SHORT行背景 | `#2E0A0A` |
| 罫線 | `#333333` thin |
| ヘッダー下線 | `#00D4AA` medium |

---

## 6. 定期実行（launchd）

### 6.1 実行スケジュール

4時間ごと（0:00, 4:00, 8:00, 12:00, 16:00, 20:00）

### 6.2 launchd plist設定

ファイル: `~/Library/LaunchAgents/com.dothax.hl-tracker.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.dothax.hl-tracker</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/shiroperu/Documents/workspace/HYPE_position/scripts/run_all.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <array>
        <dict><key>Hour</key><integer>0</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Hour</key><integer>4</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Hour</key><integer>12</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Hour</key><integer>16</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Hour</key><integer>20</integer><key>Minute</key><integer>0</integer></dict>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/shiroperu/Documents/workspace/HYPE_position</string>
    <key>StandardOutPath</key>
    <string>/Users/shiroperu/Documents/workspace/HYPE_position/logs/launchd_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/shiroperu/Documents/workspace/HYPE_position/logs/launchd_stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

### 6.3 セットアップ手順

```bash
# 1. 依存パッケージインストール
pip3 install requests openpyxl pandas

# 2. ディレクトリ作成
mkdir -p ~/Documents/workspace/HYPE_position/{scripts,data,logs}

# 3. スクリプト配置（Claude Codeで生成）

# 4. launchd登録
cp com.dothax.hl-tracker.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.dothax.hl-tracker.plist

# 5. 手動テスト実行
python3 scripts/run_all.py

# 6. 状態確認
launchctl list | grep hl-tracker
```

### 6.4 停止・再開

```bash
# 一時停止
launchctl unload ~/Library/LaunchAgents/com.dothax.hl-tracker.plist

# 再開
launchctl load ~/Library/LaunchAgents/com.dothax.hl-tracker.plist
```

---

## 7. ログ仕様

### 7.1 実行ログ（logs/hl_YYYY-MM-DD_HH-mm.log）

```
2026-03-08 12:00:01 [INFO] === Hyperliquid Position Tracker Started ===
2026-03-08 12:00:01 [INFO] Phase 1: Fetching positions for 26 traders
2026-03-08 12:00:02 [INFO]   [T1] BobbyBigSize: 23 positions (Acct: $17,303,621)
2026-03-08 12:00:03 [INFO]   [T1] x.com/SilkBtc: 16 positions (Acct: $4,037,718)
...
2026-03-08 12:00:30 [INFO] Phase 1 complete: 391 positions from 13 active traders
2026-03-08 12:00:30 [INFO] Saved: data/hl_positions_2026-03-08_12-00.xlsx
2026-03-08 12:00:31 [INFO] Phase 2: Analyzing sentiment (166 tokens)
2026-03-08 12:00:31 [INFO] Comparing with: data/hl_positions_2026-03-08_08-00.xlsx
2026-03-08 12:00:32 [INFO] Saved: data/hl_analysis_2026-03-08_12-00.xlsx
2026-03-08 12:00:32 [INFO] === Complete (31.2s) ===
```

### 7.2 エラー時

```
2026-03-08 12:00:15 [WARNING] [T3] SSS888: API timeout, retrying...
2026-03-08 12:00:19 [ERROR] [T3] SSS888: Failed after retry: ConnectionError
```

---

## 8. Coworkスケジュールタスクからの移行

### 8.1 移行手順

1. 新システム（Python + launchd）をセットアップ・テスト実行
2. 正常動作を確認後、Coworkのスケジュールタスク `hl-position-snapshot` を無効化
3. 既存の `~/.claude/settings.json` のChrome許可設定は削除可能

### 8.2 既存データの扱い

- `HYPE_position/` フォルダ直下の既存ファイル（hl_positions_*.xlsx, hl_analysis_*.xlsx）はそのまま保持
- 新システムでは `data/` サブフォルダに出力するため、既存ファイルとは混在しない
- 前回比較は `data/` フォルダ内のファイルのみを対象とする

---

## 9. 将来の拡張可能性（スコープ外）

- Slack/Discord通知: 大幅なセンチメント変化時にアラート
- Webダッシュボード: 時系列チャートのHTMLレポート生成
- トレーダー追加/削除: config.pyの編集で対応可能な設計とする
- マルチタイムフレーム分析: 4時間/日次/週次の比較
