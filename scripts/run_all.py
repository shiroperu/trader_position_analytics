"""メインエントリポイント: Phase 1 (ポジション取得) → Phase 2 (センチメント分析) → Phase 3 (ChromaDB) → Slack通知 を順次実行"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

# パス解決（launchdやスタンドアロン実行時）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from scripts.config import setup_logging, DATA_DIR
from scripts.fetch_positions import fetch_positions
from scripts.analyze_sentiment import analyze_sentiment, flatten_all_data
from scripts.store_chromadb import store_to_chromadb

# プロジェクトルートの .env を読み込み
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def main():
    parser = argparse.ArgumentParser(description="Hyperliquid Position Tracker")
    parser.add_argument("--excel", action="store_true", help="Excel出力を有効化（デフォルト: 無効）")
    args = parser.parse_args()

    logger = setup_logging()
    start = time.time()

    logger.info("=== Hyperliquid Position Tracker Started ===")

    # Phase 1: ポジション取得
    result = fetch_positions(logger, write_excel=args.excel)

    if result is None:
        logger.error("Phase 1 failed.")
        elapsed = time.time() - start
        logger.error(f"=== Aborted ({elapsed:.1f}s) ===")
        return 1

    all_data, timestamp = result
    rows = flatten_all_data(all_data)

    # Phase 2: センチメント分析
    token_results = analyze_sentiment(rows, logger, write_excel=args.excel, timestamp=timestamp)

    if token_results is None:
        logger.warning("Phase 2 failed.")

    # Phase 3: ChromaDB保存
    stored = store_to_chromadb(rows, timestamp, logger)
    if not stored:
        logger.warning("Phase 3 (ChromaDB) failed.")

    # Phase 4: Slack にセンチメント差分を投稿
    _post_sentiment_to_slack(logger)

    # Phase 4b: Excel ファイルを Slack に添付（--excel 有効時のみ）
    if args.excel:
        excel_files = [
            p for p in [
                DATA_DIR / f"hl_positions_{timestamp}.xlsx",
                DATA_DIR / f"hl_analysis_{timestamp}.xlsx",
            ]
            if p.exists()
        ]
        if excel_files:
            _upload_excel_to_slack(excel_files, logger)

    elapsed = time.time() - start
    logger.info(f"=== Complete ({elapsed:.1f}s) ===")
    return 0


def _upload_excel_to_slack(excel_files: list[Path], logger) -> None:
    """生成された Excel ファイルを Slack チャンネルにアップロードする"""
    import os

    token = os.environ.get("SLACK_BOT_TOKEN", "")
    channel = os.environ.get("SLACK_CHANNEL", "")

    if not token or not channel:
        logger.warning("Phase 4b: SLACK_BOT_TOKEN or SLACK_CHANNEL not set. Skipping Excel upload.")
        return

    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
    except ImportError:
        logger.warning("Phase 4b: slack_sdk not installed. Run: pip install slack_sdk")
        return

    client = WebClient(token=token)

    for filepath in excel_files:
        try:
            client.files_upload_v2(
                channel=channel,
                file=str(filepath),
                title=filepath.name,
                initial_comment=f"📊 {filepath.stem}",
            )
            logger.info(f"Phase 4b: Uploaded {filepath.name} to Slack")
        except SlackApiError as e:
            logger.warning(f"Phase 4b: Failed to upload {filepath.name}: {e.response['error']}")
        except Exception as e:
            logger.warning(f"Phase 4b: Failed to upload {filepath.name}: {e}")


def _post_sentiment_to_slack(logger) -> None:
    """crypto-research-agent の sentiment コマンドを呼び出して Slack に差分を投稿する"""
    import os

    # CRYPTO_RESEARCH_AGENT_DIR で上書き可能（Mac/VPS でパスが異なるため）
    agent_dir_env = os.environ.get("CRYPTO_RESEARCH_AGENT_DIR")
    if agent_dir_env:
        agent_dir = Path(agent_dir_env)
    else:
        agent_dir = Path.home() / "Documents" / "workspace" / "boxter" / "crypto-research-agent"

    agent_python = agent_dir / ".venv" / "bin" / "python3"

    if not agent_python.exists():
        logger.warning(f"Phase 4: crypto-research-agent の venv が見つかりません: {agent_python}")
        return

    try:
        # SLACK_CHANNEL を設定している場合は Slack に投稿
        cmd = [str(agent_python), "-m", "src.cli", "sentiment", "--no-fetch"]

        # crypto-research-agent の .env から SLACK_CHANNEL を読み取る
        env_file = agent_dir / ".env"
        slack_channel = ""
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("SLACK_CHANNEL="):
                    slack_channel = line.split("=", 1)[1].strip()
                    break

        if slack_channel:
            cmd.extend(["--slack", slack_channel])

        result = subprocess.run(
            cmd,
            cwd=str(agent_dir),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            logger.info("Phase 4: Sentiment diff posted to Slack")
        else:
            logger.warning(f"Phase 4: sentiment command failed: {result.stderr[:200]}")
    except Exception as e:
        logger.warning(f"Phase 4: Slack notification failed: {e}")


if __name__ == "__main__":
    sys.exit(main())
