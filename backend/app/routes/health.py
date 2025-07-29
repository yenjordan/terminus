from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.database import get_db
import traceback

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return {"status": "healthy"}


@router.get("/health/db")
async def database_health_check(db: AsyncSession = Depends(get_db)):
    """Check database connectivity"""
    try:
        # Try to execute a simple query
        result = await db.execute(text("SELECT 1"))
        if result.scalar() == 1:
            return {"status": "database connected", "result": "success"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database query returned unexpected result",
            )
    except Exception as e:
        error_detail = f"Database connection error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail,
        )
