# backend/app/domain/repositories.py
from typing import List, Optional, Protocol

from .entities import Exhibit, TourPath, VisitorProfile
from .value_objects import ExhibitId, ProfileId, TourPathId, UserId


class ExhibitRepository(Protocol):
    """Repository protocol for Exhibit entities."""

    async def get_by_id(self, exhibit_id: ExhibitId) -> Optional[Exhibit]:
        """Get an exhibit by its ID."""
        ...

    async def list_all(self, include_inactive: bool = False) -> List[Exhibit]:
        """List all exhibits."""
        ...

    async def list_by_category(self, category: str, include_inactive: bool = False) -> List[Exhibit]:
        """List exhibits by category."""
        ...

    async def list_by_hall(self, hall: str, include_inactive: bool = False) -> List[Exhibit]:
        """List exhibits by hall."""
        ...

    async def find_by_interests(self, interests: List[str], limit: int = 10) -> List[Exhibit]:
        """Find exhibits matching given interests."""
        ...

    async def save(self, exhibit: Exhibit) -> Exhibit:
        """Save an exhibit (create or update)."""
        ...

    async def delete(self, exhibit_id: ExhibitId) -> bool:
        """Delete an exhibit by its ID. Returns True if deleted."""
        ...


class TourPathRepository(Protocol):
    """Repository protocol for TourPath entities."""

    async def get_by_id(self, tour_path_id: TourPathId) -> Optional[TourPath]:
        """Get a tour path by its ID."""
        ...

    async def list_all(self, include_inactive: bool = False) -> List[TourPath]:
        """List all tour paths."""
        ...

    async def list_by_theme(self, theme: str, include_inactive: bool = False) -> List[TourPath]:
        """List tour paths by theme."""
        ...

    async def save(self, tour_path: TourPath) -> TourPath:
        """Save a tour path (create or update)."""
        ...

    async def delete(self, tour_path_id: TourPathId) -> bool:
        """Delete a tour path by its ID. Returns True if deleted."""
        ...


class VisitorProfileRepository(Protocol):
    """Repository protocol for VisitorProfile entities."""

    async def get_by_id(self, profile_id: ProfileId) -> Optional[VisitorProfile]:
        """Get a visitor profile by its ID."""
        ...

    async def get_by_user_id(self, user_id: UserId) -> Optional[VisitorProfile]:
        """Get a visitor profile by user ID."""
        ...

    async def save(self, profile: VisitorProfile) -> VisitorProfile:
        """Save a visitor profile (create or update)."""
        ...

    async def update(self, profile: VisitorProfile) -> VisitorProfile:
        """Update an existing visitor profile."""
        ...
