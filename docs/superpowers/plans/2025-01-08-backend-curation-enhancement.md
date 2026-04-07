# Backend Curation Enhancement Plan

## Goal

增强后端以支持完整的 Digital Curation Agent 功能：
1. 新增公开展品 API (Public Exhibits API)
2. 将展品信息索引到 RAG 系统
3. 支持按展品检索和过滤

## Current State Analysis

### 现有架构

```
backend/
├── app/
│   ├── api/
│   │   ├── admin.py          # Admin 展品管理 (需认证)
│   │   ├── curator.py        # Curator Agent API
│   │   ├── documents.py      # 文档管理 + 摄取
│   │   └── ...
│   ├── application/
│   │   ├── exhibit_service.py    # Exhibit CRUD
│   │   ├── ingestion_service.py  # 文档摄取到 ES
│   │   └── chunking.py           # 文本分块
│   ├── infra/
│   │   ├── elasticsearch/
│   │   │   └── client.py     # ES 客户端 (仅支持文档 chunks)
│   │   └── postgres/
│   │       └── models.py     # Exhibit Model (含 document_id 外键)
│   └── main.py               # FastAPI 应用 + 路由注册
```

### 当前限制

1. **无公开展品 API**: `/api/v1/admin/exhibits` 需要 admin 认证
2. **RAG 仅索引文档**: `ingestion_service.py` 只处理 Document chunks
3. **无展品元数据检索**: Exhibit 的位置、展厅等信息不在 ES 中
4. **Admin API 不完整**: 缺少 `PUT /admin/exhibits/{id}` 更新接口

---

## Architecture Design

### 改造后架构

```
backend/
├── app/
│   ├── api/
│   │   ├── exhibits.py       # 新增: 公开展品 API
│   │   ├── admin.py          # 修改: 添加 update exhibit
│   │   └── ...
│   ├── application/
│   │   ├── exhibit_indexing_service.py  # 新增: 展品索引服务
│   │   ├── exhibit_search_service.py    # 新增: 展品搜索服务
│   │   └── ...
│   ├── infra/
│   │   ├── elasticsearch/
│   │   │   └── client.py     # 扩展: 支持展品索引
│   │   └── langchain/
│   │       └── retrievers.py # 扩展: 展品感知检索器
│   └── main.py               # 修改: 注册新路由
```

### 数据流向

```
┌─────────────────────────────────────────────────────────────────────┐
│                        展品创建/更新流程                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Admin 创建/更新 Exhibit                                            │
│        │                                                            │
│        ▼                                                            │
│   ┌─────────────────┐                                               │
│   │  PostgreSQL     │ ◄── 主存储 (元数据)                            │
│   │  (exhibits)     │                                               │
│   └────────┬────────┘                                               │
│            │                                                        │
│            ▼                                                        │
│   ┌─────────────────┐     ┌─────────────────┐                       │
│   │ ExhibitIndexing │────►│ Elasticsearch   │ ◄── 可检索副本         │
│   │ Service         │     │ (exhibit docs)  │                       │
│   └─────────────────┘     └─────────────────┘                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                        知识检索流程                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   用户查询: "青铜鼎的铸造工艺"                                        │
│        │                                                            │
│        ▼                                                            │
│   ┌─────────────────┐                                               │
│   │ Curator Agent   │                                               │
│   │                 │                                               │
│   │ 1. 先搜展品元数据  ──► PostgreSQL (按名称/类别匹配)               │
│   │                 │                                               │
│   │ 2. 再搜知识内容   ──► Elasticsearch                              │
│   │    - 文档 chunks                                                 │
│   │    - 展品描述 (如果有)                                            │
│   │                 │                                               │
│   │ 3. 整合生成回答                                                  │
│   └─────────────────┘                                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Task 1: 新增公开展品 API

**Files:**
- Create: `backend/app/api/exhibits.py`
- Modify: `backend/app/main.py`

### Step 1: 创建 exhibits.py 公开 API

Create `backend/app/api/exhibits.py`:

```python
"""公开展品 API - 无需认证即可访问展品基本信息"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.api.deps import SessionDep
from app.application.exhibit_service import ExhibitService
from app.infra.postgres.repositories import PostgresExhibitRepository

router = APIRouter(prefix="/exhibits", tags=["exhibits"])


class ExhibitListItem(BaseModel):
    """展品列表项 (精简信息)"""
    id: str
    name: str
    category: Optional[str]
    hall: Optional[str]
    floor: Optional[int]
    importance: int
    estimated_visit_time: Optional[int]
    is_active: bool


class ExhibitDetail(BaseModel):
    """展品详情"""
    id: str
    name: str
    description: Optional[str]
    category: Optional[str]
    hall: Optional[str]
    floor: Optional[int]
    era: Optional[str]
    importance: int
    estimated_visit_time: Optional[int]
    location_x: Optional[float]
    location_y: Optional[float]
    is_active: bool


class ExhibitListResponse(BaseModel):
    exhibits: list[ExhibitListItem]
    total: int
    skip: int
    limit: int


class CategoryStats(BaseModel):
    category: str
    count: int


class HallStats(BaseModel):
    hall: str
    count: int


class ExhibitStatsResponse(BaseModel):
    total_exhibits: int
    categories: list[CategoryStats]
    halls: list[HallStats]


def get_exhibit_service(session: SessionDep) -> ExhibitService:
    """Get exhibit service instance."""
    repository = PostgresExhibitRepository(session)
    return ExhibitService(repository)


@router.get("", response_model=ExhibitListResponse)
async def list_exhibits(
    session: SessionDep,
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回记录数"),
    category: Optional[str] = Query(None, description="按类别筛选"),
    hall: Optional[str] = Query(None, description="按展厅筛选"),
    floor: Optional[int] = Query(None, ge=1, le=3, description="按楼层筛选"),
    search: Optional[str] = Query(None, description="按名称搜索"),
) -> ExhibitListResponse:
    """获取展品列表 (公开接口，无需认证)
    
    支持分页、筛选和搜索功能。
    """
    service = get_exhibit_service(session)
    
    # 如果有搜索关键词，使用搜索功能
    if search:
        exhibits = await service.search_exhibits(
            query=search,
            category=category,
            hall=hall,
            floor=floor,
            skip=skip,
            limit=limit,
        )
    else:
        # 否则使用筛选功能
        exhibits = await service.list_exhibits(
            skip=skip,
            limit=limit,
            category=category,
            hall=hall,
            floor=floor,
        )
    
    # 获取总数
    all_exhibits = await service.list_exhibits(
        skip=0, 
        limit=10000,
        category=category,
        hall=hall,
        floor=floor,
    )
    total = len(all_exhibits)
    
    return ExhibitListResponse(
        exhibits=[
            ExhibitListItem(
                id=e.id.value,
                name=e.name,
                category=e.category,
                hall=e.hall,
                floor=e.location.floor if e.location else None,
                importance=e.importance,
                estimated_visit_time=e.estimated_visit_time,
                is_active=e.is_active,
            )
            for e in exhibits if e.is_active
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/stats", response_model=ExhibitStatsResponse)
async def get_exhibit_stats(
    session: SessionDep,
) -> ExhibitStatsResponse:
    """获取展品统计信息 (公开接口)"""
    service = get_exhibit_service(session)
    
    all_exhibits = await service.list_all_active()
    
    # 统计类别
    category_counts: dict[str, int] = {}
    hall_counts: dict[str, int] = {}
    
    for exhibit in all_exhibits:
        if exhibit.category:
            category_counts[exhibit.category] = category_counts.get(exhibit.category, 0) + 1
        if exhibit.hall:
            hall_counts[exhibit.hall] = hall_counts.get(exhibit.hall, 0) + 1
    
    return ExhibitStatsResponse(
        total_exhibits=len(all_exhibits),
        categories=[
            CategoryStats(category=k, count=v) 
            for k, v in sorted(category_counts.items(), key=lambda x: -x[1])
        ],
        halls=[
            HallStats(hall=k, count=v)
            for k, v in sorted(hall_counts.items(), key=lambda x: -x[1])
        ],
    )


@router.get("/{exhibit_id}", response_model=ExhibitDetail)
async def get_exhibit(
    session: SessionDep,
    exhibit_id: str,
) -> ExhibitDetail:
    """获取单个展品详情 (公开接口)"""
    from app.domain.value_objects import ExhibitId
    
    service = get_exhibit_service(session)
    exhibit = await service.get_exhibit(exhibit_id)
    
    if not exhibit or not exhibit.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exhibit not found: {exhibit_id}",
        )
    
    return ExhibitDetail(
        id=exhibit.id.value,
        name=exhibit.name,
        description=exhibit.description,
        category=exhibit.category,
        hall=exhibit.hall,
        floor=exhibit.location.floor if exhibit.location else None,
        era=exhibit.era,
        importance=exhibit.importance,
        estimated_visit_time=exhibit.estimated_visit_time,
        location_x=exhibit.location.x if exhibit.location else None,
        location_y=exhibit.location.y if exhibit.location else None,
        is_active=exhibit.is_active,
    )


@router.get("/categories/list", response_model=list[str])
async def list_categories(
    session: SessionDep,
) -> list[str]:
    """获取所有展品类别列表"""
    service = get_exhibit_service(session)
    categories = await service.get_all_categories()
    return categories


@router.get("/halls/list", response_model=list[str])
async def list_halls(
    session: SessionDep,
) -> list[str]:
    """获取所有展厅列表"""
    service = get_exhibit_service(session)
    halls = await service.get_all_halls()
    return halls
```

### Step 2: 注册路由

Modify `backend/app/main.py`:

```python
# Add import
from app.api.exhibits import router as exhibits_router

# ... existing router registrations ...
app.include_router(admin_router, prefix="/api/v1")
app.include_router(curator_router, prefix="/api/v1")
app.include_router(profile_router, prefix="/api/v1")

# Add new public exhibits router
app.include_router(exhibits_router, prefix="/api/v1")
```

---

## Task 2: 扩展 Exhibit Service

**Files:**
- Modify: `backend/app/application/exhibit_service.py`

Add new methods to `ExhibitService`:

```python
# Add to backend/app/application/exhibit_service.py

async def list_all_active(self) -> list[Exhibit]:
    """获取所有活跃展品"""
    return await self._repo.list_all_active()

async def search_exhibits(
    self,
    query: str,
    category: Optional[str] = None,
    hall: Optional[str] = None,
    floor: Optional[int] = None,
    skip: int = 0,
    limit: int = 20,
) -> list[Exhibit]:
    """搜索展品 (按名称)"""
    return await self._repo.search_by_name(
        query=query,
        category=category,
        hall=hall,
        floor=floor,
        skip=skip,
        limit=limit,
    )

async def get_all_categories(self) -> list[str]:
    """获取所有类别"""
    return await self._repo.get_distinct_categories()

async def get_all_halls(self) -> list[str]:
    """获取所有展厅"""
    return await self._repo.get_distinct_halls()
```

---

## Task 3: 扩展 Repository

**Files:**
- Modify: `backend/app/infra/postgres/repositories.py`

Add new methods to `PostgresExhibitRepository`:

```python
# Add to PostgresExhibitRepository

async def list_all_active(self) -> list[Exhibit]:
    """List all active exhibits."""
    from sqlalchemy import select
    from app.infra.postgres.models import Exhibit as ExhibitORM
    
    result = await self._session.execute(
        select(ExhibitORM).where(ExhibitORM.is_active == True)
    )
    orms = result.scalars().all()
    return [self._to_entity(orm) for orm in orms]

async def search_by_name(
    self,
    query: str,
    category: Optional[str] = None,
    hall: Optional[str] = None,
    floor: Optional[int] = None,
    skip: int = 0,
    limit: int = 20,
) -> list[Exhibit]:
    """Search exhibits by name (case-insensitive)."""
    from sqlalchemy import select, or_
    from app.infra.postgres.models import Exhibit as ExhibitORM
    
    stmt = select(ExhibitORM).where(
        ExhibitORM.is_active == True,
        ExhibitORM.name.ilike(f"%{query}%")
    )
    
    if category:
        stmt = stmt.where(ExhibitORM.category == category)
    if hall:
        stmt = stmt.where(ExhibitORM.hall == hall)
    if floor is not None:
        stmt = stmt.where(ExhibitORM.floor == floor)
    
    stmt = stmt.offset(skip).limit(limit)
    
    result = await self._session.execute(stmt)
    orms = result.scalars().all()
    return [self._to_entity(orm) for orm in orms]

async def get_distinct_categories(self) -> list[str]:
    """Get distinct category values."""
    from sqlalchemy import select, distinct
    from app.infra.postgres.models import Exhibit as ExhibitORM
    
    result = await self._session.execute(
        select(distinct(ExhibitORM.category))
        .where(ExhibitORM.is_active == True)
        .where(ExhibitORM.category.isnot(None))
        .order_by(ExhibitORM.category)
    )
    return [row[0] for row in result.all() if row[0]]

async def get_distinct_halls(self) -> list[str]:
    """Get distinct hall values."""
    from sqlalchemy import select, distinct
    from app.infra.postgres.models import Exhibit as ExhibitORM
    
    result = await self._session.execute(
        select(distinct(ExhibitORM.hall))
        .where(ExhibitORM.is_active == True)
        .where(ExhibitORM.hall.isnot(None))
        .order_by(ExhibitORM.hall)
    )
    return [row[0] for row in result.all() if row[0]]
```

---

## Task 4: 新增 Admin Update Exhibit API

**Files:**
- Modify: `backend/app/api/admin.py`

### Step 1: 添加 Update Request Model

```python
# Add to backend/app/api/admin.py

class UpdateExhibitRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    location_x: Optional[float] = None
    location_y: Optional[float] = None
    floor: Optional[int] = None
    hall: Optional[str] = None
    category: Optional[str] = None
    era: Optional[str] = None
    importance: Optional[int] = None
    estimated_visit_time: Optional[int] = None
    document_id: Optional[str] = None
    is_active: Optional[bool] = None
```

### Step 2: 添加 Update Endpoint

```python
# Add to backend/app/api/admin.py

@router.put("/exhibits/{exhibit_id}", response_model=ExhibitResponse)
async def update_exhibit(
    session: SessionDep,
    exhibit_id: str,
    request: UpdateExhibitRequest,
    current_user: CurrentAdminUser,
) -> ExhibitResponse:
    """Update an exhibit (admin only)."""
    service = get_exhibit_service(session)
    
    # Build update dict with non-None values
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    
    try:
        exhibit = await service.update_exhibit(exhibit_id, **updates)
    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exhibit not found: {exhibit_id}",
        )
    
    return ExhibitResponse(
        id=exhibit.id.value,
        name=exhibit.name,
        description=exhibit.description,
        location_x=exhibit.location.x if exhibit.location else 0,
        location_y=exhibit.location.y if exhibit.location else 0,
        floor=exhibit.location.floor if exhibit.location else 1,
        hall=exhibit.hall,
        category=exhibit.category,
        era=exhibit.era,
        importance=exhibit.importance,
        estimated_visit_time=exhibit.estimated_visit_time,
        document_id=exhibit.document_id or "",
        is_active=exhibit.is_active,
        created_at=exhibit.created_at.isoformat(),
        updated_at=exhibit.updated_at.isoformat(),
    )
```

### Step 3: 添加 Update Method to Service

```python
# Add to ExhibitService

async def update_exhibit(self, exhibit_id: str, **updates) -> Exhibit:
    """Update an exhibit."""
    from app.domain.value_objects import ExhibitId, Location
    
    # Get existing exhibit
    existing = await self._repo.get_by_id(ExhibitId(exhibit_id))
    if not existing:
        raise EntityNotFoundError(f"Exhibit not found: {exhibit_id}")
    
    # Handle location updates
    if any(k in updates for k in ["location_x", "location_y", "floor"]):
        x = updates.pop("location_x", existing.location.x if existing.location else 0)
        y = updates.pop("location_y", existing.location.y if existing.location else 0)
        floor = updates.pop("floor", existing.location.floor if existing.location else 1)
        updates["location"] = Location(x=x, y=y, floor=floor)
    
    # Handle document_id
    if "document_id" in updates:
        from app.domain.value_objects import DocumentId
        doc_id = updates.pop("document_id")
        updates["document_id"] = DocumentId(doc_id) if doc_id else None
    
    # Apply updates
    for key, value in updates.items():
        if hasattr(existing, key):
            setattr(existing, key, value)
    
    # Save
    return await self._repo.update(existing)
```

---

## Task 5: RAG 索引展品信息

**Files:**
- Create: `backend/app/application/exhibit_indexing_service.py`
- Modify: `backend/app/infra/elasticsearch/client.py`

### Step 1: 扩展 ES Client 支持展品索引

Modify `backend/app/infra/elasticsearch/client.py`:

```python
# Add new methods to ElasticsearchClient

async def index_exhibit(self, exhibit_doc: dict[str, Any]) -> dict[str, Any]:
    """Index an exhibit document to Elasticsearch.
    
    Args:
        exhibit_doc: Exhibit document with fields:
            - exhibit_id: str
            - name: str
            - description: str
            - category: str
            - hall: str
            - floor: int
            - era: str
            - content_vector: list[float] (embedding of name+description)
            - metadata: dict
    
    Returns:
        Index result
    """
    try:
        exhibit_id = exhibit_doc["exhibit_id"]
        # Use a specific ID format for exhibits
        doc_id = f"exhibit_{exhibit_id}"
        
        result = await self.client.index(
            index=self.index_name, 
            id=doc_id, 
            document=exhibit_doc
        )
        logger.info(f"Indexed exhibit: {exhibit_id}")
        return cast(dict[str, Any], result)
    except (ApiError, TransportError) as e:
        logger.error(f"Failed to index exhibit: {type(e).__name__}")
        raise RetrievalError("Failed to index exhibit")

async def delete_exhibit(self, exhibit_id: str) -> dict[str, Any]:
    """Delete an exhibit document from Elasticsearch."""
    try:
        doc_id = f"exhibit_{exhibit_id}"
        result = await self.client.delete(index=self.index_name, id=doc_id)
        logger.info(f"Deleted exhibit from index: {exhibit_id}")
        return cast(dict[str, Any], result)
    except (ApiError, TransportError) as e:
        if e.meta.status == 404:
            return {"status": "not_found"}
        logger.error(f"Failed to delete exhibit: {type(e).__name__}")
        raise RetrievalError("Failed to delete exhibit")

async def search_exhibits(
    self, 
    query_vector: list[float], 
    top_k: int = 5,
    filters: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """Search exhibits using vector similarity.
    
    Args:
        query_vector: Query embedding vector
        top_k: Number of results
        filters: Optional filters (category, hall, floor)
    
    Returns:
        List of exhibit documents
    """
    try:
        # Build filter query
        filter_queries = [{"term": {"doc_type": "exhibit"}}]
        
        if filters:
            if filters.get("category"):
                filter_queries.append({"term": {"category": filters["category"]}})
            if filters.get("hall"):
                filter_queries.append({"term": {"hall": filters["hall"]}})
            if filters.get("floor") is not None:
                filter_queries.append({"term": {"floor": filters["floor"]}})
        
        query = {
            "knn": {
                "field": "content_vector",
                "query_vector": query_vector,
                "k": top_k,
                "num_candidates": top_k * 10,
                "filter": {"bool": {"must": filter_queries}},
            },
            "size": top_k,
        }
        
        response = await self.client.search(index=self.index_name, body=query)
        return [cast(dict[str, Any], hit["_source"]) for hit in response["hits"]["hits"]]
    except (ApiError, TransportError) as e:
        logger.error(f"Exhibit search failed: {type(e).__name__}")
        raise RetrievalError("Exhibit search failed")
```

### Step 2: 创建展品索引服务

Create `backend/app/application/exhibit_indexing_service.py`:

```python
"""展品索引服务 - 将展品信息索引到 Elasticsearch 用于 RAG 检索"""

from typing import Any

from loguru import logger

from app.domain.entities import Exhibit
from app.infra.elasticsearch.client import ElasticsearchClient
from app.infra.langchain.embeddings import CustomOllamaEmbeddings


class ExhibitIndexingService:
    """Service for indexing exhibit information to Elasticsearch."""
    
    def __init__(
        self,
        es_client: ElasticsearchClient,
        embeddings: CustomOllamaEmbeddings,
    ):
        self.es_client = es_client
        self.embeddings = embeddings
    
    def _build_exhibit_text(self, exhibit: Exhibit) -> str:
        """Build searchable text from exhibit information.
        
        Combines name, description, category, era, and hall into
        a single text for embedding.
        """
        parts = [f"展品名称: {exhibit.name}"]
        
        if exhibit.description:
            parts.append(f"描述: {exhibit.description}")
        if exhibit.category:
            parts.append(f"类别: {exhibit.category}")
        if exhibit.era:
            parts.append(f"年代: {exhibit.era}")
        if exhibit.hall:
            parts.append(f"展厅: {exhibit.hall}")
        
        return "\n".join(parts)
    
    async def index_exhibit(self, exhibit: Exhibit) -> dict[str, Any]:
        """Index a single exhibit to Elasticsearch.
        
        Args:
            exhibit: Exhibit entity to index
            
        Returns:
            Index operation result
        """
        # Build searchable text
        text = self._build_exhibit_text(exhibit)
        
        # Generate embedding
        embedding = await self.embeddings.aembed_query(text)
        
        # Build document
        doc = {
            "doc_type": "exhibit",  # Mark as exhibit document
            "exhibit_id": exhibit.id.value,
            "name": exhibit.name,
            "description": exhibit.description or "",
            "category": exhibit.category or "",
            "hall": exhibit.hall or "",
            "floor": exhibit.location.floor if exhibit.location else 1,
            "era": exhibit.era or "",
            "importance": exhibit.importance,
            "estimated_visit_time": exhibit.estimated_visit_time or 0,
            "content": text,  # Searchable content
            "content_vector": embedding,
            "location_x": exhibit.location.x if exhibit.location else 0,
            "location_y": exhibit.location.y if exhibit.location else 0,
            "is_active": exhibit.is_active,
            "document_id": exhibit.document_id.value if exhibit.document_id else None,
        }
        
        # Index to ES
        result = await self.es_client.index_exhibit(doc)
        logger.info(f"Indexed exhibit {exhibit.id.value}: {exhibit.name}")
        return result
    
    async def delete_exhibit_index(self, exhibit_id: str) -> dict[str, Any]:
        """Delete an exhibit from the search index.
        
        Args:
            exhibit_id: Exhibit ID to delete
            
        Returns:
            Delete operation result
        """
        result = await self.es_client.delete_exhibit(exhibit_id)
        logger.info(f"Deleted exhibit {exhibit_id} from index")
        return result
    
    async def reindex_all_exhibits(
        self,
        exhibits: list[Exhibit],
        batch_size: int = 10,
    ) -> dict[str, Any]:
        """Reindex all exhibits (useful for rebuilding index).
        
        Args:
            exhibits: List of exhibits to index
            batch_size: Number of exhibits to process concurrently
            
        Returns:
            Reindexing statistics
        """
        import asyncio
        
        semaphore = asyncio.Semaphore(batch_size)
        
        async def index_with_semaphore(exhibit: Exhibit) -> bool:
            async with semaphore:
                try:
                    await self.index_exhibit(exhibit)
                    return True
                except Exception as e:
                    logger.error(f"Failed to index exhibit {exhibit.id.value}: {e}")
                    return False
        
        results = await asyncio.gather(*[
            index_with_sehibit(e) for e in exhibits if e.is_active
        ])
        
        success_count = sum(results)
        fail_count = len(results) - success_count
        
        logger.info(f"Reindexed {success_count} exhibits, {fail_count} failed")
        
        return {
            "total": len(results),
            "success": success_count,
            "failed": fail_count,
        }
```

---

## Task 6: 集成索引到 Admin API

**Files:**
- Modify: `backend/app/api/admin.py`

### Step 1: 添加索引触发

Modify exhibit creation and update endpoints to trigger indexing:

```python
# Modify create_exhibit endpoint in admin.py

from fastapi import Request

@router.post("/exhibits", response_model=ExhibitResponse, status_code=status.HTTP_201_CREATED)
async def create_exhibit(
    session: SessionDep,
    request: CreateExhibitRequest,
    current_user: CurrentAdminUser,
    http_request: Request,  # Add to get app state
) -> ExhibitResponse:
    """Create a new exhibit (admin only)."""
    service = get_exhibit_service(session)
    
    exhibit = await service.create_exhibit(...)
    
    # Index to Elasticsearch
    try:
        es_client = http_request.app.state.es_client
        embeddings = http_request.app.state.embeddings
        
        from app.application.exhibit_indexing_service import ExhibitIndexingService
        indexing_service = ExhibitIndexingService(es_client, embeddings)
        await indexing_service.index_exhibit(exhibit)
    except Exception as e:
        logger.error(f"Failed to index exhibit {exhibit.id.value}: {e}")
        # Don't fail the request, just log the error
    
    return ExhibitResponse(...)


@router.put("/exhibits/{exhibit_id}", response_model=ExhibitResponse)
async def update_exhibit(
    session: SessionDep,
    exhibit_id: str,
    request: UpdateExhibitRequest,
    current_user: CurrentAdminUser,
    http_request: Request,
) -> ExhibitResponse:
    """Update an exhibit (admin only)."""
    service = get_exhibit_service(session)
    
    exhibit = await service.update_exhibit(exhibit_id, **updates)
    
    # Re-index to Elasticsearch
    try:
        es_client = http_request.app.state.es_client
        embeddings = http_request.app.state.embeddings
        
        from app.application.exhibit_indexing_service import ExhibitIndexingService
        indexing_service = ExhibitIndexingService(es_client, embeddings)
        
        if exhibit.is_active:
            await indexing_service.index_exhibit(exhibit)
        else:
            # If deactivated, remove from index
            await indexing_service.delete_exhibit_index(exhibit_id)
    except Exception as e:
        logger.error(f"Failed to re-index exhibit {exhibit_id}: {e}")
    
    return ExhibitResponse(...)


@router.delete("/exhibits/{exhibit_id}", response_model=DeleteResponse)
async def delete_exhibit(
    session: SessionDep,
    exhibit_id: str,
    current_user: CurrentAdminUser,
    http_request: Request,
) -> DeleteResponse:
    """Delete an exhibit (admin only)."""
    service = get_exhibit_service(session)
    
    success = await service.delete_exhibit(exhibit_id)
    
    # Remove from Elasticsearch index
    if success:
        try:
            es_client = http_request.app.state.es_client
            from app.application.exhibit_indexing_service import ExhibitIndexingService
            indexing_service = ExhibitIndexingService(es_client, None)
            await indexing_service.delete_exhibit_index(exhibit_id)
        except Exception as e:
            logger.error(f"Failed to delete exhibit {exhibit_id} from index: {e}")
    
    return DeleteResponse(status="deleted", exhibit_id=exhibit_id)
```

---

## Task 7: 扩展 RAG 检索器支持展品

**Files:**
- Modify: `backend/app/infra/langchain/retrievers.py`

### Step 1: 创建展品感知检索器

```python
# Modify backend/app/infra/langchain/retrievers.py

from typing import Any, Optional

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, Field

from app.application.retrieval import rrf_fusion


class ExhibitAwareRetriever(BaseRetriever):
    """展品感知检索器 - 同时检索文档 chunks 和展品信息"""
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    es_client: Any
    embeddings: Any
    top_k: int = 5
    rrf_k: int = 60
    include_exhibits: bool = True  # 是否包含展品检索
    exhibit_weight: float = 0.3    # 展品结果权重 (0-1)
    
    def _get_relevant_documents(self, query: str) -> list[Document]:
        raise NotImplementedError("Use _aget_relevant_documents")
    
    async def _aget_relevant_documents(
        self, 
        query: str,
        exhibit_filters: Optional[dict[str, Any]] = None,
    ) -> list[Document]:
        """Retrieve relevant documents including exhibit information.
        
        Args:
            query: Search query
            exhibit_filters: Optional filters for exhibits (category, hall, floor)
            
        Returns:
            List of documents (both chunks and exhibits)
        """
        query_vector = await self.embeddings.aembed_query(query)
        
        # Search document chunks
        dense_results = await self.es_client.search_dense(
            query_vector, 
            self.top_k * 2,
            filters={"doc_type": "chunk"}  # Only search chunks
        )
        bm25_results = await self.es_client.search_bm25(
            query, 
            self.top_k * 2,
            filters={"doc_type": "chunk"}
        )
        
        # Fuse chunk results
        chunk_fused = rrf_fusion(dense_results, bm25_results, k=self.rrf_k)
        
        documents = []
        
        # Add chunk documents
        for item in chunk_fused[:self.top_k]:
            doc = Document(
                page_content=item.get("content", ""),
                metadata={
                    "chunk_id": item.get("chunk_id"),
                    "document_id": item.get("document_id"),
                    "chunk_level": item.get("chunk_level"),
                    "source": item.get("source"),
                    "rrf_score": item.get("rrf_score"),
                    "doc_type": "chunk",
                },
            )
            documents.append(doc)
        
        # Search exhibits if enabled
        if self.include_exhibits:
            exhibit_results = await self.es_client.search_exhibits(
                query_vector=query_vector,
                top_k=max(1, int(self.top_k * self.exhibit_weight)),
                filters=exhibit_filters,
            )
            
            for item in exhibit_results:
                # Build exhibit description
                content = f"""展品: {item.get('name', '')}
描述: {item.get('description', '')}
类别: {item.get('category', '')}
展厅: {item.get('hall', '')}
年代: {item.get('era', '')}"""
                
                doc = Document(
                    page_content=content,
                    metadata={
                        "exhibit_id": item.get("exhibit_id"),
                        "name": item.get("name"),
                        "category": item.get("category"),
                        "hall": item.get("hall"),
                        "floor": item.get("floor"),
                        "doc_type": "exhibit",
                        "rrf_score": item.get("_score", 0),
                    },
                )
                documents.append(doc)
        
        # Sort by score
        documents.sort(
            key=lambda x: x.metadata.get("rrf_score", 0), 
            reverse=True
        )
        
        return documents[:self.top_k]
```

---

## Task 8: 创建重新索引 Admin 端点

**Files:**
- Modify: `backend/app/api/admin.py`

### Step 1: 添加批量重新索引端点

```python
# Add to backend/app/api/admin.py

class ReindexResponse(BaseModel):
    status: str
    total: int
    success: int
    failed: int


@router.post("/exhibits/reindex", response_model=ReindexResponse)
async def reindex_all_exhibits(
    session: SessionDep,
    current_user: CurrentAdminUser,
    http_request: Request,
) -> ReindexResponse:
    """Reindex all active exhibits to Elasticsearch (admin only).
    
    Useful for rebuilding the search index after schema changes.
    """
    from app.application.exhibit_indexing_service import ExhibitIndexingService
    
    # Get all active exhibits
    service = get_exhibit_service(session)
    exhibits = await service.list_all_active()
    
    # Reindex
    es_client = http_request.app.state.es_client
    embeddings = http_request.app.state.embeddings
    indexing_service = ExhibitIndexingService(es_client, embeddings)
    
    result = await indexing_service.reindex_all_exhibits(exhibits)
    
    return ReindexResponse(
        status="completed",
        total=result["total"],
        success=result["success"],
        failed=result["failed"],
    )
```

---

## Summary

### New Files (3)
- `backend/app/api/exhibits.py` - 公开展品 API
- `backend/app/application/exhibit_indexing_service.py` - 展品索引服务
- `backend/app/application/exhibit_search_service.py` - 展品搜索服务 (可选)

### Modified Files (5)
- `backend/app/main.py` - 注册新路由
- `backend/app/api/admin.py` - 添加 update exhibit 和 reindex 端点
- `backend/app/application/exhibit_service.py` - 扩展服务方法
- `backend/app/infra/postgres/repositories.py` - 添加 repository 方法
- `backend/app/infra/elasticsearch/client.py` - 扩展 ES 客户端
- `backend/app/infra/langchain/retrievers.py` - 展品感知检索器

### API Endpoints Added

**Public Exhibits API** (`/api/v1/exhibits`):
- `GET /exhibits` - List exhibits with filters
- `GET /exhibits/stats` - Get exhibit statistics
- `GET /exhibits/{id}` - Get exhibit detail
- `GET /exhibits/categories/list` - List all categories
- `GET /exhibits/halls/list` - List all halls

**Admin API Extensions** (`/api/v1/admin`):
- `PUT /admin/exhibits/{id}` - Update exhibit
- `POST /admin/exhibits/reindex` - Reindex all exhibits

### Data Flow

```
Exhibit Creation/Update
    ↓
PostgreSQL (primary storage)
    ↓
Elasticsearch (indexed copy for RAG)
    ↓
Curator Agent retrieves from both sources
```

---

**Estimated effort:** 2-3 days
**Priority order:**
1. Public Exhibits API (Task 1-3)
2. Admin Update API (Task 4)
3. Exhibit Indexing Service (Task 5-6)
4. Exhibit-Aware Retriever (Task 7)
5. Reindex Endpoint (Task 8)
