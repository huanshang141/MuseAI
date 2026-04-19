import json
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.domain.value_objects import ExhibitId, UserId


class PreferenceManagementInput(BaseModel):
    action: str = Field(
        ..., description="Action to perform: 'get' or 'update'"
    )
    user_id: str = Field(..., description="User ID")
    updates: dict[str, Any] | None = Field(
        None, description="Updates to apply (for update action)"
    )


class PreferenceManagementTool(BaseTool):
    name: str = "preference_management"
    description: str = (
        "Manage user preferences and profile information. "
        "Input should include action ('get' or 'update'), user_id, "
        "and optionally updates (dict with fields to update)."
    )

    profile_repository: Any = Field(
        ..., description="Repository for visitor profiles (VisitorProfileRepository protocol)"
    )

    async def _arun(self, query: str) -> str:
        try:
            data = json.loads(query)
            input_data = PreferenceManagementInput(**data)
        except (json.JSONDecodeError, Exception) as e:
            return json.dumps({"error": f"Invalid input: {str(e)}"})

        try:
            user_id = UserId(input_data.user_id)

            if input_data.action == "get":
                profile = await self.profile_repository.get_by_user_id(user_id)
                if profile:
                    result = {
                        "success": True,
                        "profile": {
                            "id": profile.id.value,
                            "user_id": profile.user_id.value,
                            "interests": profile.interests,
                            "knowledge_level": profile.knowledge_level,
                            "narrative_preference": profile.narrative_preference,
                            "reflection_depth": profile.reflection_depth,
                            "visited_exhibit_ids": [
                                eid.value for eid in profile.visited_exhibit_ids
                            ],
                        },
                    }
                else:
                    result = {
                        "success": False,
                        "message": "Profile not found",
                    }

            elif input_data.action == "update":
                if not input_data.updates:
                    return json.dumps(
                        {"success": False, "message": "No updates provided"}
                    )

                profile = await self.profile_repository.get_by_user_id(user_id)
                if not profile:
                    return json.dumps(
                        {"success": False, "message": "Profile not found"}
                    )

                updates = input_data.updates
                if "interests" in updates:
                    profile.interests = updates["interests"]
                if "knowledge_level" in updates:
                    profile.knowledge_level = updates["knowledge_level"]
                if "narrative_preference" in updates:
                    profile.narrative_preference = updates["narrative_preference"]
                if "reflection_depth" in updates:
                    profile.reflection_depth = str(updates["reflection_depth"])
                if "visited_exhibit_ids" in updates:
                    profile.visited_exhibit_ids = [
                        ExhibitId(eid) for eid in updates["visited_exhibit_ids"]
                    ]

                updated = await self.profile_repository.update(profile)
                result = {
                    "success": True,
                    "profile": {
                        "id": updated.id.value,
                        "user_id": updated.user_id.value,
                        "interests": updated.interests,
                        "knowledge_level": updated.knowledge_level,
                        "narrative_preference": updated.narrative_preference,
                        "reflection_depth": updated.reflection_depth,
                    },
                }

            else:
                result = {
                    "success": False,
                    "message": f"Unknown action: {input_data.action}",
                }

            return json.dumps(result, ensure_ascii=False)

        except Exception as e:
            return json.dumps({"error": str(e)})

    def _run(self, query: str) -> str:
        raise NotImplementedError("This tool only supports async execution")
