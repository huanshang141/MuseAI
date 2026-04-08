#!/usr/bin/env python3
"""Prepare test data for performance testing.

Seeds Elasticsearch with test documents and creates test users.
"""
import argparse
import asyncio
import uuid

from loguru import logger

from app.config.settings import get_settings
from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.postgres.database import get_session, init_database
from app.infra.postgres.models import User
from app.infra.security.password import hash_password

from .config import TestConfig, get_config


# Sample museum content for testing
SAMPLE_DOCUMENTS = [
    {
        "title": "青铜鼎",
        "content": "这是一件商代晚期的青铜鼎，高约50厘米，重达25公斤。鼎身饰有精美的饕餮纹和云雷纹，"
        "体现了商代青铜铸造的最高水平。该鼎出土于河南安阳殷墟，是研究商代礼制的重要实物。",
        "category": "青铜器",
        "hall": "古代中国馆",
        "floor": 1,
    },
    {
        "title": "青花瓷瓶",
        "content": "明代永乐年间的青花瓷瓶，高35厘米。瓶身绘有缠枝莲纹，青花发色鲜艳，"
        "釉面莹润。此瓶代表了明代景德镇官窑的最高工艺水平。",
        "category": "瓷器",
        "hall": "瓷器馆",
        "floor": 2,
    },
    {
        "title": "清明上河图",
        "content": "北宋画家张择端的代表作，描绘了汴京清明时节的繁荣景象。"
        "画卷长528厘米，宽24.8厘米，画中有各色人物814人，牲畜60多匹，船只28艘。"
        "这幅作品是研究宋代城市生活的珍贵史料。",
        "category": "书画",
        "hall": "书画馆",
        "floor": 3,
    },
    {
        "title": "玉琮",
        "content": "良渚文化时期的玉琮，高约18厘米，外方内圆，象征天圆地方的宇宙观。"
        "玉质温润，表面雕刻有神人兽面纹，是良渚文化玉器的典型代表。",
        "category": "玉器",
        "hall": "玉器馆",
        "floor": 2,
    },
    {
        "title": "司母戊鼎",
        "content": "商代晚期青铜器，是中国目前已发现的最大青铜器，重达832.84公斤。"
        "鼎身四周饰有龙纹和饕餮纹，足部饰有蝉纹，工艺精湛，气势恢宏。"
        "该鼎是研究商代社会制度和铸造技术的国宝级文物。",
        "category": "青铜器",
        "hall": "古代中国馆",
        "floor": 1,
    },
]


async def create_test_documents(
    es_client: ElasticsearchClient,
    num_docs: int,
) -> int:
    """Create test documents in Elasticsearch."""
    logger.info(f"Creating {num_docs} test documents in Elasticsearch...")

    created = 0
    for i in range(num_docs):
        # Cycle through sample documents
        base_doc = SAMPLE_DOCUMENTS[i % len(SAMPLE_DOCUMENTS)]

        # Create document with unique ID
        doc = {
            "chunk_id": str(uuid.uuid4()),
            "document_id": f"test_doc_{i // len(SAMPLE_DOCUMENTS)}",
            "title": f"{base_doc['title']}_{i}",
            "content": base_doc["content"],
            "source": "test_data",
            "category": base_doc["category"],
            "hall": base_doc["hall"],
            "floor": base_doc["floor"],
            "metadata": {
                "name": base_doc["title"],
                "category": base_doc["category"],
            },
            # Generate random embedding vector (768 dims for nomic-embed-text)
            "content_vector": [0.1] * 768,  # Simplified for testing
        }

        try:
            await es_client.index_chunk(doc)
            created += 1
        except Exception as e:
            logger.error(f"Failed to create document {i}: {e}")

    # Refresh index to make documents searchable
    await es_client.client.indices.refresh(index=es_client.index_name)
    logger.info(f"Created {created} test documents")
    return created


async def create_test_users_db(config: TestConfig) -> int:
    """Create test users directly in the database."""
    logger.info(f"Creating {config.num_test_users} test users in database...")

    # Initialize database connection
    settings = get_settings()
    await init_database(settings.DATABASE_URL)

    created = 0
    async with get_session() as session:
        for i in range(config.num_test_users):
            email = f"{config.test_user_email_prefix}_{i}@test.example.com"

            # Check if user exists
            from sqlalchemy import select

            stmt = select(User).where(User.email == email)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                continue

            # Create new user
            user = User(
                id=str(uuid.uuid4()),
                email=email,
                password_hash=hash_password(config.test_user_password),
                role="user",
            )
            session.add(user)
            created += 1

        await session.commit()

    logger.info(f"Created {created} new test users")
    return created


async def prepare_test_data(config: TestConfig) -> dict[str, int]:
    """Prepare all test data."""
    results = {}

    # Initialize Elasticsearch client
    settings = get_settings()
    es_client = ElasticsearchClient(
        hosts=[settings.ELASTICSEARCH_URL],
        index_name=settings.ELASTICSEARCH_INDEX,
    )

    try:
        # Create test documents
        results["documents"] = await create_test_documents(es_client, config.num_test_documents)

        # Create test users
        results["users"] = await create_test_users_db(config)

    finally:
        await es_client.close()

    return results


def main():
    parser = argparse.ArgumentParser(description="Prepare test data for performance testing")
    parser.add_argument(
        "--scenario",
        choices=["smoke", "load", "stress", "spike"],
        default="load",
        help="Test scenario to prepare data for",
    )
    parser.add_argument(
        "--num-users",
        type=int,
        help="Number of test users to create (overrides scenario default)",
    )
    parser.add_argument(
        "--num-docs",
        type=int,
        help="Number of test documents to create (overrides scenario default)",
    )

    args = parser.parse_args()

    config = get_config(args.scenario)
    if args.num_users:
        config.num_test_users = args.num_users
    if args.num_docs:
        config.num_test_documents = args.num_docs

    logger.info(f"Preparing test data for scenario: {args.scenario}")
    results = asyncio.run(prepare_test_data(config))

    print(f"\nTest data preparation complete:")
    print(f"  Documents created: {results.get('documents', 0)}")
    print(f"  Users created: {results.get('users', 0)}")


if __name__ == "__main__":
    main()