# backend/app/infra/postgres/repositories.py
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Exhibit, VisitorProfile
from app.domain.value_objects import (
    ExhibitId,
    Location,
    ProfileId,
    UserId,
)

from .models import Exhibit as ExhibitORM
from .models import VisitorProfile as VisitorProfileORM


class PostgresExhibitRepository:
    """PostgreSQL implementation of ExhibitRepository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_entity(self, orm: ExhibitORM) -> Exhibit:
        """Convert ORM model to domain entity."""
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

    async def get_by_id(self, exhibit_id: ExhibitId) -> Optional[Exhibit]:
        """Get an exhibit by its ID."""
        result = await self._session.execute(
            select(ExhibitORM).where(ExhibitORM.id == exhibit_id.value)
        )
        orm = result.scalar_one_or_none()
        return self._to_entity(orm) if orm else None

    async def list_all(self, include_inactive: bool = False) -> List[Exhibit]:
        """List all exhibits."""
        query = select(ExhibitORM)
        if not include_inactive:
            query = query.where(ExhibitORM.is_active.is_(True))
        result = await self._session.execute(query)
        return [self._to_entity(orm) for orm in result.scalars().all()]

    async def list_by_category(
        self, category: str, include_inactive: bool = False
    ) -> List[Exhibit]:
        """List exhibits by category."""
        query = select(ExhibitORM).where(ExhibitORM.category == category)
        if not include_inactive:
            query = query.where(ExhibitORM.is_active.is_(True))
        result = await self._session.execute(query)
        return [self._to_entity(orm) for orm in result.scalars().all()]

    async def list_by_hall(
        self, hall: str, include_inactive: bool = False
    ) -> List[Exhibit]:
        """List exhibits by hall."""
        query = select(ExhibitORM).where(ExhibitORM.hall == hall)
        if not include_inactive:
            query = query.where(ExhibitORM.is_active.is_(True))
        result = await self._session.execute(query)
        return [self._to_entity(orm) for orm in result.scalars().all()]

    async def find_by_interests(
        self, interests: List[str], limit: int = 10
    ) -> List[Exhibit]:
        """Find exhibits matching given interests (by category)."""
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
        """Save an exhibit (create or update)."""
        orm = await self._session.get(ExhibitORM, exhibit.id.value)

        if orm is None:
            # Create new
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
            # Update existing
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
        """Delete an exhibit by its ID."""
        orm = await self._session.get(ExhibitORM, exhibit_id.value)
        if orm is None:
            return False
        await self._session.delete(orm)
        await self._session.flush()
        return True


class PostgresVisitorProfileRepository:
    """PostgreSQL implementation of VisitorProfileRepository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_entity(self, orm: VisitorProfileORM) -> VisitorProfile:
        """Convert ORM model to domain entity."""
        return VisitorProfile(
            id=ProfileId(orm.id),
            user_id=UserId(orm.user_id),
            interests=list(orm.interests) if orm.interests else [],
            knowledge_level=orm.knowledge_level or "beginner",
            narrative_preference=orm.narrative_preference or "balanced",
            reflection_depth=str(orm.reflection_depth)
            if orm.reflection_depth is not None
            else "2",
            visited_exhibit_ids=[ExhibitId(eid) for eid in orm.visited_exhibit_ids]
            if orm.visited_exhibit_ids
            else [],
            feedback_history=list(orm.feedback_history)
            if orm.feedback_history
            else [],
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    async def get_by_id(self, profile_id: ProfileId) -> Optional[VisitorProfile]:
        """Get a visitor profile by its ID."""
        result = await self._session.execute(
            select(VisitorProfileORM).where(VisitorProfileORM.id == profile_id.value)
        )
        orm = result.scalar_one_or_none()
        return self._to_entity(orm) if orm else None

    async def get_by_user_id(self, user_id: UserId) -> Optional[VisitorProfile]:
        """Get a visitor profile by user ID."""
        result = await self._session.execute(
            select(VisitorProfileORM).where(
                VisitorProfileORM.user_id == user_id.value
            )
        )
        orm = result.scalar_one_or_none()
        return self._to_entity(orm) if orm else None

    async def save(self, profile: VisitorProfile) -> VisitorProfile:
        """Save a visitor profile (create or update)."""
        orm = await self._session.get(VisitorProfileORM, profile.id.value)

        # Convert reflection_depth to int for storage
        try:
            reflection_depth = int(profile.reflection_depth)
        except (ValueError, TypeError):
            reflection_depth = 2

        if orm is None:
            # Create new
            orm = VisitorProfileORM(
                id=profile.id.value,
                user_id=profile.user_id.value,
                interests=profile.interests,
                knowledge_level=profile.knowledge_level,
                narrative_preference=profile.narrative_preference,
                reflection_depth=reflection_depth,
                visited_exhibit_ids=[eid.value for eid in profile.visited_exhibit_ids],
                feedback_history=profile.feedback_history,
                created_at=profile.created_at,
                updated_at=profile.updated_at,
            )
            self._session.add(orm)
        else:
            # Update existing
            orm.interests = profile.interests
            orm.knowledge_level = profile.knowledge_level
            orm.narrative_preference = profile.narrative_preference
            orm.reflection_depth = reflection_depth
            orm.visited_exhibit_ids = [
                eid.value for eid in profile.visited_exhibit_ids
            ]
            orm.feedback_history = profile.feedback_history
            orm.updated_at = profile.updated_at

        await self._session.flush()
        return self._to_entity(orm)

    async def update(self, profile: VisitorProfile) -> VisitorProfile:
        """Update an existing visitor profile."""
        return await self.save(profile)
