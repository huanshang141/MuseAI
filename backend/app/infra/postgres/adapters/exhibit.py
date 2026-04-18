from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Exhibit
from app.domain.value_objects import ExhibitId, Location

from ..models import Exhibit as ExhibitORM


class PostgresExhibitRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_entity(self, orm: ExhibitORM) -> Exhibit:
        return Exhibit(
            id=ExhibitId(orm.id),
            name=orm.name,
            description=orm.description or "",
            location=Location(
                x=orm.location_x or 0.0,
                y=orm.location_y or 0.0,
                floor=orm.floor or 1,
            ),
            hall=orm.hall or "",
            category=orm.category or "",
            era=orm.era or "",
            importance=orm.importance,
            estimated_visit_time=orm.estimated_visit_time or 0,
            document_id=orm.document_id or "",
            is_active=orm.is_active,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    async def get_by_id(self, exhibit_id: ExhibitId) -> Exhibit | None:
        result = await self._session.execute(
            select(ExhibitORM).where(ExhibitORM.id == exhibit_id.value)
        )
        orm = result.scalar_one_or_none()
        return self._to_entity(orm) if orm else None

    async def list_all(
        self,
        include_inactive: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Exhibit]:
        query = select(ExhibitORM)
        if not include_inactive:
            query = query.where(ExhibitORM.is_active.is_(True))
        query = query.order_by(ExhibitORM.created_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(query)
        return [self._to_entity(orm) for orm in result.scalars().all()]

    async def list_by_category(
        self,
        category: str,
        include_inactive: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Exhibit]:
        query = select(ExhibitORM).where(ExhibitORM.category == category)
        if not include_inactive:
            query = query.where(ExhibitORM.is_active.is_(True))
        query = query.order_by(ExhibitORM.created_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(query)
        return [self._to_entity(orm) for orm in result.scalars().all()]

    async def list_by_hall(
        self,
        hall: str,
        include_inactive: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Exhibit]:
        query = select(ExhibitORM).where(ExhibitORM.hall == hall)
        if not include_inactive:
            query = query.where(ExhibitORM.is_active.is_(True))
        query = query.order_by(ExhibitORM.created_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(query)
        return [self._to_entity(orm) for orm in result.scalars().all()]

    async def find_by_interests(
        self, interests: list[str], limit: int = 10
    ) -> list[Exhibit]:
        if not interests:
            return []
        query = (
            select(ExhibitORM)
            .where(ExhibitORM.category.in_(interests))
            .where(ExhibitORM.is_active.is_(True))
            .limit(limit)
        )
        result = await self._session.execute(query)
        return [self._to_entity(orm) for orm in result.scalars().all()]

    async def save(self, exhibit: Exhibit) -> Exhibit:
        orm = await self._session.get(ExhibitORM, exhibit.id.value)

        if orm is None:
            orm = ExhibitORM(
                id=exhibit.id.value,
                name=exhibit.name,
                description=exhibit.description,
                location_x=exhibit.location.x,
                location_y=exhibit.location.y,
                floor=exhibit.location.floor,
                hall=exhibit.hall,
                category=exhibit.category,
                era=exhibit.era,
                importance=exhibit.importance,
                estimated_visit_time=exhibit.estimated_visit_time,
                document_id=exhibit.document_id,
                is_active=exhibit.is_active,
                created_at=exhibit.created_at,
                updated_at=exhibit.updated_at,
            )
            self._session.add(orm)
        else:
            orm.name = exhibit.name
            orm.description = exhibit.description
            orm.location_x = exhibit.location.x
            orm.location_y = exhibit.location.y
            orm.floor = exhibit.location.floor
            orm.hall = exhibit.hall
            orm.category = exhibit.category
            orm.era = exhibit.era
            orm.importance = exhibit.importance
            orm.estimated_visit_time = exhibit.estimated_visit_time
            orm.document_id = exhibit.document_id
            orm.is_active = exhibit.is_active
            orm.updated_at = exhibit.updated_at

        await self._session.flush()
        return self._to_entity(orm)

    async def delete(self, exhibit_id: ExhibitId) -> bool:
        orm = await self._session.get(ExhibitORM, exhibit_id.value)
        if orm is None:
            return False
        await self._session.delete(orm)
        await self._session.flush()
        return True

    async def list_all_active(self) -> list[Exhibit]:
        query = select(ExhibitORM).where(ExhibitORM.is_active.is_(True))
        result = await self._session.execute(query)
        return [self._to_entity(orm) for orm in result.scalars().all()]

    async def list_with_filters(
        self,
        category: str | None = None,
        hall: str | None = None,
        floor: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Exhibit]:
        query = select(ExhibitORM).where(ExhibitORM.is_active.is_(True))

        if category is not None:
            query = query.where(ExhibitORM.category == category)
        if hall is not None:
            query = query.where(ExhibitORM.hall == hall)
        if floor is not None:
            query = query.where(ExhibitORM.floor == floor)

        query = query.order_by(ExhibitORM.created_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(query)
        return [self._to_entity(orm) for orm in result.scalars().all()]

    async def search_by_name(
        self,
        query: str,
        category: str | None = None,
        hall: str | None = None,
        floor: int | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Exhibit]:
        escaped_query = query.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
        sql_query = (
            select(ExhibitORM)
            .where(ExhibitORM.is_active.is_(True))
            .where(ExhibitORM.name.ilike(f"%{escaped_query}%"))
        )

        if category is not None:
            sql_query = sql_query.where(ExhibitORM.category == category)
        if hall is not None:
            sql_query = sql_query.where(ExhibitORM.hall == hall)
        if floor is not None:
            sql_query = sql_query.where(ExhibitORM.floor == floor)

        sql_query = sql_query.offset(skip).limit(limit)
        result = await self._session.execute(sql_query)
        return [self._to_entity(orm) for orm in result.scalars().all()]

    async def get_distinct_categories(self) -> list[str]:
        query = (
            select(ExhibitORM.category)
            .where(ExhibitORM.is_active.is_(True))
            .where(ExhibitORM.category.isnot(None))
            .distinct()
            .order_by(ExhibitORM.category)
        )
        result = await self._session.execute(query)
        return [row[0] for row in result.all() if row[0] is not None]

    async def get_distinct_halls(self) -> list[str]:
        query = (
            select(ExhibitORM.hall)
            .where(ExhibitORM.is_active.is_(True))
            .where(ExhibitORM.hall.isnot(None))
            .distinct()
            .order_by(ExhibitORM.hall)
        )
        result = await self._session.execute(query)
        return [row[0] for row in result.all() if row[0] is not None]
