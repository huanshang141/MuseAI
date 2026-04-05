# Test Data Initialization Script Design

## Overview

Create a test data initialization script for development environment testing. The script populates PostgreSQL and Elasticsearch with realistic museum artifact data for end-to-end data pipeline validation.

## Requirements

- **Domain**: Museum artifacts (青铜器、书画、陶瓷、玉器等)
- **Documents**: 15 artifacts with Chinese content
- **Chat Data**: 3 chat sessions with 4-6 messages each
- **Idempotent**: Safe to run multiple times, skip existing data
- **Approach**: Minimal script using existing services

## Architecture

### File Location
`scripts/init_test_data.py`

### Components

```
scripts/init_test_data.py
├── SAMPLE_DOCUMENTS: list[dict]  # 15 artifacts
├── SAMPLE_CHAT_SESSIONS: list[dict]  # 3 sessions with messages
├── async init_documents() -> None
├── async init_chat_data() -> None
├── async main() -> None
└── if __name__ == "__main__"
```

### Data Flow

1. Load settings & initialize database/ES connections
2. Create ES index if not exists
3. For each document:
   - Check existence by filename
   - Skip if exists
   - Create Document + IngestionJob records
   - Call IngestionService.process_document()
4. For each chat session:
   - Check existence by title + user_id
   - Skip if exists
   - Create ChatSession + ChatMessages
5. Print summary

## Data Structure

### Documents (15 total)

| Category | Count | Examples |
|----------|-------|----------|
| 青铜器 | 4 | 四羊方尊, 司母戊鼎, 曾侯乙编钟, 长信宫灯 |
| 书画 | 3 | 清明上河图, 千里江山图, 洛神赋图 |
| 陶瓷 | 2 | 唐三彩骆驼载乐俑, 宋代汝窑天青釉洗 |
| 玉器 | 2 | 金缕玉衣, 翠玉白菜 |
| 金银器 | 2 | 何家村窖藏金银器, 舞马衔杯纹银壶 |
| 杂项 | 2 | 马踏飞燕, 素纱襌衣 |

### Chat Sessions (3 total)

1. **青铜器咨询** - Questions about bronze artifacts
2. **书画鉴赏** - Questions about paintings/calligraphy
3. **综合问答** - Mixed museum questions

Each session has 4-6 messages (alternating user/assistant).

## Error Handling

- **Connection failures**: Exit with clear error message
- **Duplicate data**: Skip with log message
- **Ingestion failures**: Log error, continue to next document
- **Missing dependencies**: Fail fast at startup

## Success Criteria

- Script runs without errors with all services available
- 15 documents indexed to ES with multi-level chunks
- 3 chat sessions with message history
- Re-running produces no duplicates
- Retrieval queries return relevant results
