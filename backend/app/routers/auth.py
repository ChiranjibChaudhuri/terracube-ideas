from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from app.db import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.user_repo import UserRepository
from app.auth import verify_password, get_password_hash, create_access_token
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str

@router.post("/login")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    import logging
    logger = logging.getLogger("uvicorn.error")
    logger.info(f"Login attempt for {data.email}")
    try:
        repo = UserRepository(db)
        user = await repo.get_by_email(data.email)
        
        if not user or not verify_password(data.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        token = create_access_token({"sub": str(user.id), "email": user.email})
        
        return {
            "token": token,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name
            }
        }
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/register")
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
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
        
        token = create_access_token({"sub": str(new_user.id), "email": new_user.email})
        
        return {
            "token": token,
            "user": {
                "id": str(new_user.id),
                "email": new_user.email,
                "name": new_user.name
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
