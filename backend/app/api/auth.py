from fastapi import APIRouter, HTTPException, Request, status
from loguru import logger
from pydantic import BaseModel, EmailStr
from redis.exceptions import RedisError

from app.api.deps import AuthRateLimitDep, JWTHandlerDep, RedisCacheDep, SessionDep
from app.application.auth_service import (
    authenticate_user,
    create_access_token,
)
from app.infra.postgres.adapters.auth_repository import PostgresUserRepository
from app.infra.security import verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str


@router.post("/login", response_model=TokenResponse, summary="Login administrator")
async def login(
    request: LoginRequest,
    session: SessionDep,
    jwt_handler: JWTHandlerDep,
    _: AuthRateLimitDep,
):
    user_repo = PostgresUserRepository(session)
    user = await authenticate_user(
        user_repo=user_repo,
        email=request.email,
        password=request.password,
        verify_password_func=verify_password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user.id, jwt_handler)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=jwt_handler.expire_minutes * 60,
        role=user.role,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Logout administrator")
async def logout(
    request: Request,
    jwt_handler: JWTHandlerDep,
    redis: RedisCacheDep,
    _: AuthRateLimitDep,
):
    """Logout an administrator by blacklisting the current token."""
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "")

    if token:
        jti = jwt_handler.get_jti(token)

        if jti:
            try:
                # Blacklist the token with TTL matching token expiration
                ttl = jwt_handler.expire_minutes * 60
                await redis.blacklist_token(jti, ttl)
            except RedisError as e:
                logger.warning("Logout blacklist write failed: {}", e)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Logout temporarily unavailable. Please retry.",
                ) from e

    return None
