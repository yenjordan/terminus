from datetime import datetime, timedelta
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import get_settings
from app.db.models import User

settings = get_settings()


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_current_user_from_token(token: str, db: AsyncSession) -> User | None:
    """Get user from JWT token - standalone function"""
    try:
        # Decode the token
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        
        if email is None:
            return None
            
        # Get user from database
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        return user
        
    except JWTError:
        return None
    except Exception:
        return None


class AuthService:
    """Authentication service for user management"""
    
    async def get_current_user_from_token(self, token: str, db: AsyncSession) -> User | None:
        """Get user from JWT token"""
        try:
            # Decode the token
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            email: str = payload.get("sub")
            
            if email is None:
                return None
                
            # Get user from database
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            
            return user
            
        except JWTError:
            return None
        except Exception:
            return None


# Create service instance
auth_service = AuthService()
