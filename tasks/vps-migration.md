# VPS 引越し計画 — trader_position_analytics

> **目的**: macOS launchd 実行をやめ、Ubuntu VPS 上の systemd timer 実行に移行する
> **デプロイ**: GitHub Actions (`workflow_dispatch`) → SSH/rsync → systemd
> **Secrets**: GitHub Secrets を SoT、デプロイ時に VPS 側 `.env` を生成
> **作成日**: 2026-05-08
> **ステータス**: 📋 計画中

---

## 移行後アーキテクチャ

```
[GitHub: trader_position_analytics]
    │  workflow_dispatch（手動）
    ▼
GitHub Actions deploy.yml
    ├─ rsync同期 (--delete --exclude=chromadb_data,logs,data,.venv,.env)
    ├─ Secrets → .env を生成して scp
    ├─ ssh: pip install -r requirements.txt（必要時）
    └─ ssh: sudo systemctl daemon-reload  ← NOPASSWD sudoers 要
                │
                ▼
[Ubuntu VPS]
/opt/trader_position_analytics/   ← ubuntu:ubuntu 所有（dexter と同階層）
    ├─ scripts/
    ├─ requirements.txt
    ├─ .venv/                ← VPS 側で作成、デプロイ対象外
    ├─ .env                  ← Secrets から再生成
    ├─ chromadb_data/        ← VPS 永続、初回 scp 移送
    ├─ data/                 ← VPS 永続
    └─ logs/                 ← VPS 永続

systemd (system-level, dexter と統一):
    /etc/systemd/system/trader-position-analytics.service  (Type=oneshot, User=ubuntu, ExecStart=python scripts/run_all.py --excel)
    /etc/systemd/system/trader-position-analytics.timer    (OnCalendar=*-*-* 00,04,06,08,12,16,20,22:00:00)
```

---

## 確定済み前提

| 項目 | 値 |
|---|---|
| VPS host | `<VPS_HOST>`（実値はローカル管理。public repo のため redact） |
| VPS OS | Ubuntu 24.04.3 LTS (noble) |
| VPS user | `ubuntu`（既存・流用） |
| VPS Python 現状 | 3.12.3（3.14 は未導入） |
| VPS timezone | `Asia/Tokyo`（変換不要） |
| プロジェクトパス | `/opt/trader_position_analytics`（ubuntu:ubuntu 所有、dexter と同階層） |
| 人間用 SSH 鍵 | `~/.ssh/LST_Vola.key`（既存・利用継続） |
| GHA 用 SSH 鍵 | `~/.ssh/gha_trader_deploy`（新規発行） |
| Python 3.14 | VPS にインストール済（事前確認済） |
| デプロイトリガ | `workflow_dispatch` 手動 |
| ChromaDB データ | 初回 scp で移送 |
| 実行スケジュール | 毎日 0/4/6/8/12/16/20/22 時（8回） |
| 必要 secrets | `SLACK_BOT_TOKEN`, `SLACK_CHANNEL` |
| 実行コマンド | `python3.14 scripts/run_all.py --excel` |

---

## Phase 0: 情報収集（ユーザ操作必要）

> **依存**: なし
> **検証**: 全項目のメモが揃っていること

- [x] **0-1** VPS 接続情報確定（host=<VPS_HOST>, user=ubuntu, Ubuntu 24.04.3 LTS）
- [x] **0-2** VPS Python 現状確認（3.12.3、3.14 未導入 → deadsnakes 第一候補）
- [x] **0-3** タイムゾーン確認（Asia/Tokyo ✓）
- [x] **0-4** デプロイ用 SSH 鍵の新規発行・登録
  - `~/.ssh/gha_trader_deploy` 発行済み
  - VPS `authorized_keys` 登録済み、疎通確認済み
  - 秘密鍵は Phase 3 で GitHub Secrets に登録

---

## Phase 1: VPS 基盤セットアップ

> **依存**: Phase 0 完了
> **検証**: VPS 上で `python3.14 -V` と venv 起動が通ること

- [x] **1-1** GHA 用公開鍵を VPS に登録（Phase 0-4 で完了）
- [ ] **1-2** Python 3.14 動作確認（VPS にインストール済）
  - `python3.14 --version` で `Python 3.14.x` を確認
  - `python3.14 -c "import venv; print('venv ok')"` で venv モジュール確認
  - `which python3.14` で絶対パス取得（systemd unit `ExecStart=` で利用）
  - 未インストールだった場合のみ deadsnakes PPA で導入: `sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt update && sudo apt install -y python3.14 python3.14-venv python3.14-dev`
- [ ] **1-3** プロジェクトディレクトリ作成（`/opt/` 配置、dexter と同階層）
  - `sudo mkdir -p /opt/trader_position_analytics/{chromadb_data,data,logs}`
  - `sudo chown -R ubuntu:ubuntu /opt/trader_position_analytics`（GHA から rsync するため ubuntu 所有が必須）
- [ ] **1-4** venv 作成
  - `cd /opt/trader_position_analytics && python3.14 -m venv .venv`
  - `.venv/bin/pip install --upgrade pip`
  - `requirements.txt` を scp してインストールテスト
- [ ] **1-5** ChromaDB 既存データ移送
  - Mac で launchd を **一時停止**: `launchctl unload ~/Library/LaunchAgents/com.dothax.hl-tracker.plist`
  - Mac から: `tar czf - -C ~/Documents/workspace/trader_position_analytics chromadb_data | ssh -i ~/.ssh/LST_Vola.key ubuntu@<VPS_HOST> 'cd /opt/trader_position_analytics && tar xzf -'`
  - VPS 側で `du -sh /opt/trader_position_analytics/chromadb_data` でサイズ照合
  - launchd は **再開しない**（Phase 5 まで停止継続）

---

## Phase 2: systemd unit/timer をリポジトリに同梱（system-level、dexter と統一）

> **依存**: Phase 1
> **検証**: VPS で `sudo systemctl start trader-position-analytics.service` が exit 0

- [ ] **2-1** ディレクトリ作成: `deploy/systemd/`
- [ ] **2-2** `deploy/systemd/trader-position-analytics.service` 作成
  - `Type=oneshot`
  - `User=ubuntu`
  - `Group=ubuntu`
  - `WorkingDirectory=/opt/trader_position_analytics`
  - `EnvironmentFile=/opt/trader_position_analytics/.env`
  - `ExecStart=/opt/trader_position_analytics/.venv/bin/python3.14 scripts/run_all.py --excel`
  - `StandardOutput=append:/opt/trader_position_analytics/logs/systemd_stdout.log`
  - `StandardError=append:/opt/trader_position_analytics/logs/systemd_stderr.log`
  - `[Install] WantedBy=multi-user.target`
- [ ] **2-3** `deploy/systemd/trader-position-analytics.timer` 作成
  - `OnCalendar=*-*-* 00,04,06,08,12,16,20,22:00:00`
  - `Persistent=true`（VPS停止時に取りこぼし対応）
  - `Unit=trader-position-analytics.service`
  - `[Install] WantedBy=timers.target`
- [ ] **2-4** `deploy/install.sh`（手動実行用、要 sudo）作成
  - `sudo cp deploy/systemd/trader-position-analytics.{service,timer} /etc/systemd/system/`
  - `sudo systemctl daemon-reload`
  - `sudo systemctl enable --now trader-position-analytics.timer`
- [ ] **2-5** VPS で手動 install.sh 実行 → `systemctl list-timers trader-position-analytics.timer` で確認

---

## Phase 3: GitHub Actions デプロイワークフロー

> **依存**: Phase 2
> **検証**: workflow_dispatch から実行 → VPS 側でファイル更新を確認

- [ ] **3-1** GitHub Secrets 登録
  - `SSH_PRIVATE_KEY`（Phase 0-4 で発行）
  - `SSH_HOST`
  - `SSH_USER`
  - `SSH_KNOWN_HOSTS`（`ssh-keyscan -H <host>` の出力）
  - `SLACK_BOT_TOKEN`
  - `SLACK_CHANNEL`
- [ ] **3-2** VPS 側に NOPASSWD sudoers 設定
  - `sudo visudo -f /etc/sudoers.d/trader-deploy`
  - 内容: `ubuntu ALL=(root) NOPASSWD: /bin/systemctl daemon-reload, /bin/systemctl restart trader-position-analytics.timer, /bin/systemctl restart trader-position-analytics.service`
  - 理由: GHA deploy で systemd unit 更新時に対話なしで `sudo systemctl daemon-reload` を実行するため
- [ ] **3-3** `.github/workflows/deploy.yml` 作成
  - `on: workflow_dispatch:`
  - rsync で `scripts/`, `requirements.txt`, `deploy/` を `/opt/trader_position_analytics/` に同期（`chromadb_data/`, `data/`, `logs/`, `.venv/`, `.env` は除外）
  - 同期は ubuntu ユーザのまま実行可能（Phase 1-3 で `chown ubuntu:ubuntu` 済みのため sudo 不要）
  - heredoc で `.env` を生成し scp `/opt/trader_position_analytics/.env`（権限 600）
  - ssh で `/opt/trader_position_analytics/.venv/bin/pip install -r requirements.txt` と `sudo systemctl daemon-reload`
- [ ] **3-4** `.github/workflows/deploy.yml` 動作確認
  - GitHub UI から `Run workflow` 実行
  - VPS で `ls -la /opt/trader_position_analytics/scripts/` と `cat /opt/trader_position_analytics/.env`（権限600確認）

---

## Phase 4: 検証

> **依存**: Phase 3
> **検証**: Slack 通知到達、journalctl にエラーなし

- [ ] **4-1** 手動実行テスト: `sudo systemctl start trader-position-analytics.service`
  - `sudo journalctl -u trader-position-analytics.service -e` でログ確認
  - Slack に Excel ファイルが投稿されていること
  - `/opt/trader_position_analytics/data/`, `logs/` に新ファイル生成
  - `/opt/trader_position_analytics/chromadb_data/` の更新確認
- [ ] **4-2** タイマ次回実行時刻の確認
  - `systemctl list-timers trader-position-analytics.timer`
  - 次の 0/4/6/8/12/16/20/22 時の正時に発火することを確認
- [ ] **4-3** 1スケジュール周回確認（最低24時間運用観察）
  - 8回分の発火と Slack 通知の整合
  - ChromaDB retention（30日）の動作確認

---

## Phase 5: 旧環境（Mac launchd）停止

> **依存**: Phase 4 で 24時間以上の安定運用を確認
> **検証**: Mac の launchd で hl-tracker が走らないこと

- [ ] **5-1** launchd ジョブの恒久停止
  - `launchctl unload ~/Library/LaunchAgents/com.dothax.hl-tracker.plist`
  - `launchctl list | grep hl-tracker` が空になることを確認
- [ ] **5-2** plist ファイルの扱い決定
  - 案A: ファイル削除して repo の `com.dothax.hl-tracker.plist` を `legacy/` に退避
  - 案B: 残置（再開可能性あり）
- [ ] **5-3** 旧 Mac 側 `chromadb_data/` の扱い
  - VPS と整合性が確認できた後に `chromadb_data/.bak` へリネーム保管
- [ ] **5-4** README.md / CLAUDE.md の更新
  - 「launchd で実行中」記述 → 「VPS systemd で実行中（GitHub Actions deploy）」に変更

---

## ロールバック手順

問題発生時は Phase 5 完了前なら即座に戻せる:

1. VPS: `sudo systemctl stop trader-position-analytics.timer`
2. Mac: `launchctl load ~/Library/LaunchAgents/com.dothax.hl-tracker.plist` で旧運用復帰

---

## 残リスク・要確認

- **Python 3.14 の VPS インストール状況**: VPS には Python 3.14 がインストール済み（事前確認済）。`/usr/bin/python3.14` 等の絶対パスを Phase 2 の systemd unit `ExecStart=` に埋め込む際に再確認。
- **ChromaDB 初回 scp の停止時間**: tar+scp の所要時間中は launchd 停止 → 8回スロット 1〜2 個分のデータが欠ける。許容するか、Mac 側を完全停止せずスナップショット転送するかの判断。
- **VPS タイムゾーン**: `Asia/Tokyo` でなければ `OnCalendar=` を UTC 換算するか `Timezone=Asia/Tokyo` を service 側に明示。
- **Slack rate limit**: 8回/日なので問題なし。
- **NOPASSWD sudoers の最小権限**: Phase 3-2 で許可するコマンドは `daemon-reload` と `restart trader-position-analytics.{timer,service}` のみ。広い権限を与えないこと。
- **`/opt/` 配下の所有権**: GHA からの rsync は ubuntu ユーザで実行するため、Phase 1-3 の `chown ubuntu:ubuntu /opt/trader_position_analytics` を必ず先に実施。
