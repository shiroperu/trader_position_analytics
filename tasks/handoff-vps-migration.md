# VPS 引越し — 別 PC 再開ハンドオフ

> **作成**: 2026-05-08
> **全体計画**: [vps-migration.md](./vps-migration.md)
> **現在地**: Phase 1-2（Python 3.14 インストール）の入口

---

## 別 PC で再開する前に揃えるもの

| # | 必要なもの | 取得方法 |
|---|---|---|
| 1 | このリポジトリ | `git clone https://github.com/shiroperu/trader_position_analytics.git` |
| 2 | GHA 用 SSH 秘密鍵 `~/.ssh/gha_trader_deploy` | 元 PC からセキュアに転送（USB / 1Password 等） |
| 3 | 人間用 SSH 鍵 `~/.ssh/LST_Vola.key` | 元 PC から転送（既存運用で使用中のはず） |
| 4 | VPS_HOST（IP or ドメイン） | 自身のメモから補完。public repo のため未記載 |

転送した秘密鍵は `chmod 600 ~/.ssh/gha_trader_deploy ~/.ssh/LST_Vola.key` を必ず実行。

## 確認事項（揃ったら最初に実行）

```bash
ls -la ~/.ssh/gha_trader_deploy ~/.ssh/LST_Vola.key
ssh -i ~/.ssh/gha_trader_deploy -o IdentitiesOnly=yes ubuntu@<VPS_HOST> 'whoami && lsb_release -ds'
```

→ `ubuntu` / `Ubuntu 24.04.3 LTS` が返れば再開準備OK。

---

## ✅ ここまで完了済み（Phase 0 + Phase 1-1）

- VPS Ubuntu 24.04.3 LTS 確認
- Python 3.12.3 確認（3.14 はまだ無し）
- Timezone Asia/Tokyo 確認
- GHA 用 SSH 鍵 `~/.ssh/gha_trader_deploy` 発行
- 公開鍵を VPS の `~/.ssh/authorized_keys` に登録
- 新鍵での疎通確認（パスワード無しログイン成功）

公開鍵（参考）:
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIF1rYa4h8wptYQfyD3fM7B7rU+dEkeIjyfXjRaL/YQNp gha-deploy-trader-position-analytics
```

---

## ▶️ 次の一手: Phase 1-2 — Python 3.14 インストール

`<VPS_HOST>` を実値に置き換えて、上から順に実行。

### Step ① deadsnakes PPA 追加 + apt update

```bash
ssh -t -i ~/.ssh/gha_trader_deploy -o IdentitiesOnly=yes ubuntu@<VPS_HOST> 'sudo add-apt-repository -y ppa:deadsnakes/ppa && sudo apt update'
```

→ `apt update` 末尾を確認。エラーが無ければ次へ。

### Step ② python3.14 が apt に存在するか確認

```bash
ssh -i ~/.ssh/gha_trader_deploy -o IdentitiesOnly=yes ubuntu@<VPS_HOST> 'apt-cache madison python3.14'
```

→ 1行以上出れば deadsnakes に存在。空なら **pyenv フォールバック**（下記）。

### Step ③ インストール（②で存在を確認した場合のみ）

```bash
ssh -t -i ~/.ssh/gha_trader_deploy -o IdentitiesOnly=yes ubuntu@<VPS_HOST> 'sudo apt install -y python3.14 python3.14-venv python3.14-dev'
```

### 動作確認

```bash
ssh -i ~/.ssh/gha_trader_deploy -o IdentitiesOnly=yes ubuntu@<VPS_HOST> 'python3.14 --version && python3.14 -c "import venv; print(\"venv ok\")"'
```

→ `Python 3.14.x` と `venv ok` が出たら **Phase 1-2 完了**。`tasks/vps-migration.md` の 1-2 をチェック済みに更新する。

---

## pyenv フォールバック（Step ② で deadsnakes に無かった場合）

```bash
ssh -t -i ~/.ssh/gha_trader_deploy -o IdentitiesOnly=yes ubuntu@<VPS_HOST> 'sudo apt install -y build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev curl libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev'
ssh -i ~/.ssh/gha_trader_deploy -o IdentitiesOnly=yes ubuntu@<VPS_HOST> 'curl https://pyenv.run | bash'
ssh -i ~/.ssh/gha_trader_deploy -o IdentitiesOnly=yes ubuntu@<VPS_HOST> 'echo "export PATH=\"\$HOME/.pyenv/bin:\$PATH\"" >> ~/.bashrc && echo "eval \"\$(pyenv init -)\"" >> ~/.bashrc'
ssh -i ~/.ssh/gha_trader_deploy -o IdentitiesOnly=yes ubuntu@<VPS_HOST> 'bash -lc "pyenv install -l | grep \"^  3.14\" | tail -3"'
# 出力で最新の 3.14.x を選んで（例: 3.14.0）:
ssh -t -i ~/.ssh/gha_trader_deploy -o IdentitiesOnly=yes ubuntu@<VPS_HOST> 'bash -lc "pyenv install 3.14.0"'
```

pyenv 経由の場合、`python3.14` の絶対パスは `~/.pyenv/versions/3.14.x/bin/python3.14`。systemd unit の `ExecStart=` で絶対パス指定が必要。

---

## Phase 1-3 以降の概要（Phase 1-2 完了後に再読み込み）

`tasks/vps-migration.md` の Phase 1-3 以降を参照:
- 1-3: プロジェクトディレクトリ作成
- 1-4: venv 作成 + requirements.txt インストール
- 1-5: ChromaDB 既存データ scp 移送（Mac の launchd 一時停止が必要）
- Phase 2: systemd unit/timer 作成
- Phase 3: GitHub Actions deploy.yml
- Phase 4: 検証
- Phase 5: 旧環境停止

---

## トラブルシュート

| 症状 | 対処 |
|---|---|
| 新鍵で password を聞かれる | VPS の `~/.ssh/authorized_keys` に gha_trader_deploy.pub が記載されているか確認 |
| sudo がパスワードを要求 | `ssh -t` で pseudo-TTY 付与し対話入力 |
| ssh コマンドが multi-line で壊れる | 1コマンド1行ずつ実行する |
| deadsnakes に 3.14 が無い | pyenv フォールバックへ切替 |
