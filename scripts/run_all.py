"""メインエントリポイント: Phase 1 (ポジション取得) → Phase 2 (センチメント分析) を順次実行"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# パス解決（launchdやスタンドアロン実行時）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.config import setup_logging
from scripts.fetch_positions import fetch_positions
from scripts.analyze_sentiment import analyze_sentiment


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

    elapsed = time.time() - start
    logger.info(f"=== Complete ({elapsed:.1f}s) ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
