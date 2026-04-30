"""Seed TTS persona prompts into the prompt system.

Run: uv run python backend/scripts/seed_tts_prompts.py
"""
import asyncio

from app.application.prompt_service import PromptService
from app.application.tts_service import (
    VOICE_DESCRIPTION_KEY,
    VOICE_KEY,
    extract_voice,
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
        "content": (
            "【角色】五十多岁的资深考古学家，声音沉稳浑厚，带有学术气息。"
            "常年在田野考古，说话沉稳有力，偶尔带出专业术语但从不卖弄。\n"
            "【场景】在博物馆展厅中，面对感兴趣的参观者，分享自己多年的考古发现与文物背后的故事。\n"
            "【指导】\n"
            "- 语速：适中偏慢，像在课堂上娓娓道来，重要细节处会刻意放慢\n"
            "- 气息：平稳深沉，偶尔在惊叹处加入轻微的感叹\n"
            "- 咬字：清晰准确，对文物名称和历史年代会略微加重\n"
            "- 情绪：对考古发现怀有真挚的热爱与敬畏，讲到精彩处声音会微微上扬"
        ),
        "variables": [
            {"name": VOICE_KEY, "description": "白桦"},
            {"name": VOICE_DESCRIPTION_KEY, "description": "五十多岁的中年男性，声音沉稳浑厚，带有学术气息"},
        ],
    },
    {
        "key": "tour_tts_persona_b",
        "name": "Tour TTS - Villager",
        "category": "tts",
        "content": (
            "【角色】六十多岁的老村民，声音沙哑沧桑，带有北方乡音。"
            "一辈子生活在这片土地上，对家乡的历史和传说了如指掌，说话朴实接地气。\n"
            "【场景】在村口老槐树下，或者博物馆的民俗展区，向来访的客人讲述过去的故事和家乡的记忆。\n"
            "【指导】\n"
            "- 语速：稍慢，像老人家拉家常，有停顿和回忆的间隙\n"
            "- 气息：略带喘息感，偶尔叹气，带着岁月的沉淀\n"
            "- 咬字：带轻微北方口音，平翘舌略混，儿化音自然\n"
            "- 情绪：怀旧温暖，讲到苦难处声音低沉，讲到开心处爽朗大笑"
        ),
        "variables": [
            {"name": VOICE_KEY, "description": "苏打"},
            {"name": VOICE_DESCRIPTION_KEY, "description": "六十多岁的老年男性，声音沙哑沧桑，带有北方乡音"},
        ],
    },
    {
        "key": "tour_tts_persona_c",
        "name": "Tour TTS - Teacher",
        "category": "tts",
        "content": (
            "【角色】三十多岁的年轻历史老师，声音清脆明亮，富有感染力。"
            "讲课生动有趣，善于用比喻和提问吸引学生注意力，是学生最喜欢的老师。\n"
            "【场景】在博物馆中带领学生参观，或者面对参观者，用生动活泼的方式讲解历史知识。\n"
            "【指导】\n"
            "- 语速：适中偏快，节奏明快，像在课堂上激情授课\n"
            "- 气息：充沛有力，偶尔在提问时故意停顿制造悬念\n"
            "- 咬字：清晰利落，关键词汇会加重语气，像划重点\n"
            "- 情绪：热情洋溢，充满好奇心，讲到有趣处会忍不住笑出来"
        ),
        "variables": [
            {"name": VOICE_KEY, "description": "茉莉"},
            {"name": VOICE_DESCRIPTION_KEY, "description": "三十多岁的年轻女性，声音清脆明亮，富有感染力"},
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
                new_vars = list(existing.variables)
                changed = False

                # Backfill voice_description if missing
                if extract_voice_description(existing.variables) is None:
                    voice_desc = extract_voice_description(prompt["variables"])
                    if voice_desc:
                        new_vars = store_voice_description(new_vars, voice_desc)
                        changed = True
                        print(f"  [backfill] {prompt['key']} voice_description")

                # Backfill voice if missing
                if extract_voice(existing.variables) is None:
                    voice = extract_voice(prompt["variables"])
                    if voice:
                        new_vars.append({"name": VOICE_KEY, "description": voice})
                        changed = True
                        print(f"  [backfill] {prompt['key']} voice={voice}")

                if changed:
                    await repo.update_with_variables(
                        key=prompt["key"],
                        content=existing.content,
                        variables=new_vars,
                        changed_by="seed_script",
                        change_reason="Backfill missing TTS metadata",
                    )
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
