#!/usr/bin/env python3
"""Validate and import real museum data from XLSX or a CSV-pair directory.

Examples:
    python scripts/import_museum_data.py museum_data.xlsx --source-name banpo-2026 --dry-run
    python scripts/import_museum_data.py ./museum_csv --source-name banpo-2026
    python scripts/import_museum_data.py ./museum_csv --source-name banpo-2026 --authoritative

The non-dry-run path requires the configured PostgreSQL, Elasticsearch and
embedding provider. Changed exhibits remain inactive unless RAG indexing
finishes successfully.
"""
# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.application.museum_data_import_service import (
    MuseumDataImportService,
    MuseumDataIndexingError,
    MuseumDataValidationError,
    load_museum_dataset,
    validate_source_name,
)
from app.application.unified_indexing_service import UnifiedIndexingService
from app.config.settings import get_settings
from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.langchain import create_embeddings


async def _run_import(
    input_path: Path,
    source_name: str,
    dry_run: bool,
    authoritative: bool = False,
) -> dict:
    dataset = load_museum_dataset(input_path)
    source_name = validate_source_name(source_name)
    if dry_run:
        summary = await MuseumDataImportService().import_dataset(
            dataset,
            source_name=source_name,
            dry_run=True,
            authoritative=authoritative,
        )
        return summary.to_dict()

    settings = get_settings()
    if settings.DATABASE_URL == "sqlite+aiosqlite:///:memory:":
        raise RuntimeError(
            "Refusing to import into the default in-memory database; configure DATABASE_URL"
        )
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    es_client = ElasticsearchClient(
        hosts=[settings.ELASTICSEARCH_URL],
        index_name=settings.ELASTICSEARCH_INDEX,
    )
    try:
        if not await es_client.health_check():
            raise RuntimeError("Elasticsearch health check failed; no database rows were changed")
        await es_client.create_index(settings.ELASTICSEARCH_INDEX, settings.EMBEDDING_DIMS)
        indexing_service = UnifiedIndexingService(
            es_client=es_client,
            embeddings=create_embeddings(settings),
        )
        session_maker = async_sessionmaker(engine, expire_on_commit=False)
        async with session_maker() as session:
            service = MuseumDataImportService(session, indexing_service)
            summary = await service.import_dataset(
                dataset,
                source_name=source_name,
                authoritative=authoritative,
            )
            return summary.to_dict()
    finally:
        await es_client.close()
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import validated museum halls/exhibits and rebuild their RAG index"
    )
    parser.add_argument(
        "input",
        type=Path,
        help="museum_data.xlsx or a directory containing halls.csv and exhibits.csv",
    )
    parser.add_argument(
        "--source-name",
        required=True,
        help="Stable source identifier; keep the same value for future updates",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate every row without connecting to PostgreSQL, Elasticsearch or embeddings",
    )
    parser.add_argument(
        "--authoritative",
        action="store_true",
        help=(
            "Treat this source as an authoritative snapshot: safely deactivate omitted "
            "same-source and unowned legacy rows after deleting their old RAG sources"
        ),
    )
    args = parser.parse_args()

    try:
        result = asyncio.run(
            _run_import(
                args.input,
                args.source_name,
                args.dry_run,
                args.authoritative,
            )
        )
    except MuseumDataValidationError as exc:
        print(json.dumps({"status": "validation_failed", "issues": exc.issues}, ensure_ascii=False, indent=2))
        raise SystemExit(2) from None
    except MuseumDataIndexingError as exc:
        print(
            json.dumps(
                {
                    "status": "indexing_incomplete",
                    "failures": exc.failures,
                    "summary": exc.summary.to_dict(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        raise SystemExit(3) from None
    except Exception as exc:
        print(
            json.dumps(
                {"status": "failed", "error": f"{type(exc).__name__}: {exc}"},
                ensure_ascii=False,
                indent=2,
            )
        )
        raise SystemExit(1) from None

    print(json.dumps({"status": "validated" if args.dry_run else "completed", **result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
