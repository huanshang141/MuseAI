"""Seed TTS persona prompts into the prompt system.

Run: uv run python backend/scripts/seed_tts_prompts.py
"""
import asyncio

from app.config.settings import get_settings
from app.infra.postgres.database import get_session
from app.infra.postgres.adapters.prompt import PostgresPromptRepository
from app.infra.cache.prompt_cache import PromptCache
from app.application.prompt_service import PromptService

TTS_PROMPTS = [
    {
        "key": "tour_tts_persona_a",
        "name": "Tour TTS - Archaeologist",
        "category": "tts",
        "content": "用沉稳专业的语气讲解，语速适中，带有学术气息，像一位资深考古学家在分享发现",
        "variables": [],
    },
    {
        "key": "tour_tts_persona_b",
        "name": "Tour TTS - Villager",
        "category": "tts",
        "content": "用亲切朴实的语气讲述，语速稍慢，带有乡音的温暖感，像一位老村民在回忆往事",
        "variables": [],
    },
    {
        "key": "tour_tts_persona_c",
        "name": "Tour TTS - Teacher",
        "category": "tts",
        "content": "用生动有趣的语气讲解，语速适中，善于用比喻和提问吸引注意力，像一位热情的历史老师",
        "variables": [],
    },
]


async def main():
    settings = get_settings()
    async with get_session() as session:
        repo = PostgresPromptRepository(session)
        cache = PromptCache()
        cache.set_repository(repo)
        service = PromptService(repo, cache)

        for prompt in TTS_PROMPTS:
            existing = await service.get_prompt(prompt["key"])
            if existing:
                print(f"  [skip] {prompt['key']} already exists")
                continue
            await service.create_prompt(
                key=prompt["key"],
                name=prompt["name"],
                category=prompt["category"],
                content=prompt["content"],
                variables=prompt["variables"],
            )
            print(f"  [created] {prompt['key']}")

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
