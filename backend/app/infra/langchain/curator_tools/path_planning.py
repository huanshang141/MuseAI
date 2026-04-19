import json
import math
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class PathPlanningInput(BaseModel):
    interests: list[str] = Field(..., description="List of user interests/categories")
    available_time: int = Field(..., description="Available time in minutes")
    current_location: dict[str, Any] = Field(
        ..., description="Current location with x, y, floor"
    )
    visited_exhibit_ids: list[str] = Field(
        default_factory=list, description="List of already visited exhibit IDs"
    )


class PathPlanningTool(BaseTool):
    name: str = "path_planning"
    description: str = (
        "Plan an optimal tour path based on user interests, available time, and current location. "
        "Uses nearest neighbor TSP algorithm for path optimization. "
        "Input should include interests (list of categories), available_time (minutes), "
        "current_location (dict with x, y, floor), and optionally visited_exhibit_ids."
    )

    exhibit_repository: Any = Field(
        ..., description="Repository for exhibit data (ExhibitRepository protocol)"
    )

    def _calculate_distance(
        self, loc1: dict[str, Any], loc2: dict[str, Any]
    ) -> float:
        floor_penalty = 0
        if loc1.get("floor", 1) != loc2.get("floor", 1):
            floor_penalty = 100

        dx = loc1.get("x", 0) - loc2.get("x", 0)
        dy = loc1.get("y", 0) - loc2.get("y", 0)
        return math.sqrt(dx * dx + dy * dy) + floor_penalty

    def _nearest_neighbor_tsp(
        self,
        start: dict[str, Any],
        exhibits: list[Any],
        visited_ids: set[str],
        max_time: int,
    ) -> tuple[list[dict[str, Any]], int, int]:
        path = []
        current_location = start
        total_time = 0
        remaining_exhibits = [
            e for e in exhibits if e.id.value not in visited_ids
        ]
        visited_in_path = set()

        while remaining_exhibits and total_time < max_time:
            nearest = None
            nearest_dist = float("inf")
            nearest_idx = -1

            for idx, exhibit in enumerate(remaining_exhibits):
                exhibit_loc = {
                    "x": exhibit.location.x,
                    "y": exhibit.location.y,
                    "floor": exhibit.location.floor,
                }
                dist = self._calculate_distance(current_location, exhibit_loc)
                if dist < nearest_dist:
                    nearest_dist = dist
                    nearest = exhibit
                    nearest_idx = idx

            if nearest is None:
                break

            travel_time = max(1, int(nearest_dist / 10))
            visit_time = nearest.estimated_visit_time or 5
            total_time_needed = travel_time + visit_time

            if total_time + total_time_needed > max_time:
                break

            path.append(
                {
                    "id": nearest.id.value,
                    "name": nearest.name,
                    "category": nearest.category,
                    "location": {
                        "x": nearest.location.x,
                        "y": nearest.location.y,
                        "floor": nearest.location.floor,
                    },
                    "estimated_visit_time": visit_time,
                }
            )
            total_time += total_time_needed
            visited_in_path.add(nearest.id.value)

            current_location = {
                "x": nearest.location.x,
                "y": nearest.location.y,
                "floor": nearest.location.floor,
            }

            remaining_exhibits.pop(nearest_idx)

        return path, total_time, len(path)

    async def _arun(self, query: str) -> str:
        try:
            data = json.loads(query)
            input_data = PathPlanningInput(**data)
        except (json.JSONDecodeError, Exception) as e:
            return json.dumps(
                {"error": f"Invalid input: {str(e)}"}
            )

        try:
            exhibits = await self.exhibit_repository.find_by_interests(
                input_data.interests, limit=50
            )

            if not exhibits:
                return json.dumps(
                    {
                        "path": [],
                        "estimated_duration": 0,
                        "exhibit_count": 0,
                        "message": "No exhibits found matching your interests.",
                    }
                )

            visited_ids = set(input_data.visited_exhibit_ids)
            path, duration, count = self._nearest_neighbor_tsp(
                input_data.current_location,
                exhibits,
                visited_ids,
                input_data.available_time,
            )

            result = {
                "path": path,
                "estimated_duration": duration,
                "exhibit_count": count,
            }
            return json.dumps(result, ensure_ascii=False)

        except Exception as e:
            return json.dumps({"error": str(e)})

    def _run(self, query: str) -> str:
        raise NotImplementedError("This tool only supports async execution")
