from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.db.database import get_db
from app.db.models import User, CodeSession, CodeSubmission, CodeReview, CodeFile
from app.schemas.auth import (
    Token,
    TokenData,
    UserCreate,
    UserResponse,
    LoginRequest,
    DeleteAccountRequest,
)
from app.services.auth import create_access_token
from app.config import get_settings
from pydantic import EmailStr
import traceback
import json
from fastapi.responses import JSONResponse

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).filter(User.email == token_data.email))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        # logging request data for debugging
        request_info = {
            "path": request.url.path,
            "method": request.method,
            "client": request.client.host if request.client else "unknown",
        }
        print(f"Processing registration request: {json.dumps(request_info)}")
        print(f"User data: {user_data.email}, {user_data.username}, role: {user_data.role}")

        # checking if user exists
        result = await db.execute(select(User).filter(User.email == user_data.email))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
            )

        result = await db.execute(select(User).filter(User.username == user_data.username))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken"
            )

        # creating new user
        user = User(
            email=user_data.email,
            username=user_data.username,
            role=user_data.role,  # setting the role from request
        )
        user.set_password(user_data.password)

        db.add(user)
        await db.commit()
        await db.refresh(user)

        print(f"User created successfully: {user.id}, {user.email}")
        return user

    except HTTPException as he:
        # re-raising HTTP exceptions as they are already properly formatted
        print(f"HTTP Exception during registration: {he.detail}")
        raise
    except Exception as e:
        # catching and logging any other exceptions
        error_detail = f"Registration error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": error_detail}
        )


@router.post("/login", response_model=Token)
async def login(login_data: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(User).filter(User.email == login_data.email))
        user = result.scalar_one_or_none()

        if not user or not user.verify_password(login_data.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token = create_access_token(data={"sub": user.email})
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        error_detail = f"Login error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": error_detail}
        )


@router.post("/delete-account")
async def delete_account(request_data: DeleteAccountRequest, db: AsyncSession = Depends(get_db)):
    """Delete a user account and all associated data"""
    try:
        # verifying credentials
        result = await db.execute(select(User).filter(User.email == request_data.email))
        user = result.scalar_one_or_none()

        if not user or not user.verify_password(request_data.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id = user.id
        print(f"Deleting account for user: {user.email} (ID: {user_id})")

        # deleting associated data in the correct order to respect foreign key constraints

        # 1. delete code reviews made by the user
        await db.execute(delete(CodeReview).where(CodeReview.reviewer_id == user_id))

        # 2. delete code submissions and their associated reviews
        # get all submission IDs
        result = await db.execute(
            select(CodeSubmission.id).where(CodeSubmission.user_id == user_id)
        )
        submission_ids = [row[0] for row in result.fetchall()]

        # dekete reviews of user's submissions
        if submission_ids:
            await db.execute(delete(CodeReview).where(CodeReview.submission_id.in_(submission_ids)))

        # delete the submissions
        await db.execute(delete(CodeSubmission).where(CodeSubmission.user_id == user_id))

        # 3. delete code files in user's sessions
        # get all session IDs
        result = await db.execute(select(CodeSession.id).where(CodeSession.user_id == user_id))
        session_ids = [row[0] for row in result.fetchall()]

        # delete files in those sessions
        if session_ids:
            await db.execute(delete(CodeFile).where(CodeFile.session_id.in_(session_ids)))

        # 4. delete code sessions
        await db.execute(delete(CodeSession).where(CodeSession.user_id == user_id))

        # 5. delete the user
        await db.execute(delete(User).where(User.id == user_id))

        # commit all changes
        await db.commit()

        return {"message": "Account and all associated data deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        # rollback in case of error
        await db.rollback()
        error_detail = f"Account deletion error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": error_detail}
        )


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/request-password-reset")
async def request_password_reset(email: EmailStr, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.email == email))
    user = result.scalar_one_or_none()
    if user:
        user.generate_reset_token()
        await db.commit()
        return {
            "message": "If an account exists with this email, a password reset link will be sent"
        }
    return {"message": "If an account exists with this email, a password reset link will be sent"}


@router.post("/reset-password")
async def reset_password(token: str, new_password: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.reset_token == token))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token"
        )

    user.set_password(new_password)
    user.clear_reset_token()
    await db.commit()

    return {"message": "Password has been reset successfully"}
