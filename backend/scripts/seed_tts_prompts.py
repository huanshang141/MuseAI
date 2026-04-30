"""Seed TTS persona prompts into the prompt system.

Run: uv run python backend/scripts/seed_tts_prompts.py
"""
import asyncio

from app.application.prompt_service import PromptService
from app.application.tts_service import (
    VOICE_DESCRIPTION_KEY,
    extract_voice_description,
    store_voice_description,
)
from app.config.settings import get_settings
from app.infra.cache.prompt_cache import PromptCache
from app.infra.postgres.adapters.prompt import PostgresPromptRepository
from app.infra.postgres.database import get_session, init_database

TTS_PROMPTS = [
    {
        "key": "tour_tts_persona_a",
        "name": "Tour TTS - Archaeologist",
        "category": "tts",
        "content": "用沉稳专业的语气讲解，语速适中，带有学术气息，像一位资深考古学家在分享发现",
        "variables": [
            {"name": VOICE_DESCRIPTION_KEY, "description": "五十多岁的中年男性，声音沉稳浑厚，带有学术气息"}
        ],
    },
    {
        "key": "tour_tts_persona_b",
        "name": "Tour TTS - Villager",
        "category": "tts",
        "content": "用亲切朴实的语气讲述，语速稍慢，带有乡音的温暖感，像一位老村民在回忆往事",
        "variables": [
            {"name": VOICE_DESCRIPTION_KEY, "description": "六十多岁的老年男性，声音沙哑沧桑，带有北方乡音"}
        ],
    },
    {
        "key": "tour_tts_persona_c",
        "name": "Tour TTS - Teacher",
        "category": "tts",
        "content": "用生动有趣的语气讲解，语速适中，善于用比喻和提问吸引注意力，像一位热情的历史老师",
        "variables": [
            {"name": VOICE_DESCRIPTION_KEY, "description": "三十多岁的年轻女性，声音清脆明亮，富有感染力"}
        ],
    },
]


async def main():
    settings = get_settings()
    await init_database(settings.DATABASE_URL)
    async with get_session() as session:
        repo = PostgresPromptRepository(session)
        cache = PromptCache()
        cache.set_repository(repo)
        service = PromptService(repo, cache)

        for prompt in TTS_PROMPTS:
            existing = await service.get_prompt(prompt["key"])
            if existing:
                # Backfill voice_description if missing
                if extract_voice_description(existing.variables) is None:
                    voice_desc = extract_voice_description(prompt["variables"])
                    if voice_desc:
                        new_vars = store_voice_description(existing.variables, voice_desc)
                        await repo.update_with_variables(
                            key=prompt["key"],
                            content=existing.content,
                            variables=new_vars,
                            changed_by="seed_script",
                            change_reason="Backfill voice description",
                        )
                        print(f"  [backfilled] {prompt['key']} voice_description")
                    else:
                        print(f"  [skip] {prompt['key']} already exists")
                else:
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
