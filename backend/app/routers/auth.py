from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr, Field
from app.db import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.repositories.user_repo import UserRepository
from app.auth import verify_password, get_password_hash, create_access_token, create_refresh_token
from app.config import settings
from app.models import UserRole
from app.authorization import get_current_admin, require_permission
from typing import Optional

router = APIRouter(prefix="/api/auth", tags=["auth"])

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str

class UpdateUserRequest(BaseModel):
    """Request model for updating user (admin only)."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[UserRole] = Field(None, description="User role (admin/editor/viewer)")
    is_active: Optional[bool] = Field(None, description="Whether user account is active")

@router.post("/login")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate a user and return a JWT access token.
    
    - **email**: User's email address
    - **password**: User's password
    """
    import logging
    logger = logging.getLogger("uvicorn.error")
    logger.info(f"Login attempt for {data.email}")
    try:
        repo = UserRepository(db)
        user = await repo.get_by_email(data.email)
        
        if not user or not verify_password(data.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        token = create_access_token({"sub": str(user.id), "email": user.email})
        refresh = create_refresh_token({"sub": str(user.id), "email": user.email})

        return {
            "token": token,
            "refresh_token": refresh,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/register")
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Register a new user account.
    
    - **name**: Full name
    - **email**: valid email address
    - **password**: Secure password
    """
    try:
        repo = UserRepository(db)
        # Check if user exists
        existing = await repo.get_by_email(data.email)
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")

        password_hash = get_password_hash(data.password)
        new_user = await repo.create(
            email=data.email, 
            password_hash=password_hash, 
            name=data.name
        )
        await db.commit()
        await db.refresh(new_user)  # Ensure user data is loaded after commit

        token = create_access_token({"sub": str(new_user.id), "email": new_user.email})
        refresh = create_refresh_token({"sub": str(new_user.id), "email": new_user.email})

        return {
            "token": token,
            "refresh_token": refresh,
            "user": {
                "id": str(new_user.id),
                "email": new_user.email,
                "name": new_user.name,
                "role": new_user.role
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me")
async def get_current_user_info(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get information about the currently authenticated user.
    """
    from app.models import User

    result = await db.execute(select(User).where(User.id == current_user["id"]))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None
        }
    }


@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """
    List all users (admin only).
    """
    from app.models import User
    from sqlalchemy import select

    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()

    return {
        "users": [
            {
                "id": str(u.id),
                "email": u.email,
                "name": u.name,
                "role": u.role,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None
            }
            for u in users
        ]
    }


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    data: UpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """
    Update a user's role or status (admin only).
    """
    import uuid
    from app.models import User
    from sqlalchemy import select

    try:
        target_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    result = await db.execute(select(User).where(User.id == target_uuid))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update fields if provided
    if data.name is not None:
        user.name = data.name
    if data.role is not None:
        user.role = data.role.value
    if data.is_active is not None:
        user.is_active = data.is_active

    await db.commit()

    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "is_active": user.is_active
        }
    }


@router.post("/refresh")
async def refresh_token(
    refresh_token: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh an access token using a refresh token.
    """
    from app.auth import decode_token, create_access_token
    import uuid

    # Decode refresh token
    payload = decode_token(refresh_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Verify it's a refresh token
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Verify user still exists and is active
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid user ID in token")

    from app.models import User
    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=401, detail="User account is disabled")

    # Generate new access token
    access_token = create_access_token({"sub": str(user.id), "email": user.email})

    return {
        "token": access_token,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "role": user.role
        }
    }
