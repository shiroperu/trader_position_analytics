# Hyperliquid Position Tracker

Hyperliquid DEX の上位トレーダー26名のperps（永久先物）ポジションを定期取得し、トークンごとのLONG/SHORT センチメント分析を行うシステム。

## 概要

Hyperliquid の収益ランキング上位100名から選定した26名のトレーダーのポジション動向をウォッチし、市場のセンチメントやトレンドを把握する。

### 主な機能

- **Phase 1 — ポジション取得**: Hyperliquid API から26名のポジション情報を取得し、Excel出力
- **Phase 2 — センチメント分析**: トークンごとのLONG/SHORT比率、P&L、レバレッジを集計・可視化
- **自動実行**: launchd による4時間間隔スケジューリング（0:00, 4:00, 8:00, 12:00, 16:00, 20:00）
- **トレンド比較**: 前回実行結果との差分を検出し、センチメント変化を追跡

## セットアップ

### 前提条件

- Python 3.10+
- macOS（launchd スケジューリング使用時）
- インターネット接続（Hyperliquid API アクセス）

### インストール

```bash
# リポジトリをクローン
git clone <repository-url>
cd trader_position_analytics

# 仮想環境を作成・有効化
python3 -m venv .venv
source .venv/bin/activate

# 依存パッケージをインストール
pip install -r requirements.txt
```

> **Note**: 以降のコマンド実行前に `source .venv/bin/activate` で仮想環境を有効化してください。

### 依存パッケージ

| パッケージ | バージョン | 用途 |
|-----------|-----------|------|
| requests | 2.32.3 | Hyperliquid API 呼び出し |
| openpyxl | 3.1.5 | Excel ファイル生成・スタイリング |
| pandas | 2.2.3 | データ操作ユーティリティ |
| chromadb | 0.6.3 | ベクトルDB（セマンティック検索・RAG連携） |

## 使い方

### 手動実行

```bash
# 全フェーズ一括実行（推奨）
python3 scripts/run_all.py

# Phase 1 のみ（ポジション取得）
python3 scripts/fetch_positions.py

# Phase 2 のみ（センチメント分析）
python3 scripts/analyze_sentiment.py
```

### 自動スケジューリング（launchd）

```bash
# plist を登録
cp com.dothax.hl-tracker.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.dothax.hl-tracker.plist

# ステータス確認
launchctl list | grep hl-tracker

# 停止・解除
launchctl unload ~/Library/LaunchAgents/com.dothax.hl-tracker.plist
```

## 出力ファイル

### Phase 1: ポジションデータ

`data/hl_positions_YYYY-MM-DD_HH-mm.xlsx`

| カラム | 内容 |
|--------|------|
| Tier | トレーダーランク（T1〜T4） |
| Trader | トレーダー名 |
| Acct Value($) | アカウント評価額 |
| Coin | トークン名 |
| Side | LONG / SHORT |
| Size | ポジションサイズ |
| Leverage | レバレッジ倍率 |
| Entry Px | エントリー価格 |
| Pos Value($) | ポジション評価額 |
| Unrealized PnL($) | 未実現損益 |
| ROE(%) | 自己資本利益率 |
| Liq Px | 清算価格 |
| Margin($) | 証拠金 |
| Cum Funding($) | 累積ファンディング |

### Phase 2: センチメント分析

`data/hl_analysis_YYYY-MM-DD_HH-mm.xlsx`（4シート）

| シート | 内容 |
|--------|------|
| Token Sentiment | トークンごとのセンチメント集計（19カラム） |
| Top30 Chart | LONG vs SHORT 積み上げ棒グラフ |
| Trader x Token Matrix | トレーダー×トークンのL/S/–マトリクス |
| Legend & Notes | メタデータ、センチメント基準、データサマリー |

#### センチメント判定基準

| ラベル | 条件 |
|--------|------|
| Strong LONG | LONG比率 > 70% |
| Lean LONG | LONG比率 > 55% |
| Neutral | 45% 〜 55% |
| Lean SHORT | SHORT比率 > 55% |
| Strong SHORT | SHORT比率 > 70% |

## 監視対象トレーダー

26名を4つのTierに分類：

| Tier | 分類 | 人数 | 例 |
|------|------|------|-----|
| T1 | Institution / Famous | 4 | BobbyBigSize, Auros |
| T2 | Jeff Group | 6 | jefe 等 |
| T3 | Community Notable | 10 | 憨巴小龙, wanyekest 等 |
| T4 | Anonymous High PNL | 6 | 匿名アドレス |

## プロジェクト構成

```
trader_position_analytics/
├── scripts/
│   ├── config.py                 # 設定（トレーダー一覧、API設定、スタイル）
│   ├── fetch_positions.py        # Phase 1: ポジション取得
│   ├── analyze_sentiment.py      # Phase 2: センチメント分析
│   ├── run_all.py                # メインエントリーポイント
│   ├── store_chromadb.py         # Phase 3: ChromaDB保存
│   ├── query_chromadb.py         # ChromaDBクエリツール
│   └── test_edge_cases.py        # エッジケーステスト
├── data/                         # 出力Excel（実行時生成）
├── chromadb_data/                # ChromaDB永続データ（実行時生成）
├── logs/                         # ログファイル（実行時生成）
├── sample/                       # サンプル・参考ファイル
├── requirements.txt              # Python依存パッケージ
├── REQUIREMENTS.md               # 技術要件定義書
└── com.dothax.hl-tracker.plist   # launchd スケジュール設定
```

## 実行フロー

```
launchd（4時間間隔）
    │
    ▼
run_all.py
    │
    ├── Phase 1: fetch_positions.py
    │   └── Hyperliquid API × 26トレーダー
    │   └── data/hl_positions_*.xlsx 出力
    │
    ├── Phase 2: analyze_sentiment.py
    │   └── ポジションデータ読み込み
    │   └── トークンごと集計・前回比較
    │   └── data/hl_analysis_*.xlsx 出力（4シート）
    │
    ├── Phase 3: store_chromadb.py
    │   └── センチメント・マトリクスデータをChromaDBに保存
    │   └── セマンティック検索・時系列分析・RAG連携用
    │
    └── logs/hl_*.log
```

## 技術仕様

- **API**: `POST https://api.hyperliquid.xyz/info`（clearinghouse state）
- **レート制限**: リクエスト間1秒インターバル
- **リトライ**: 失敗時3秒待機後にリトライ（個別トレーダー単位でスキップ）
- **タイムアウト**: 15秒
- **Excelスタイル**: ダークテーマ（LONG=緑, SHORT=赤）
- **ChromaDB**: ローカル永続ストレージ（`chromadb_data/`）、デフォルト埋め込みモデル使用

## ChromaDB データストレージ

Phase 3 で分析結果を ChromaDB に保存し、セマンティック検索・時系列分析・RAG連携を実現する。

### コレクション

| コレクション | 内容 | ドキュメント例 |
|---|---|---|
| `token_sentiment` | トークンごとのセンチメント集計 | "BTC: Strong LONG sentiment. 8 long vs 2 short traders (80% long)..." |
| `trader_token_matrix` | トレーダー×トークンのポジション | "BobbyBigSize (T1, account $17.3M) is SHORT on BTC." |

### クエリツール

```bash
# セマンティック検索
python3 scripts/query_chromadb.py search "bullish tokens"
python3 scripts/query_chromadb.py search "high leverage positions" -c trader_token_matrix

# 特定トークンの履歴
python3 scripts/query_chromadb.py history BTC --limit 30

# トレンドデータ
python3 scripts/query_chromadb.py trend ETH --last 20

# 保存済みスナップショット一覧
python3 scripts/query_chromadb.py snapshots

# スナップショットサマリー
python3 scripts/query_chromadb.py summary 2026-03-08_12-00

# トレーダーのポジション
python3 scripts/query_chromadb.py trader BobbyBigSize
```

### RAG 連携

外部の LLM アプリケーションから利用する場合:

```python
from scripts.query_chromadb import semantic_search

results = semantic_search(
    "What is the current market sentiment for altcoins?",
    n_results=20,
)
# results にはドキュメント + メタデータが含まれ、LLM のコンテキストとして使用可能
```

> **Note**: 初回実行時に埋め込みモデル（all-MiniLM-L6-v2、約80MB）が自動ダウンロードされます。

## ライセンス

Private
