"""Admin API endpoints for prompt management."""

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.api.deps import CurrentAdminUser, PromptCacheDep, SessionDep
from app.domain.entities import Prompt, PromptVersion
from app.domain.exceptions import PromptNotFoundError
from app.infra.postgres.prompt_repository import PostgresPromptRepository

router = APIRouter(prefix="/admin/prompts", tags=["admin-prompts"])


# Pydantic models for request/response
class PromptResponse(BaseModel):
    """Response model for a single prompt."""

    id: str
    key: str
    name: str
    description: str | None
    category: str
    content: str
    variables: list[dict[str, str]]
    is_active: bool
    current_version: int
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class PromptListResponse(BaseModel):
    """Response model for list of prompts."""

    prompts: list[PromptResponse]
    total: int


class UpdatePromptRequest(BaseModel):
    """Request model for updating a prompt."""

    content: str
    change_reason: str | None = None


class VersionResponse(BaseModel):
    """Response model for a single prompt version."""

    id: str
    prompt_id: str
    version: int
    content: str
    changed_by: str | None
    change_reason: str | None
    created_at: str

    model_config = {"from_attributes": True}


class VersionListResponse(BaseModel):
    """Response model for list of prompt versions."""

    versions: list[VersionResponse]
    total: int


class ReloadResponse(BaseModel):
    """Response model for reload operations."""

    status: str
    message: str


def _prompt_to_response(prompt: Prompt) -> PromptResponse:
    """Convert Prompt entity to response model."""
    return PromptResponse(
        id=prompt.id.value,
        key=prompt.key,
        name=prompt.name,
        description=prompt.description,
        category=prompt.category,
        content=prompt.content,
        variables=prompt.variables,
        is_active=prompt.is_active,
        current_version=prompt.current_version,
        created_at=prompt.created_at.isoformat(),
        updated_at=prompt.updated_at.isoformat(),
    )


def _version_to_response(version: PromptVersion) -> VersionResponse:
    """Convert PromptVersion entity to response model."""
    return VersionResponse(
        id=version.id,
        prompt_id=version.prompt_id.value,
        version=version.version,
        content=version.content,
        changed_by=version.changed_by,
        change_reason=version.change_reason,
        created_at=version.created_at.isoformat(),
    )


def get_prompt_repository(session: SessionDep) -> PostgresPromptRepository:
    """Get prompt repository instance."""
    return PostgresPromptRepository(session)


@router.get("", response_model=PromptListResponse)
async def list_prompts(
    session: SessionDep,
    current_user: CurrentAdminUser,
    category: str | None = Query(None, description="Filter by category"),
    include_inactive: bool = Query(False, description="Include inactive prompts"),
) -> PromptListResponse:
    """List all prompts with optional filtering.

    Args:
        session: Database session
        current_user: Current admin user
        category: Optional category filter
        include_inactive: Whether to include inactive prompts

    Returns:
        List of prompts
    """
    repository = get_prompt_repository(session)
    prompts = await repository.list_all(category=category, include_inactive=include_inactive)

    return PromptListResponse(
        prompts=[_prompt_to_response(p) for p in prompts],
        total=len(prompts),
    )


@router.get("/{key}", response_model=PromptResponse)
async def get_prompt(
    session: SessionDep,
    key: str,
    current_user: CurrentAdminUser,
) -> PromptResponse:
    """Get a prompt by key.

    Args:
        session: Database session
        key: Prompt key
        current_user: Current admin user

    Returns:
        Prompt details

    Raises:
        HTTPException: 404 if prompt not found
    """
    repository = get_prompt_repository(session)
    prompt = await repository.get_by_key(key)

    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt not found: {key}",
        )

    return _prompt_to_response(prompt)


@router.put("/{key}", response_model=PromptResponse)
async def update_prompt(
    session: SessionDep,
    key: str,
    request: UpdatePromptRequest,
    current_user: CurrentAdminUser,
    prompt_cache: PromptCacheDep,
) -> PromptResponse:
    """Update a prompt's content.

    Creates a new version of the prompt.

    Args:
        session: Database session
        key: Prompt key
        request: Update request with new content
        current_user: Current admin user
        prompt_cache: Prompt cache for refreshing

    Returns:
        Updated prompt

    Raises:
        HTTPException: 404 if prompt not found
    """
    repository = get_prompt_repository(session)

    try:
        prompt = await repository.update(
            key=key,
            content=request.content,
            changed_by=current_user.get("email"),
            change_reason=request.change_reason,
        )
    except PromptNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt not found: {key}",
        ) from None

    # Refresh cache
    prompt_cache.refresh(prompt)

    return _prompt_to_response(prompt)


@router.get("/{key}/versions", response_model=VersionListResponse)
async def list_versions(
    session: SessionDep,
    key: str,
    current_user: CurrentAdminUser,
    skip: int = Query(0, ge=0, description="Number of versions to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum versions to return"),
) -> VersionListResponse:
    """List versions of a prompt.

    Args:
        session: Database session
        key: Prompt key
        current_user: Current admin user
        skip: Number of versions to skip
        limit: Maximum versions to return

    Returns:
        List of prompt versions (newest first)
    """
    repository = get_prompt_repository(session)
    versions = await repository.list_versions(key=key, skip=skip, limit=limit)
    total = await repository.count_versions(key=key)

    return VersionListResponse(
        versions=[_version_to_response(v) for v in versions],
        total=total,
    )


@router.get("/{key}/versions/{version}", response_model=VersionResponse)
async def get_version(
    session: SessionDep,
    key: str,
    version: int,
    current_user: CurrentAdminUser,
) -> VersionResponse:
    """Get a specific version of a prompt.

    Args:
        session: Database session
        key: Prompt key
        version: Version number
        current_user: Current admin user

    Returns:
        Prompt version details

    Raises:
        HTTPException: 404 if prompt or version not found
    """
    repository = get_prompt_repository(session)
    prompt_version = await repository.get_version(key=key, version=version)

    if prompt_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version} not found for prompt: {key}",
        )

    return _version_to_response(prompt_version)


@router.post("/{key}/versions/{version}/rollback", response_model=PromptResponse)
async def rollback_to_version(
    session: SessionDep,
    key: str,
    version: int,
    current_user: CurrentAdminUser,
    prompt_cache: PromptCacheDep,
) -> PromptResponse:
    """Rollback a prompt to a specific version.

    Creates a new version with the content from the specified version.

    Args:
        session: Database session
        key: Prompt key
        version: Version to rollback to
        current_user: Current admin user
        prompt_cache: Prompt cache for refreshing

    Returns:
        Updated prompt

    Raises:
        HTTPException: 404 if prompt or version not found
    """
    repository = get_prompt_repository(session)

    try:
        prompt = await repository.rollback_to_version(
            key=key,
            version=version,
            changed_by=current_user.get("email"),
            change_reason=f"Rollback to version {version}",
        )
    except PromptNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt not found: {key}",
        ) from None

    # Refresh cache
    prompt_cache.refresh(prompt)

    return _prompt_to_response(prompt)


@router.post("/{key}/reload", response_model=ReloadResponse)
async def reload_prompt(
    session: SessionDep,
    key: str,
    current_user: CurrentAdminUser,
    prompt_cache: PromptCacheDep,
) -> ReloadResponse:
    """Reload a single prompt into cache.

    Args:
        session: Database session
        key: Prompt key
        current_user: Current admin user
        prompt_cache: Prompt cache to reload into

    Returns:
        Reload status

    Raises:
        HTTPException: 404 if prompt not found
    """
    repository = get_prompt_repository(session)
    prompt = await repository.get_by_key(key)

    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt not found: {key}",
        )

    prompt_cache.refresh(prompt)

    return ReloadResponse(
        status="success",
        message=f"Prompt '{key}' reloaded successfully",
    )


@router.post("/reload-all", response_model=ReloadResponse)
async def reload_all_prompts(
    session: SessionDep,
    current_user: CurrentAdminUser,
    prompt_cache: PromptCacheDep,
) -> ReloadResponse:
    """Reload all prompts into cache.

    Args:
        session: Database session
        current_user: Current admin user
        prompt_cache: Prompt cache to reload into

    Returns:
        Reload status
    """
    repository = get_prompt_repository(session)

    # Set repository for cache (needed for load_all)
    prompt_cache.set_repository(repository)
    await prompt_cache.load_all()

    cached_keys = prompt_cache.get_all_keys()

    return ReloadResponse(
        status="success",
        message=f"Reloaded {len(cached_keys)} prompts into cache",
    )
