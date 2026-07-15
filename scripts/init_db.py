#!/usr/bin/env python3
"""Unified initialization script for MuseAI services.

Handles PostgreSQL schema migrations, Elasticsearch index creation,
service connectivity checks, and optional data seeding.

Usage:
    # Full initialization (migrations + ES index + service checks)
    python scripts/init_db.py

    # With development seed data (requires Elasticsearch + Ollama running)
    python scripts/init_db.py --seed-dev

    # Schema-only (PostgreSQL migrations only, skip everything else)
    python scripts/init_db.py --schema-only

Environment variables:
    DATABASE_URL:          PostgreSQL connection string (required)
    ELASTICSEARCH_URL:     Elasticsearch endpoint (default: http://localhost:9200)
    ELASTICSEARCH_INDEX:   ES index name (default: museai_chunks_v1)
    EMBEDDING_DIMS:        Vector dimensions for ES index (default: 768)
    REDIS_URL:             Redis endpoint (default: redis://localhost:6379)

Examples:
    # Local development (full setup with seed data)
    python scripts/init_db.py --seed-dev

    # Only run PostgreSQL migrations
    python scripts/init_db.py --schema-only
"""

import argparse
import asyncio
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env file from project root so os.environ picks up DATABASE_URL etc.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ---------------------------------------------------------------------------
# Service connectivity checks
# ---------------------------------------------------------------------------

def check_postgres() -> bool:
    """Check PostgreSQL connectivity via a lightweight query."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("  [SKIP] DATABASE_URL not set")
        return False

    try:
        import psycopg2
        # Convert async URL to sync for psycopg2
        sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        conn = psycopg2.connect(sync_url, connect_timeout=5)
        conn.cursor().execute("SELECT 1")
        conn.close()
        print("  [OK]   PostgreSQL is reachable")
        return True
    except ImportError:
        # psycopg2 not available, try via subprocess
        try:
            result = subprocess.run(
                [sys.executable, "-c", "import psycopg2; psycopg2.connect('" +
                 database_url.replace("postgresql+asyncpg://", "postgresql://") +
                 "', connect_timeout=5).close()"],
                capture_output=True, timeout=10,
            )
            if result.returncode == 0:
                print("  [OK]   PostgreSQL is reachable")
                return True
            print("  [FAIL] PostgreSQL connection failed")
            return False
        except Exception:
            print("  [SKIP] Cannot check PostgreSQL (psycopg2 not installed)")
            return False
    except Exception as e:
        print(f"  [FAIL] PostgreSQL: {e}")
        return False


def check_elasticsearch() -> bool:
    """Check Elasticsearch connectivity via HTTP."""
    es_url = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
    try:
        import urllib.request
        req = urllib.request.Request(f"{es_url}/_cluster/health", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                print("  [OK]   Elasticsearch is reachable")
                return True
        print("  [FAIL] Elasticsearch returned unexpected status")
        return False
    except Exception as e:
        print(f"  [FAIL] Elasticsearch: {e}")
        return False


def check_redis() -> bool:
    """Check Redis connectivity."""
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    try:
        import redis
        r = redis.from_url(redis_url, socket_timeout=5)
        r.ping()
        r.close()
        print("  [OK]   Redis is reachable")
        return True
    except ImportError:
        print("  [SKIP] Cannot check Redis (redis package not installed)")
        return False
    except Exception as e:
        print(f"  [FAIL] Redis: {e}")
        return False


def check_all_services() -> dict[str, bool]:
    """Run all service connectivity checks and return results."""
    print("=" * 60)
    print("Checking service connectivity")
    print("=" * 60)
    results = {
        "postgres": check_postgres(),
        "elasticsearch": check_elasticsearch(),
        "redis": check_redis(),
    }
    print()
    return results


# ---------------------------------------------------------------------------
# PostgreSQL migrations
# ---------------------------------------------------------------------------

def _check_database_url() -> str:
    """Validate DATABASE_URL is set and return it."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("Error: DATABASE_URL environment variable is required.")
        print("  Example: export DATABASE_URL=postgresql+asyncpg://museai:password@localhost:5432/museai")
        sys.exit(1)
    return database_url


def run_migrations() -> None:
    """Run Alembic migrations to bring schema to latest version."""
    print("=" * 60)
    print("Running database migrations (alembic upgrade head)")
    print("=" * 60)

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=os.path.join(os.path.dirname(__file__), ".."),
        capture_output=False,
    )

    if result.returncode != 0:
        print("\nError: Alembic migration failed. Check the output above.")
        sys.exit(1)

    print("\nMigrations completed successfully.\n")


def show_migration_status() -> None:
    """Display current migration status."""
    print("-" * 60)
    print("Migration status:")
    print("-" * 60)
    subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=os.path.join(os.path.dirname(__file__), ".."),
    )
    print()


# ---------------------------------------------------------------------------
# Elasticsearch index creation
# ---------------------------------------------------------------------------

async def create_es_index() -> bool:
    """Create Elasticsearch index with proper mapping. Returns True on success."""
    es_url = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
    index_name = os.environ.get("ELASTICSEARCH_INDEX", "museai_chunks_v1")
    dims = int(os.environ.get("EMBEDDING_DIMS", "768"))

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
    from app.infra.elasticsearch.client import ElasticsearchClient

    es_client = ElasticsearchClient(hosts=[es_url], index_name=index_name)
    try:
        healthy = await es_client.health_check()
        if not healthy:
            print("  [FAIL] Elasticsearch is not reachable. Skipping index creation.")
            return False

        result = await es_client.create_index(index_name, dims)
        status = result.get("status", "unknown")
        if status == "already_exists":
            print(f"  [OK]   Index '{index_name}' already exists.")
        elif status == "created":
            print(f"  [OK]   Created index '{index_name}' (dims={dims}, analyzer=ik_max_word).")
        return True
    except Exception as e:
        print(f"  [FAIL] ES index creation failed: {e}")
        return False
    finally:
        await es_client.close()


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

def seed_dev_data() -> None:
    """Seed development test data (prompts, personas, halls, exhibits, test user)."""
    scripts_dir = os.path.dirname(__file__)
    project_root = os.path.join(scripts_dir, "..")

    # Seed dev user
    print("  Seeding development user...")
    result = subprocess.run(
        [sys.executable, os.path.join(scripts_dir, "seed_dev_user.py")],
        cwd=project_root,
    )
    if result.returncode != 0:
        print("  Warning: Failed to seed dev user (non-fatal).")

    # Seed prompts, personas, and halls (pure DB, no external deps)
    print("  Seeding prompts, personas, and halls...")
    result = subprocess.run(
        [sys.executable, os.path.join(scripts_dir, "seed_prompts_and_personas.py")],
        cwd=project_root,
    )
    if result.returncode != 0:
        print("  Warning: Failed to seed prompts/personas/halls (non-fatal).")

    # Seed exhibits (this also creates the ES index internally)
    print("  Seeding exhibit data...")
    result = subprocess.run(
        [sys.executable, os.path.join(scripts_dir, "init_exhibits.py")],
        cwd=project_root,
    )
    if result.returncode != 0:
        print("  Warning: Failed to seed exhibits (non-fatal). Ensure Elasticsearch and Ollama are running.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialize MuseAI: database migrations, ES index, service checks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--init-es",
        action="store_true",
        help="Create Elasticsearch index with proper mapping (idempotent).",
    )
    parser.add_argument(
        "--seed-dev",
        action="store_true",
        help="Seed development test data (dev user + exhibits). Requires ES + Ollama.",
    )
    parser.add_argument(
        "--schema-only",
        action="store_true",
        help="Only run PostgreSQL migrations, skip all other operations.",
    )
    args = parser.parse_args()

    # Ensure sys.path includes backend for imports
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

    _check_database_url()

    # Step 0: Service connectivity checks
    services = check_all_services()

    if not services["postgres"]:
        print("Error: PostgreSQL is not reachable. Cannot proceed.")
        print("  Start it with: docker-compose up -d postgres")
        sys.exit(1)

    # Step 1: Run PostgreSQL migrations
    step = 1
    print(f"{'=' * 60}")
    print(f"Step {step}: PostgreSQL schema migrations")
    print(f"{'=' * 60}")
    run_migrations()
    show_migration_status()

    if args.schema_only:
        print("Schema-only mode. Skipping ES index and seed operations.")
        print("\nInitialization complete (schema only).")
        return

    # Step 2: Elasticsearch index creation
    step += 1
    if args.init_es or args.seed_dev:
        print(f"{'=' * 60}")
        print(f"Step {step}: Elasticsearch index creation")
        print(f"{'=' * 60}")
        if services["elasticsearch"]:
            asyncio.run(create_es_index())
        else:
            print("  [SKIP] Elasticsearch is not reachable.")
        print()

    # Step 3: Seed development data
    if args.seed_dev:
        step += 1
        print(f"{'=' * 60}")
        print(f"Step {step}: Seed development data")
        print(f"{'=' * 60}")
        if not services["elasticsearch"]:
            print("  [WARN] Elasticsearch is not reachable. Seed data requires ES.")
        seed_dev_data()
        print()

    # Summary
    print("=" * 60)
    print("Initialization complete!")
    print("=" * 60)

    # Print service status summary
    print("\nService status:")
    print(f"  PostgreSQL:      {'OK' if services['postgres'] else 'UNAVAILABLE'}")
    print(f"  Elasticsearch:   {'OK' if services['elasticsearch'] else 'UNAVAILABLE'}")
    print(f"  Redis:           {'OK' if services['redis'] else 'UNAVAILABLE'}")

    if not services["elasticsearch"]:
        print("\nNote: Elasticsearch is not available. The app will start in degraded mode.")
        print("  Start it with: docker-compose up -d elasticsearch")
        print("  Then run:      python scripts/init_db.py --init-es")

    print("\nTip: Create the single administrator with:")
    print("  python scripts/bootstrap_admin.py --email admin@museai.local")


if __name__ == "__main__":
    main()
