"""メインエントリポイント: Phase 1 (ポジション取得) → Phase 2 (センチメント分析) → Slack通知 を順次実行"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

# パス解決（launchdやスタンドアロン実行時）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.config import setup_logging
from scripts.fetch_positions import fetch_positions
from scripts.analyze_sentiment import analyze_sentiment
from scripts.store_chromadb import store_to_chromadb


def main():
    logger = setup_logging()
    start = time.time()

    logger.info("=== Hyperliquid Position Tracker Started ===")

    # Phase 1: ポジション取得
    positions_file = fetch_positions(logger)

    if positions_file is None:
        logger.error("Phase 1 failed. Skipping Phase 2.")
        elapsed = time.time() - start
        logger.error(f"=== Aborted ({elapsed:.1f}s) ===")
        return 1

    # Phase 2: センチメント分析
    analysis_file = analyze_sentiment(positions_file, logger)

    if analysis_file is None:
        logger.warning("Phase 2 failed.")

    # Phase 3: ChromaDB保存
    if positions_file is not None:
        stored = store_to_chromadb(positions_file, logger)
        if not stored:
            logger.warning("Phase 3 (ChromaDB) failed.")
    else:
        logger.info("Phase 3: Skipped (no position data).")

    # Phase 4: Slack にセンチメント差分を投稿
    _post_sentiment_to_slack(logger)

    elapsed = time.time() - start
    logger.info(f"=== Complete ({elapsed:.1f}s) ===")
    return 0


def _post_sentiment_to_slack(logger) -> None:
    """crypto-research-agent の sentiment コマンドを呼び出して Slack に差分を投稿する"""
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
