import asyncio
import uuid
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import TourEvent
from app.infra.postgres.models import TourEventModel, TourSessionModel

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 0.5


async def record_events(
    session: AsyncSession,
    tour_session_id: str,
    events: list[dict],
) -> list[TourEvent]:
    if not events:
        return []

    # Stable primary keys make an unknown commit outcome detectable even for
    # events that predate client_event_id support.
    prepared_events = [(str(uuid.uuid4()), event_data) for event_data in events]
    now = datetime.now(UTC)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # The whole lock/dedup/insert/commit transaction is the retry unit.
            # A retry must see what the database actually committed rather than
            # reusing a pre-error identity-map snapshot.
            await session.execute(
                select(TourSessionModel.id)
                .where(TourSessionModel.id == tour_session_id)
                .with_for_update()
            )
            result = await session.execute(
                select(TourEventModel).where(
                    TourEventModel.tour_session_id == tour_session_id
                )
            )
            existing_models = result.scalars().all()
            existing_by_id = {model.id: model for model in existing_models}
            existing_client_ids = {
                str(client_event_id)
                for model in existing_models
                if (client_event_id := (model.event_meta or {}).get("client_event_id"))
            }

            models: list[TourEventModel] = []
            batch_client_ids: set[str] = set()
            for event_id, event_data in prepared_events:
                if event_id in existing_by_id:
                    models.append(existing_by_id[event_id])
                    continue
                metadata = event_data.get("metadata") or {}
                client_event_id = metadata.get("client_event_id")
                if client_event_id:
                    client_event_id = str(client_event_id)
                    if (
                        client_event_id in existing_client_ids
                        or client_event_id in batch_client_ids
                    ):
                        continue
                    batch_client_ids.add(client_event_id)
                model = TourEventModel(
                    id=event_id,
                    tour_session_id=tour_session_id,
                    event_type=event_data["event_type"],
                    exhibit_id=event_data.get("exhibit_id"),
                    hall=event_data.get("hall"),
                    duration_seconds=event_data.get("duration_seconds"),
                    event_meta=metadata,
                    created_at=now,
                )
                session.add(model)
                models.append(model)

            await session.commit()
            for model in models:
                await session.refresh(model)
            return [model.to_entity() for model in models]
        except OperationalError as e:
            await session.rollback()
            if attempt < MAX_RETRIES:
                logger.warning(
                    f"record_events transaction failed (attempt {attempt}/{MAX_RETRIES}): {e}"
                )
                await asyncio.sleep(RETRY_DELAY_SECONDS * attempt)
            else:
                raise

    return []  # pragma: no cover - loop either returns or raises


async def get_events_by_session(
    session: AsyncSession,
    tour_session_id: str,
) -> list[TourEvent]:
    stmt = (
        select(TourEventModel)
        .where(TourEventModel.tour_session_id == tour_session_id)
        .order_by(TourEventModel.created_at.asc())
    )
    result = await session.execute(stmt)
    return [model.to_entity() for model in result.scalars().all()]
