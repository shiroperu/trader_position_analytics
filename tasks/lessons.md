# Lessons Learned

> ユーザーからの修正やミスから学んだパターンを記録する。
> 同じミスを繰り返さないためのルール集。

---

## 記録フォーマット

```
### [日付] カテゴリ: タイトル
**状況**: 何が起きたか
**原因**: なぜ起きたか
**ルール**: 今後の防止策
```

---

## 記録

### [2026-03-09] 仕様書 vs サンプル: 食い違い時の方針確認
**状況**: REQUIREMENTS.md（Net方向=数値, 平均Lev=L/S分離）とサンプルExcel（Net方向=テキスト, 平均Lev=単一値）で仕様が食い違っていた。サンプル準拠で実装したら code-reviewer が Must Fix 判定。
**原因**: サンプルは旧システムの出力であり、新仕様書と必ずしも一致しない。どちらを正とするか事前確認していなかった。
**ルール**: 仕様書とサンプルが矛盾する場合、実装前にユーザーに確認する。デフォルトは仕様書を正とする。

### [2026-03-09] Agentワークツリーとファイル永続化
**状況**: python-engineerがworktreeで生成したExcel/logファイルがメインリポジトリのdata/logs/に残らなかった。
**原因**: Agentのworktree isolationにより、生成ファイルがクリーンアップされた。
**ルール**: Agent完了後、メインリポジトリ側でファイル生成を必ず再検証する。重要な出力は統合テストで改めて生成。

### [2026-03-09] スタンドアロン実行とモジュール実行の両立
**状況**: `python3 scripts/fetch_positions.py` が `ModuleNotFoundError: No module named 'scripts'` で失敗。
**原因**: `from scripts.config import ...` はモジュール実行(`python3 -m scripts.fetch_positions`)でのみ動作。
**ルール**: sys.path.insert(0, parent_dir) を各スクリプト冒頭に入れ、両方の実行方式に対応する。
