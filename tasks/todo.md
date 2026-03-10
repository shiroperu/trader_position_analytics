# Hyperliquid Position Tracker — 開発計画

> **仕様書**: [REQUIREMENTS.md](../REQUIREMENTS.md)
> **ステータス**: 🟢 完了
> **最終更新**: 2026-03-09

---

## Phase 0: 環境準備・基盤構築

> **担当**: python-engineer
> **依存**: なし
> **検証**: ディレクトリ構造が存在し、config.pyがimportできること

- [x] **0-1** ディレクトリ構成の作成
  - `scripts/`, `data/`, `logs/` を作成
- [x] **0-2** Python依存ライブラリのインストール
  - `pip3 install requests openpyxl pandas`
  - requirements.txt の作成（バージョン固定）
- [x] **0-3** `scripts/config.py` — トレーダーリスト・設定定数の定義
  - 26名のトレーダー情報（Tier, Name, Address, 備考）
  - T1: 4名、T2: 6名、T3: 10名、T4: 6名 ※REQUIREMENTS.md §3.1
  - API設定定数（エンドポイント、タイムアウト、リトライ間隔）
  - ファイルパス定数（data/, logs/ のパス）
  - Excelスタイリング定数（ダークテーマカラーコード）※REQUIREMENTS.md §5.3
- [x] **0-4** ロギング共通設定
  - ログ形式: `YYYY-MM-DD HH:MM:SS [LEVEL] メッセージ` ※REQUIREMENTS.md §7.1
  - ファイル出力 + コンソール出力の両方対応
  - ファイル名: `logs/hl_YYYY-MM-DD_HH-mm.log`

---

## Phase 1: ポジション取得（fetch_positions.py）

> **担当**: python-engineer → code-reviewer
> **依存**: Phase 0 完了
> **検証**: 実際のAPI呼び出しで26名分のデータ取得、Excel生成確認
> **仕様**: REQUIREMENTS.md §4

- [x] **1-1** Hyperliquid API呼び出し実装
  - エンドポイント: `POST https://api.hyperliquid.xyz/info`
  - リクエストボディ: `{"type": "clearinghouseState", "user": "<address>"}`
  - レート制限: 1秒間隔 ※REQUIREMENTS.md §4.1
  - タイムアウト: 15秒/リクエスト
- [x] **1-2** APIレスポンスのパース
  - `marginSummary.accountValue` → Acct Value
  - `assetPositions[].position` → 各ポジションデータ
  - szi符号判定: 正=LONG、負=SHORT、0=スキップ ※REQUIREMENTS.md §4.2
- [x] **1-3** エラーハンドリング
  - API失敗 → そのトレーダーをスキップ、ログ記録、他は続行
  - 全トレーダー失敗 → エラーログのみ、Excel生成しない
  - リトライ: 1回失敗 → 3秒待機 → 1回リトライ ※REQUIREMENTS.md §4.4
- [x] **1-4** Excel出力: `data/hl_positions_YYYY-MM-DD_HH-mm.xlsx`
  - シート名: `Positions YYYY-MM-DD`
  - 14列の正確な構成（Tier〜Cum Funding）※REQUIREMENTS.md §4.3
  - Tier/Trader/Acct Value列: トレーダーごとの最初の行のみ値（グループ表示）
  - ポジションなしトレーダー: `Coin = "(No positions)"` で1行出力
  - ダークテーマスタイリング適用 ※REQUIREMENTS.md §5.3
- [x] **1-5** Phase 1 単体テスト実行
  - `python3 scripts/fetch_positions.py` で正常動作確認
  - 生成されたExcelファイルの列構成・データ内容を目視確認
- [x] **1-6** code-reviewer によるPhase 1レビュー
  - REQUIREMENTS.md §4 との整合性チェック
  - 指摘事項の修正完了

---

## Phase 2: センチメント分析（analyze_sentiment.py）

> **担当**: python-engineer → code-reviewer → blockchain-chart-analyst
> **依存**: Phase 1 完了（入力ファイルが必要）
> **検証**: Phase 1出力を入力として正しく分析結果が生成されること
> **仕様**: REQUIREMENTS.md §5

- [x] **2-1** トークン別集計ロジック
  - LONG/SHORT人数（ユニークトレーダー数）
  - LONG/SHORT比率
  - LONG/SHORT価値（positionValue合計）
  - ネット方向（LONG価値 - SHORT価値）
  - LONG/SHORT PnL（未実現PnL合計）
  - 平均レバレッジ（LONG/SHORT別）※REQUIREMENTS.md §5.1.1
- [x] **2-2** センチメント判定
  - 🟢 Strong LONG: LONG比率 >= 70%
  - ↗ Lean LONG: LONG比率 55%〜69%
  - ⚖ Neutral: LONG比率 = 50%
  - ↘ Lean SHORT: SHORT比率 55%〜69%
  - 🔴 Strong SHORT: SHORT比率 >= 70% ※REQUIREMENTS.md §5.1.2
- [x] **2-3** 前回比較ロジック
  - `data/hl_positions_*.xlsx` を日付順ソート、最新の1つ前と比較
  - LONG比率変化（パーセントポイント差）
  - 価値変動率（%）
  - トレーダー数変化
  - 前回ファイルなし → 変動率列を空欄 ※REQUIREMENTS.md §5.1.3
- [x] **2-4** Sheet 1: Token Sentiment
  - トークン別LONG/SHORT比率一覧
  - 合計価値の降順でソート ※REQUIREMENTS.md §5.2 Sheet 1
- [x] **2-5** Sheet 2: Top30 Chart
  - 合計価値上位30トークンのLONG vs SHORT積み上げ棒グラフ
  - openpyxlのBarChart使用 ※REQUIREMENTS.md §5.2 Sheet 2
- [x] **2-6** Sheet 3: Trader×Token Matrix
  - 行: アクティブトレーダー（ポジション保有者のみ）
  - 列: 合計価値上位30トークン
  - セル: L / S / ― ※REQUIREMENTS.md §5.2 Sheet 3
- [x] **2-7** Sheet 4: 凡例・注記
  - データ取得日時、比較対象ファイル名
  - センチメント判定基準、対象トレーダー数、総ポジション数 ※REQUIREMENTS.md §5.2 Sheet 4
- [x] **2-8** ダークテーマスタイリング適用
  - 全4シートにREQUIREMENTS.md §5.3のカラー適用
  - LONG行背景 `#0A2E1A` / SHORT行背景 `#2E0A0A`
- [x] **2-9** Phase 2 単体テスト実行
  - Phase 1で生成したExcelを入力として `python3 scripts/analyze_sentiment.py` 実行
  - 4シートの生成・内容を確認
- [x] **2-10** code-reviewer によるPhase 2レビュー
  - REQUIREMENTS.md §5 との整合性チェック
  - 指摘事項の修正完了
- [x] **2-11** blockchain-chart-analyst による分析結果の妥当性検証
  - センチメント判定が合理的か
  - チャート・マトリクスの情報価値

---

## Phase 3: 統合・定期実行

> **担当**: python-engineer → code-reviewer
> **依存**: Phase 2 完了
> **検証**: run_all.pyで一気通貫実行し、data/とlogs/にファイルが正しく生成されること
> **仕様**: REQUIREMENTS.md §6

- [x] **3-1** `scripts/run_all.py` — メインエントリポイント
  - Phase 1（fetch_positions.py）→ Phase 2（analyze_sentiment.py）の順次実行
  - 全体の実行時間計測・ログ出力
  - Phase 1失敗時にPhase 2をスキップするハンドリング
- [x] **3-2** 統合テスト実行
  - `python3 scripts/run_all.py` で一気通貫実行
  - data/ に2ファイル（positions, analysis）が生成されること
  - logs/ にログファイルが生成されること
  - ログ内容がREQUIREMENTS.md §7.1の形式と一致すること
- [x] **3-3** launchd plist設定ファイルの作成
  - `com.dothax.hl-tracker.plist` ※REQUIREMENTS.md §6.2
  - 4時間ごと（0:00, 4:00, 8:00, 12:00, 16:00, 20:00）
  - WorkingDirectory, 環境変数PATH設定
- [x] **3-4** launchd登録・動作確認
  - plistを `~/Library/LaunchAgents/` にコピー
  - `launchctl load` で登録
  - `launchctl list | grep hl-tracker` で状態確認（exit 0 確認済み）
- [x] **3-5** code-reviewer による統合レビュー
  - run_all.py + plistのレビュー（Phase 4全体レビューに含めて実施）
  - 指摘事項の修正完了

---

## Phase 4: 品質保証・本番移行

> **担当**: code-reviewer, blockchain-chart-analyst, python-engineer
> **依存**: Phase 3 完了
> **検証**: 全レビュー指摘解消、エッジケーステスト通過

- [x] **4-1** code-reviewer による全体コードレビュー
  - 全4スクリプトのREQUIREMENTS.md完全整合性チェック
  - セキュリティ（APIレスポンスの安全なパース）
  - パフォーマンス（API呼び出し効率、メモリ使用量）
  - 1st review: FAIL (Must Fix 3件, Should Fix 3件)
  - 2nd review: PASS (全6件修正確認済み)
- [x] **4-2** エッジケーステスト
  - 全API失敗時の挙動（Excel未生成、エラーログのみ）
  - ポジションなしトレーダーの表示
  - szi = 0 のスキップ
  - 前回ファイルなし時の変動率空欄
  - liquidationPx = null の処理
- [x] **4-3** blockchain-chart-analyst による分析レポート
  - Phase 2レビュー時に実施（全11項目PASS）
- [x] **4-4** .gitignore 更新
  - `data/*.xlsx`, `logs/*.log` を追加（データファイルはGit管理外）
- [ ] **4-5** 旧システム（Cowork）からの移行 ※REQUIREMENTS.md §8
  - 新システムの正常動作確認後、Coworkスケジュールタスク無効化
  - Chrome許可設定の削除（必要に応じて）

---

## 完了基準

各Phaseの完了には以下を**すべて**満たすこと:

1. ✅ 実装コードが存在し、構文エラーなし
2. ✅ code-reviewer のレビューが **PASS**
3. ✅ 実行テストで期待する出力が得られている
4. ✅ 本ファイルの該当チェックボックスがすべてチェック済み

---

## Agent割り当てサマリー

| Phase | python-engineer | code-reviewer | blockchain-chart-analyst | product-manager |
|-------|:-:|:-:|:-:|:-:|
| Phase 0 | ● 実装 | | | |
| Phase 1 | ● 実装 | ● レビュー | | |
| Phase 2 | ● 実装 | ● レビュー | ● 検証 | |
| Phase 3 | ● 実装 | ● レビュー | | |
| Phase 4 | ○ 修正 | ● 全体レビュー | ● 分析 | ○ 必要時 |

---

## レビュー記録

| 日付 | Phase | レビュワー | 結果 | 備考 |
|------|-------|-----------|------|------|
| 2026-03-09 | Phase 1 | code-reviewer | PASS | 指摘なし |
| 2026-03-09 | Phase 2 | code-reviewer | PASS | 軽微指摘4件（修正任意） |
| 2026-03-09 | Phase 2 | blockchain-chart-analyst | PASS | 全11項目PASS |
| 2026-03-09 | Phase 4 | code-reviewer | FAIL→PASS | Must Fix 3件 + Should Fix 3件 → 再レビューPASS |
