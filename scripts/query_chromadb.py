"""ChromaDB クエリユーティリティ: セマンティック検索・時系列・トレンド分析"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# スタンドアロン実行時のパス解決
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chromadb

from scripts.config import (
    CHROMADB_COLLECTION_MATRIX,
    CHROMADB_COLLECTION_SENTIMENT,
    CHROMADB_DIR,
)


# ============================================================
# クライアント & コレクション取得
# ============================================================

def get_client() -> chromadb.PersistentClient:
    """永続化 ChromaDB クライアントを返す。"""
    if not CHROMADB_DIR.exists():
        raise FileNotFoundError(f"ChromaDB data not found: {CHROMADB_DIR}")
    return chromadb.PersistentClient(path=str(CHROMADB_DIR))


def _get_collection(client: chromadb.PersistentClient, name: str):
    """コレクションを取得する。存在しない場合はエラー。"""
    try:
        return client.get_collection(name=name)
    except Exception:
        raise ValueError(f"Collection '{name}' not found. Run Phase 3 first.")


# ============================================================
# クエリ関数
# ============================================================

def semantic_search(query: str, collection_name: str = CHROMADB_COLLECTION_SENTIMENT,
                    n_results: int = 10, where: dict | None = None) -> list[dict]:
    """セマンティック検索を実行する。

    Args:
        query: 自然言語クエリ
        collection_name: 検索対象コレクション名
        n_results: 返却件数
        where: メタデータフィルター条件

    Returns: 検索結果のリスト
    """
    client = get_client()
    collection = _get_collection(client, collection_name)

    kwargs = {
        "query_texts": [query],
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)

    output = []
    for i in range(len(results["ids"][0])):
        output.append({
            "id": results["ids"][0][i],
            "document": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        })
    return output


def get_sentiment_history(coin: str, limit: int = 30) -> list[dict]:
    """特定トークンのセンチメント履歴を時系列順で取得する。

    Args:
        coin: トークン名（例: "BTC"）
        limit: 取得件数上限

    Returns: メタデータのリスト（snapshot_ts昇順）
    """
    client = get_client()
    collection = _get_collection(client, CHROMADB_COLLECTION_SENTIMENT)

    results = collection.get(
        where={"coin": coin},
        include=["metadatas", "documents"],
    )

    entries = []
    for i in range(len(results["ids"])):
        entry = {**results["metadatas"][i]}
        entry["document"] = results["documents"][i]
        entries.append(entry)

    entries.sort(key=lambda x: x.get("snapshot_ts", ""))
    return entries[-limit:]


def get_trader_positions(trader: str, snapshot_ts: str | None = None) -> list[dict]:
    """特定トレーダーのポジション情報を取得する。

    Args:
        trader: トレーダー名
        snapshot_ts: 特定スナップショット（省略時は最新）

    Returns: ポジション情報のリスト
    """
    client = get_client()
    collection = _get_collection(client, CHROMADB_COLLECTION_MATRIX)

    where_filter: dict = {"trader": trader}
    if snapshot_ts:
        where_filter = {"$and": [{"trader": trader}, {"snapshot_ts": snapshot_ts}]}

    results = collection.get(
        where=where_filter,
        include=["metadatas", "documents"],
    )

    entries = []
    for i in range(len(results["ids"])):
        entry = {**results["metadatas"][i]}
        entry["document"] = results["documents"][i]
        entries.append(entry)

    entries.sort(key=lambda x: (x.get("snapshot_ts", ""), x.get("coin", "")))
    return entries


def get_available_snapshots() -> list[str]:
    """保存済みスナップショットのタイムスタンプ一覧を取得する。"""
    client = get_client()
    collection = _get_collection(client, CHROMADB_COLLECTION_SENTIMENT)

    results = collection.get(include=["metadatas"])

    timestamps = set()
    for meta in results["metadatas"]:
        ts = meta.get("snapshot_ts")
        if ts:
            timestamps.add(ts)

    return sorted(timestamps)


def get_trend(coin: str, last_n: int = 20) -> list[dict]:
    """特定トークンのトレンドデータを取得する。

    Args:
        coin: トークン名
        last_n: 直近N件のスナップショット

    Returns: トレンドデータ（snapshot_ts, long_ratio, sentiment, total_value, total_pnl）
    """
    history = get_sentiment_history(coin, limit=last_n)
    return [
        {
            "snapshot_ts": h["snapshot_ts"],
            "long_ratio": h.get("long_ratio"),
            "sentiment": h.get("sentiment"),
            "total_value": h.get("total_value"),
            "total_pnl": h.get("total_pnl"),
            "long_count": h.get("long_count"),
            "short_count": h.get("short_count"),
        }
        for h in history
    ]


def get_snapshot_summary(snapshot_ts: str) -> dict:
    """特定スナップショットのサマリーを取得する。

    Args:
        snapshot_ts: タイムスタンプ（例: "2026-03-08_12-00"）

    Returns: サマリー情報
    """
    client = get_client()
    sentiment_col = _get_collection(client, CHROMADB_COLLECTION_SENTIMENT)
    matrix_col = _get_collection(client, CHROMADB_COLLECTION_MATRIX)

    sentiment_results = sentiment_col.get(
        where={"snapshot_ts": snapshot_ts},
        include=["metadatas"],
    )

    matrix_results = matrix_col.get(
        where={"snapshot_ts": snapshot_ts},
        include=["metadatas"],
    )

    tokens = sentiment_results["metadatas"]
    positions = matrix_results["metadatas"]

    sentiment_counts = {}
    for t in tokens:
        s = t.get("sentiment", "Unknown")
        sentiment_counts[s] = sentiment_counts.get(s, 0) + 1

    traders = set()
    for p in positions:
        traders.add(p.get("trader", ""))

    return {
        "snapshot_ts": snapshot_ts,
        "total_tokens": len(tokens),
        "total_positions": len(positions),
        "active_traders": len(traders),
        "sentiment_distribution": sentiment_counts,
    }


# ============================================================
# CLI
# ============================================================

def _format_output(data, compact: bool = False) -> str:
    """データをJSON文字列にフォーマットする。"""
    indent = None if compact else 2
    return json.dumps(data, indent=indent, ensure_ascii=False, default=str)


def main():
    parser = argparse.ArgumentParser(
        description="ChromaDB Query Utility for Hyperliquid Position Tracker"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # search
    search_parser = subparsers.add_parser("search", help="Semantic search")
    search_parser.add_argument("query", help="Search query in natural language")
    search_parser.add_argument("-n", "--num", type=int, default=10, help="Number of results")
    search_parser.add_argument("-c", "--collection", default=CHROMADB_COLLECTION_SENTIMENT,
                               choices=[CHROMADB_COLLECTION_SENTIMENT, CHROMADB_COLLECTION_MATRIX],
                               help="Collection to search")
    search_parser.add_argument("--date", help="Filter by snapshot date (YYYY-MM-DD)")
    search_parser.add_argument("--coin", help="Filter by coin symbol")

    # history
    history_parser = subparsers.add_parser("history", help="Token sentiment history")
    history_parser.add_argument("coin", help="Token symbol (e.g., BTC)")
    history_parser.add_argument("-l", "--limit", type=int, default=30, help="Max records")

    # trend
    trend_parser = subparsers.add_parser("trend", help="Token trend data")
    trend_parser.add_argument("coin", help="Token symbol (e.g., ETH)")
    trend_parser.add_argument("--last", type=int, default=20, help="Last N snapshots")

    # snapshots
    subparsers.add_parser("snapshots", help="List available snapshots")

    # summary
    summary_parser = subparsers.add_parser("summary", help="Snapshot summary")
    summary_parser.add_argument("snapshot_ts", help="Snapshot timestamp (YYYY-MM-DD_HH-mm)")

    # trader
    trader_parser = subparsers.add_parser("trader", help="Trader positions")
    trader_parser.add_argument("name", help="Trader name")
    trader_parser.add_argument("--snapshot", help="Snapshot timestamp (optional)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "search":
            where = {}
            if args.date:
                where["snapshot_date"] = args.date
            if args.coin:
                where["coin"] = args.coin
            results = semantic_search(args.query, args.collection, args.num,
                                      where if where else None)
            print(_format_output(results))

        elif args.command == "history":
            results = get_sentiment_history(args.coin, args.limit)
            print(_format_output(results))

        elif args.command == "trend":
            results = get_trend(args.coin, args.last)
            print(_format_output(results))

        elif args.command == "snapshots":
            results = get_available_snapshots()
            print(_format_output(results))

        elif args.command == "summary":
            results = get_snapshot_summary(args.snapshot_ts)
            print(_format_output(results))

        elif args.command == "trader":
            results = get_trader_positions(args.name, args.snapshot)
            print(_format_output(results))

    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
