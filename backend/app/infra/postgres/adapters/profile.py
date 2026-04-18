from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import VisitorProfile
from app.domain.value_objects import ExhibitId, ProfileId, UserId

from ..models import VisitorProfile as VisitorProfileORM


class PostgresVisitorProfileRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_entity(self, orm: VisitorProfileORM) -> VisitorProfile:
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

    async def get_by_id(self, profile_id: ProfileId) -> VisitorProfile | None:
        result = await self._session.execute(
            select(VisitorProfileORM).where(VisitorProfileORM.id == profile_id.value)
        )
        orm = result.scalar_one_or_none()
        return self._to_entity(orm) if orm else None

    async def get_by_user_id(self, user_id: UserId) -> VisitorProfile | None:
        result = await self._session.execute(
            select(VisitorProfileORM).where(
                VisitorProfileORM.user_id == user_id.value
            )
        )
        orm = result.scalar_one_or_none()
        return self._to_entity(orm) if orm else None

    async def save(self, profile: VisitorProfile) -> VisitorProfile:
        orm = await self._session.get(VisitorProfileORM, profile.id.value)

        try:
            reflection_depth = int(profile.reflection_depth)
        except (ValueError, TypeError):
            reflection_depth = 2

        if orm is None:
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
        return await self.save(profile)
