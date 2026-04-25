# backend/app/application/exhibit_service.py
from datetime import UTC, datetime

from app.application.ports.repositories import ExhibitRepositoryPort
from app.domain.entities import Exhibit
from app.domain.exceptions import EntityNotFoundError
from app.domain.value_objects import ExhibitId, Location


class ExhibitService:
    """展品管理服务，提供展品的CRUD操作。"""

    def __init__(self, exhibit_repository: ExhibitRepositoryPort):
        self._repository = exhibit_repository

    async def create_exhibit(
        self,
        name: str,
        description: str,
        location_x: float,
        location_y: float,
        floor: int,
        hall: str,
        category: str,
        era: str,
        importance: int,
        estimated_visit_time: int,
        document_id: str | None = None,
    ) -> Exhibit:
        """创建新展品。

        Args:
            name: 展品名称
            description: 展品描述
            location_x: X坐标位置
            location_y: Y坐标位置
            floor: 楼层
            hall: 展厅
            category: 类别
            era: 年代/时期
            importance: 重要性等级
            estimated_visit_time: 预计参观时间（分钟）
            document_id: 关联文档ID（可选）

        Returns:
            创建的展品实体
        """
        import uuid

        now = datetime.now(UTC)
        exhibit = Exhibit(
            id=ExhibitId(str(uuid.uuid4())),
            name=name,
            description=description,
            location=Location(x=location_x, y=location_y, floor=floor),
            hall=hall,
            category=category,
            era=era,
            importance=importance,
            estimated_visit_time=estimated_visit_time,
            document_id=document_id,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        return await self._repository.save(exhibit)

    async def get_exhibit(self, exhibit_id: str) -> Exhibit | None:
        """根据ID获取展品。

        Args:
            exhibit_id: 展品ID

        Returns:
            展品实体，如果不存在则返回None
        """
        return await self._repository.get_by_id(ExhibitId(exhibit_id))

    async def list_exhibits(
        self,
        skip: int = 0,
        limit: int = 100,
        category: str | None = None,
        hall: str | None = None,
        floor: int | None = None,
    ) -> list[Exhibit]:
        """获取展品列表，支持分页和筛选。

        Args:
            skip: 跳过的记录数
            limit: 返回的最大记录数
            category: 按类别筛选（可选）
            hall: 按展厅筛选（可选）
            floor: 按楼层筛选（可选）

        Returns:
            展品实体列表
        """
        if floor is not None:
            return await self._repository.list_with_filters(
                category=category,
                hall=hall,
                floor=floor,
                skip=skip,
                limit=limit,
            )
        if category:
            return await self._repository.list_by_category(category, skip=skip, limit=limit)
        if hall:
            return await self._repository.list_by_hall(hall, skip=skip, limit=limit)
        return await self._repository.list_all(skip=skip, limit=limit)

    async def update_exhibit(
        self,
        exhibit_id: str,
        name: str | None = None,
        description: str | None = None,
        location_x: float | None = None,
        location_y: float | None = None,
        floor: int | None = None,
        hall: str | None = None,
        category: str | None = None,
        era: str | None = None,
        importance: int | None = None,
        estimated_visit_time: int | None = None,
        document_id: str | None = None,
        is_active: bool | None = None,
    ) -> Exhibit:
        """更新展品信息。

        Args:
            exhibit_id: 展品ID
            name: 展品名称（可选）
            description: 展品描述（可选）
            location_x: X坐标位置（可选）
            location_y: Y坐标位置（可选）
            floor: 楼层（可选）
            hall: 展厅（可选）
            category: 类别（可选）
            era: 年代/时期（可选）
            importance: 重要性等级（可选）
            estimated_visit_time: 预计参观时间（可选）
            document_id: 关联文档ID（可选）
            is_active: 是否激活（可选）

        Returns:
            更新后的展品实体

        Raises:
            EntityNotFoundError: 如果展品不存在
        """
        exhibit = await self._repository.get_by_id(ExhibitId(exhibit_id))
        if exhibit is None:
            raise EntityNotFoundError(f"Exhibit not found: {exhibit_id}")

        # 更新字段
        if name is not None:
            exhibit.name = name
        if description is not None:
            exhibit.description = description
        if location_x is not None:
            exhibit.location = Location(
                x=location_x,
                y=location_y if location_y is not None else exhibit.location.y,
                floor=floor if floor is not None else exhibit.location.floor,
            )
        elif location_y is not None or floor is not None:
            exhibit.location = Location(
                x=exhibit.location.x,
                y=location_y if location_y is not None else exhibit.location.y,
                floor=floor if floor is not None else exhibit.location.floor,
            )
        if hall is not None:
            exhibit.hall = hall
        if category is not None:
            exhibit.category = category
        if era is not None:
            exhibit.era = era
        if importance is not None:
            exhibit.importance = importance
        if estimated_visit_time is not None:
            exhibit.estimated_visit_time = estimated_visit_time
        if document_id is not None:
            exhibit.document_id = document_id
        if is_active is not None:
            exhibit.is_active = is_active

        exhibit.updated_at = datetime.now(UTC)

        return await self._repository.save(exhibit)

    async def delete_exhibit(self, exhibit_id: str) -> bool:
        """删除展品。

        Args:
            exhibit_id: 展品ID

        Returns:
            是否成功删除
        """
        return await self._repository.delete(ExhibitId(exhibit_id))

    async def find_by_interests(self, interests: list[str], limit: int = 10) -> list[Exhibit]:
        """根据兴趣标签查找相关展品。

        Args:
            interests: 兴趣标签列表
            limit: 返回的最大数量

        Returns:
            匹配的展品列表
        """
        return await self._repository.find_by_interests(interests, limit)

    async def list_all_active(self) -> list[Exhibit]:
        """获取所有活跃展品。

        Returns:
            所有活跃展品列表
        """
        return await self._repository.list_all_active()

    async def search_exhibits(
        self,
        query: str,
        skip: int = 0,
        limit: int = 20,
        category: str | None = None,
        hall: str | None = None,
        floor: int | None = None,
    ) -> list[Exhibit]:
        """搜索展品（按名称）。

        Args:
            query: 搜索关键词
            skip: 跳过的记录数
            limit: 返回的最大记录数
            category: 按类别筛选（可选）
            hall: 按展厅筛选（可选）
            floor: 按楼层筛选（可选）

        Returns:
            匹配的展品列表
        """
        return await self._repository.search_by_name(
            query=query,
            category=category,
            hall=hall,
            floor=floor,
            skip=skip,
            limit=limit,
        )

    async def get_all_categories(self) -> list[str]:
        """获取所有类别。

        Returns:
            所有类别列表
        """
        return await self._repository.get_distinct_categories()

    async def get_all_halls(self) -> list[str]:
        """获取所有展厅。

        Returns:
            所有展厅列表
        """
        return await self._repository.get_distinct_halls()
