from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, field_validator
from redis.exceptions import RedisError

from app.api.deps import AuthRateLimitDep, JWTHandlerDep, RedisCacheDep, SessionDep
from app.application.auth_service import (
    authenticate_user,
    create_access_token,
    get_user_by_email,
    register_user,
)
from app.config.settings import get_settings
from app.infra.security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if len(v) > 128:
            raise ValueError('Password must be at most 128 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    session: SessionDep,
    _: AuthRateLimitDep,  # Add rate limiting
):
    existing_user = await get_user_by_email(session, request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    settings = get_settings()
    user = await register_user(
        session=session,
        email=request.email,
        password=request.password,
        hash_password_func=hash_password,
        admin_emails=settings.get_admin_emails(),
    )
    await session.commit()

    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        created_at=user.created_at.isoformat(),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    session: SessionDep,
    jwt_handler: JWTHandlerDep,
    _: AuthRateLimitDep,  # Add rate limiting
):
    user = await authenticate_user(
        session=session,
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

    token = create_access_token(user.id, jwt_handler)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=jwt_handler.expire_minutes * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    jwt_handler: JWTHandlerDep,
    redis: RedisCacheDep,
):
    """Logout user by blacklisting their current token."""
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None  # No token to blacklist

    token = auth_header.replace("Bearer ", "")
    jti = jwt_handler.get_jti(token)

    if jti:
        try:
            # Blacklist the token with TTL matching token expiration
            ttl = jwt_handler.expire_minutes * 60
            await redis.blacklist_token(jti, ttl)
        except RedisError:
            # If Redis is unavailable, logout fails silently
            # Token will still expire naturally
            pass

    return None
