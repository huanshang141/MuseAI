#!/usr/bin/env python3
"""清理过期的 LLM 调用追踪记录

用法:
    python scripts/cleanup_llm_traces.py --days 30
    python scripts/cleanup_llm_traces.py --days 90 --dry-run
"""

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.infra.postgres.models import LLMTraceEvent


async def cleanup(days: int, dry_run: bool = False) -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable is not set")
        sys.exit(1)

    engine = create_async_engine(database_url, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    cutoff = datetime.now(UTC) - timedelta(days=days)

    async with session_maker() as session:
        count_stmt = select(func.count()).select_from(LLMTraceEvent).where(
            LLMTraceEvent.created_at < cutoff
        )
        result = await session.execute(count_stmt)
        count = result.scalar() or 0

        if dry_run:
            print(f"[DRY RUN] Would delete {count} records older than {days} days (before {cutoff.isoformat()})")
        else:
            stmt = delete(LLMTraceEvent).where(LLMTraceEvent.created_at < cutoff)
            await session.execute(stmt)
            await session.commit()
            print(f"Deleted {count} records older than {days} days (before {cutoff.isoformat()})")

    await engine.dispose()
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean up expired LLM trace records")
    parser.add_argument("--days", type=int, default=30, help="Delete records older than N days (default: 30)")
    parser.add_argument("--dry-run", action="store_true", help="Show count without deleting")
    args = parser.parse_args()

    if args.days <= 0:
        parser.error("--days must be a positive integer")

    asyncio.run(cleanup(days=args.days, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
