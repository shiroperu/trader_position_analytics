# dexter 修正依頼書: ChromaDB パスの環境変数化

> **依頼元**: trader_position_analytics（VPS 移行プロジェクト）
> **依頼先**: dexter（crypto-research-agent）リポ
> **依頼日**: 2026-05-10
> **緊急度**: 中（暫定 symlink 回避中、恒久対応として実施）
> **想定工数**: 30〜60 分

---

## 1. 背景

`trader_position_analytics` を Mac launchd → Ubuntu VPS systemd に移行した結果、ChromaDB の保存場所が変わった:

| 環境 | ChromaDB パス |
|---|---|
| Mac（旧） | `~/Documents/workspace/trader_position_analytics/chromadb_data` |
| VPS（新） | `/opt/trader_position_analytics/chromadb_data` |

dexter の `sentiment` コマンドは ChromaDB を **ハードコードされた Mac 想定パス** で読みに行くため、VPS 上では「データが見つかりません」エラーで失敗する。

## 2. 現状の問題（再現手順）

VPS で以下を実行すると:

```bash
cd /opt/bexter/dexter
SLACK_CH=$(grep '^SLACK_CHANNEL=' .env | cut -d= -f2)
.venv/bin/python3 -m src.cli sentiment --no-fetch --slack "${SLACK_CH}"
```

出力:
```
Token Sentiment 差分を取得中...

エラー: ChromaDB データが見つかりません: /home/ubuntu/Documents/workspace/trader_position_analytics/chromadb_data
```

exit code = 1。**Mac の `~/Documents/workspace/...` を Linux に置換した経路を hardcode** しているのが原因。

## 3. 暫定対応（実施中）

VPS に symlink を張って即時復旧:

```bash
sudo mkdir -p /home/ubuntu/Documents/workspace
sudo ln -s /opt/trader_position_analytics /home/ubuntu/Documents/workspace/trader_position_analytics
```

本依頼書の修正完了後、symlink は **削除する**。

## 4. 要求仕様

### 4.1 機能要件

dexter が ChromaDB を読み込むパスを **環境変数で上書き可能**にする。

| 環境変数名 | 用途 | 優先度 |
|---|---|---|
| `TRADER_CHROMADB_PATH` | trader_position_analytics の ChromaDB ディレクトリへの絶対パス | 1 |

### 4.2 動作仕様

```python
# 疑似コード
chromadb_path = os.environ.get(
    "TRADER_CHROMADB_PATH",
    str(Path.home() / "Documents/workspace/trader_position_analytics/chromadb_data"),
)
```

- `TRADER_CHROMADB_PATH` が **設定されていれば** その値を使う（VPS 想定）
- **未設定**なら現状の Mac default にフォールバック（既存の Mac 環境を壊さない）

### 4.3 dotenv ローディング

dexter が既に `python-dotenv` を使っている場合（多分使っている）、`.env` から自動読込される。使っていない場合は:

```python
from dotenv import load_dotenv
load_dotenv()  # cwd の .env を読込
```

`.env` 読込タイミングは `chromadb_path` 変数を組み立てる **前**。

### 4.4 .env.example の更新

dexter リポの `.env.example` に以下を追記:

```dotenv
# trader_position_analytics の ChromaDB ディレクトリ（絶対パス）
# 未設定時は ~/Documents/workspace/trader_position_analytics/chromadb_data (Mac default) を使用
# VPS 例: /opt/trader_position_analytics/chromadb_data
TRADER_CHROMADB_PATH=
```

## 5. 修正対象ファイル候補

dexter リポ内で grep して特定する:

```bash
cd ~/Documents/workspace/boxter/crypto-research-agent  # Mac の dexter リポ
grep -rn "chromadb_data\|trader_position_analytics" src/ --include="*.py"
```

候補（プロジェクト構造から推測）:
- `src/cli.py` または `src/cli/__init__.py` — `sentiment` サブコマンド本体
- `src/sentiment.py` または `src/services/sentiment.py` — sentiment ロジック
- `src/config.py` または `src/settings.py` — 設定 / パス定数集約

## 6. テスト計画

### 6.1 単体テスト

dexter リポでテストフレームワーク（pytest 等）を使っている場合、以下のテストケースを追加:

| ケース | 入力 | 期待挙動 |
|---|---|---|
| env 未設定 | `TRADER_CHROMADB_PATH` を unset | Mac default パス（`~/Documents/workspace/...`）を使用 |
| env 設定 | `TRADER_CHROMADB_PATH=/tmp/test_chroma` | `/tmp/test_chroma` を使用 |
| env 空文字列 | `TRADER_CHROMADB_PATH=""` | Mac default にフォールバック（実装方針要相談） |

### 6.2 結合テスト（手動）

**Mac 環境**:
```bash
# default 動作（env 未設定）が壊れていないか
cd ~/Documents/workspace/boxter/crypto-research-agent
.venv/bin/python3 -m src.cli sentiment --no-fetch
# → Mac の従来パスから読込、エラーなく動作
```

**VPS 環境**:
```bash
# .env に TRADER_CHROMADB_PATH 追加後
cd /opt/bexter/dexter
.venv/bin/python3 -m src.cli sentiment --no-fetch --slack <チャンネルID>
# → /opt/trader_position_analytics/chromadb_data から読込、Slack に投稿
```

## 7. デプロイ手順

dexter リポの修正・テスト完了後:

1. **dexter リポを commit & push**
2. **VPS で git pull**:
   ```bash
   cd /opt/bexter/dexter && git pull origin <branch>
   ```
3. **VPS の dexter `.env` に環境変数追加**:
   ```bash
   echo "TRADER_CHROMADB_PATH=/opt/trader_position_analytics/chromadb_data" >> /opt/bexter/dexter/.env
   ```
4. **smoke test**:
   ```bash
   cd /opt/bexter/dexter
   SLACK_CH=$(grep '^SLACK_CHANNEL=' .env | cut -d= -f2)
   .venv/bin/python3 -m src.cli sentiment --no-fetch --slack "${SLACK_CH}"
   echo "exit: $?"
   ```
   → exit 0、Slack に分析の示唆メッセージが投稿されること
5. **trader_position_analytics 経由でも動作確認**:
   ```bash
   sudo systemctl start trader-position-analytics.service
   sleep 120
   sudo journalctl -u trader-position-analytics.service -e --no-pager | grep "Phase 4" | tail -5
   ```
   → `Phase 4: Sentiment diff posted to Slack` が表示されること
6. **暫定 symlink を削除**:
   ```bash
   sudo rm /home/ubuntu/Documents/workspace/trader_position_analytics
   sudo rmdir /home/ubuntu/Documents/workspace 2>/dev/null
   sudo rmdir /home/ubuntu/Documents 2>/dev/null
   ```
7. **再度 smoke test** で symlink 削除後も動くこと確認

## 8. 関連: 他のハードコード監査

ChromaDB 以外にも Mac 想定のハードコードが残っている可能性がある。修正のついでに以下も確認:

```bash
# dexter リポで Mac 固有のパスパターンを grep
cd ~/Documents/workspace/boxter/crypto-research-agent
grep -rn "Documents/workspace\|/Users/\|Path.home" src/ --include="*.py"
```

ヒットしたものは、本依頼の対応範囲には含めず **別 issue として登録**。後追いで対応。

## 9. スコープ外

- dexter の他のサブコマンド（`sentiment` 以外）の挙動変更
- ChromaDB 以外の data / logs ディレクトリのパス変更
- dexter の deploy 体系（systemd 等）の見直し
- マルチプロジェクト（trader_position_analytics 以外）対応

## 10. 受け入れ基準（DoD）

- [ ] `TRADER_CHROMADB_PATH` env で ChromaDB パスが上書きできる
- [ ] env 未設定時の Mac default 動作が壊れていない（後方互換性確保）
- [ ] `.env.example` 更新済み
- [ ] Mac 環境で smoke test PASS
- [ ] VPS 環境で smoke test PASS（`.env` 設定済の状態で）
- [ ] trader_position_analytics の systemd service 経由でも `Phase 4: Sentiment diff posted to Slack` が表示される
- [ ] 暫定 symlink を削除した状態で動作継続

## 11. 参考リンク

- trader_position_analytics 側で同等の env-var 化を実施した箇所:
  - `scripts/run_all.py:113-124`（`CRYPTO_RESEARCH_AGENT_DIR` パターン）
  - [.env.example](../.env.example)
- VPS 移行計画: [vps-migration.md](./vps-migration.md)

---

## 12. 質問・確認事項（dexter 側に確認したい点）

- [ ] dexter は `python-dotenv` 利用済みか？ 未利用なら追加する範囲
- [ ] ChromaDB パスは `cli.py` で組み立てているか、`config.py` 等で集約しているか？
- [ ] テストフレームワークは pytest か？ 既存テストの追加先候補
- [ ] 環境変数名 `TRADER_CHROMADB_PATH` でよいか？ 命名規則の合意
