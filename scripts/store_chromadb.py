"""Phase 3: センチメント分析結果 & トレーダーマトリクスを ChromaDB に保存"""

from __future__ import annotations

import hashlib
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

# スタンドアロン実行時のパス解決
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chromadb

from scripts.analyze_sentiment import analyze_tokens, build_trader_matrix, flatten_all_data, load_positions
from scripts.config import (
    CHROMADB_COLLECTION_MATRIX,
    CHROMADB_COLLECTION_SENTIMENT,
    CHROMADB_DIR,
    CHROMADB_RETENTION_DAYS,
    DATA_DIR,
    setup_logging,
)


# ============================================================
# ChromaDB クライアント
# ============================================================

def _get_client() -> chromadb.PersistentClient:
    """永続化 ChromaDB クライアントを返す。"""
    CHROMADB_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMADB_DIR))


# ============================================================
# ドキュメント生成（セマンティック検索用の自然言語テキスト）
# ============================================================

def _strip_emoji(sentiment: str) -> str:
    """センチメント文字列から先頭の絵文字・記号を除去する。"""
    return re.sub(r"^[^\w]+", "", sentiment).strip()


def _build_sentiment_document(t: dict) -> str:
    """トークンセンチメントデータから自然言語ドキュメントを生成する。"""
    direction = "long-biased" if t["net_direction"] > 0 else "short-biased"
    pnl_sign = "+" if t["total_pnl"] >= 0 else ""
    return (
        f"{t['coin']}: {_strip_emoji(t['sentiment'])} sentiment. "
        f"{t['long_count']} long vs {t['short_count']} short traders "
        f"({round(t['long_ratio'] * 100)}% long). "
        f"Net position value ${abs(t['net_direction']):,.0f} {direction}. "
        f"Total value ${t['total_value']:,.0f}. "
        f"Average leverage: {t['avg_lev_long']:.1f}x long, {t['avg_lev_short']:.1f}x short. "
        f"Total PnL: ${pnl_sign}{t['total_pnl']:,.0f}."
    )


def _build_matrix_document(trader: str, tier: str, acct_value: float,
                           coin: str, side: str) -> str:
    """トレーダー×トークンペアから自然言語ドキュメントを生成する。"""
    side_label = "LONG" if side == "L" else "SHORT"
    return f"{trader} ({tier}, account ${acct_value:,.0f}) is {side_label} on {coin}."


def _trader_hash(name: str) -> str:
    """トレーダー名からChromaDB IDセーフな短縮ハッシュを生成する。"""
    return hashlib.md5(name.encode("utf-8")).hexdigest()[:8]


def _extract_timestamp(positions_file: str) -> str:
    """ポジションファイル名からタイムスタンプ部分を抽出する。"""
    basename = Path(positions_file).stem  # hl_positions_YYYY-MM-DD_HH-mm
    return basename.replace("hl_positions_", "")


# ============================================================
# メイン保存処理
# ============================================================

def store_to_chromadb(rows: list[dict], timestamp: str, logger) -> bool:
    """ポジションデータをChromaDBに保存する。

    Args:
        rows: フラット化されたポジションデータ（list[dict]）
        timestamp: スナップショットのタイムスタンプ（YYYY-MM-DD_HH-mm）
        logger: ロガー

    Returns: 成功時True、失敗時False
    """
    try:
        logger.info("Phase 3: Storing data to ChromaDB")

        if not rows:
            logger.error("Phase 3: No position data found.")
            return False

        token_results = analyze_tokens(rows)
        snapshot_ts = timestamp
        snapshot_date = snapshot_ts[:10]  # YYYY-MM-DD
        snapshot_hour = int(snapshot_ts[11:13]) if len(snapshot_ts) > 11 else 0

        client = _get_client()

        # ----- Collection 1: token_sentiment -----
        _store_sentiment(client, token_results, snapshot_ts, snapshot_date,
                         snapshot_hour, logger)

        # ----- Collection 2: trader_token_matrix -----
        top30_coins = [t["coin"] for t in token_results[:30]]
        _store_matrix(client, rows, top30_coins, snapshot_ts, snapshot_date, logger)

        logger.info(f"Phase 3: ChromaDB storage complete "
                    f"({len(token_results)} tokens, matrix for top {len(top30_coins)} coins)")

        # ----- Retention: 保持期間を超えた古いスナップショットを削除 -----
        _purge_old_snapshots(client, logger)

        return True

    except Exception as e:
        logger.error(f"Phase 3: ChromaDB storage failed: {e}")
        return False


def _store_sentiment(client: chromadb.PersistentClient, token_results: list[dict],
                     snapshot_ts: str, snapshot_date: str, snapshot_hour: int,
                     logger) -> None:
    """token_sentiment コレクションにデータを upsert する。"""
    collection = client.get_or_create_collection(
        name=CHROMADB_COLLECTION_SENTIMENT,
        metadata={"description": "Token sentiment analysis snapshots"},
    )

    ids = []
    documents = []
    metadatas = []

    for t in token_results:
        doc_id = f"sentiment_{snapshot_ts}_{t['coin']}"
        ids.append(doc_id)
        documents.append(_build_sentiment_document(t))
        metadatas.append({
            "snapshot_ts": snapshot_ts,
            "snapshot_date": snapshot_date,
            "snapshot_hour": snapshot_hour,
            "coin": t["coin"],
            "long_count": t["long_count"],
            "short_count": t["short_count"],
            "total_count": t["total_count"],
            "long_ratio": round(t["long_ratio"], 4),
            "sentiment": _strip_emoji(t["sentiment"]),
            "long_value": round(t["long_value"], 2),
            "short_value": round(t["short_value"], 2),
            "total_value": round(t["total_value"], 2),
            "net_direction": round(t["net_direction"], 2),
            "long_pnl": round(t["long_pnl"], 2),
            "short_pnl": round(t["short_pnl"], 2),
            "total_pnl": round(t["total_pnl"], 2),
            "avg_lev_long": round(t["avg_lev_long"], 2),
            "avg_lev_short": round(t["avg_lev_short"], 2),
        })

    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    logger.info(f"  token_sentiment: {len(ids)} documents upserted")


def _store_matrix(client: chromadb.PersistentClient, rows: list[dict],
                  top_coins: list[str], snapshot_ts: str, snapshot_date: str,
                  logger) -> None:
    """trader_token_matrix コレクションにデータを upsert する。"""
    collection = client.get_or_create_collection(
        name=CHROMADB_COLLECTION_MATRIX,
        metadata={"description": "Trader x Token position matrix snapshots"},
    )

    active_traders, matrix = build_trader_matrix(rows, top_coins)

    # トレーダー情報のルックアップ用マップ
    trader_info_map = {t["trader"]: t for t in active_traders}

    ids = []
    documents = []
    metadatas = []

    for (trader, coin), side in matrix.items():
        info = trader_info_map.get(trader, {})
        tier = info.get("tier", "")
        acct_value = info.get("acct_value", 0.0)

        doc_id = f"matrix_{snapshot_ts}_{_trader_hash(trader)}_{coin}"
        ids.append(doc_id)
        documents.append(_build_matrix_document(trader, tier, acct_value, coin, side))
        metadatas.append({
            "snapshot_ts": snapshot_ts,
            "snapshot_date": snapshot_date,
            "trader": trader,
            "tier": tier,
            "acct_value": round(acct_value, 2),
            "coin": coin,
            "side": side,
        })

    if ids:
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    logger.info(f"  trader_token_matrix: {len(ids)} documents upserted")


# ============================================================
# 保持期間超過データのパージ
# ============================================================

def _collect_distinct_dates(collection, batch_size: int = 500) -> set[str]:
    """コレクション内の snapshot_date (YYYY-MM-DD) を重複排除して列挙する。

    ChromaDB は内部 SQLite の SQLITE_MAX_VARIABLE_NUMBER 制限に引っかかるため、
    limit/offset でページングして取得する。
    """
    dates: set[str] = set()
    offset = 0
    while True:
        results = collection.get(
            include=["metadatas"],
            limit=batch_size,
            offset=offset,
        )
        metas = results["metadatas"]
        if not metas:
            break
        for meta in metas:
            d = meta.get("snapshot_date")
            if d:
                dates.add(d)
        if len(metas) < batch_size:
            break
        offset += batch_size
    return dates


def _purge_old_snapshots(client: chromadb.PersistentClient, logger) -> None:
    """CHROMADB_RETENTION_DAYS を超える古いスナップショットを両コレクションから削除する。

    ChromaDB の $lt 演算子は数値のみ対応なので、
    1) ページングで全 snapshot_date を列挙し、2) 古い日付を $in で一括削除する。
    削除失敗は warning ログのみで処理を続行する（保存成功を優先）。
    """
    cutoff_date = (datetime.now() - timedelta(days=CHROMADB_RETENTION_DAYS)).strftime("%Y-%m-%d")
    collection_names = [CHROMADB_COLLECTION_SENTIMENT, CHROMADB_COLLECTION_MATRIX]

    for name in collection_names:
        try:
            collection = client.get_collection(name=name)
            all_dates = _collect_distinct_dates(collection)
            old_dates = sorted(d for d in all_dates if d < cutoff_date)
            if not old_dates:
                continue

            before = collection.count()
            collection.delete(where={"snapshot_date": {"$in": old_dates}})
            after = collection.count()
            deleted = before - after
            logger.info(f"Retention: {name}: {deleted} docs purged "
                        f"(snapshot_date < {cutoff_date}), {after} remain")
        except Exception as e:
            logger.warning(f"Retention: {name} purge failed: {e}")


# ============================================================
# スタンドアロン実行
# ============================================================

if __name__ == "__main__":
    import glob

    log = setup_logging()

    if len(sys.argv) > 1:
        pos_file = sys.argv[1]
    else:
        pattern = str(DATA_DIR / "hl_positions_*.xlsx")
        files = sorted(glob.glob(pattern))
        if not files:
            log.error("No position files found in data/")
            sys.exit(1)
        pos_file = files[-1]
        log.info(f"Using latest: {Path(pos_file).name}")

    rows = load_positions(pos_file)
    ts = _extract_timestamp(pos_file)
    success = store_to_chromadb(rows, ts, log)
    if success:
        log.info("=== Phase 3 Done ===")
    else:
        log.error("=== Phase 3 Failed ===")
        sys.exit(1)
