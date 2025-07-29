from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.db.database import get_db
from app.db.models import User
from app.routes.auth import get_current_user
from app.schemas.code import CodeSessionCreate, CodeSessionUpdate, CodeSessionResponse
from app.services.session import session_service
from app.utils.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/", response_model=CodeSessionResponse)
async def create_session(
    session_data: CodeSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new code session"""

    try:
        session = await session_service.create_session(db, session_data, current_user.id)
        return session
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create session")


@router.get("/", response_model=List[CodeSessionResponse])
async def get_user_sessions(
    active_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all sessions for the current user"""

    try:
        sessions = await session_service.get_user_sessions(db, current_user.id, active_only)
        return sessions
    except Exception as e:
        logger.error(f"Error getting user sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get sessions")


@router.get("/{session_id}", response_model=CodeSessionResponse)
async def get_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific session by ID"""

    try:
        session = await session_service.get_session(db, session_id, current_user.id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session: {e}")
        raise HTTPException(status_code=500, detail="Failed to get session")


@router.put("/{session_id}", response_model=CodeSessionResponse)
async def update_session(
    session_id: int,
    session_update: CodeSessionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a session"""

    try:
        session = await session_service.update_session(
            db, session_id, session_update, current_user.id
        )
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating session: {e}")
        raise HTTPException(status_code=500, detail="Failed to update session")


@router.delete("/{session_id}")
async def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a session and all its files"""

    try:
        success = await session_service.delete_session(db, session_id, current_user.id)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"message": "Session deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete session")


@router.post("/{session_id}/activate")
async def activate_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Activate a session"""

    try:
        success = await session_service.activate_session(db, session_id, current_user.id)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"message": "Session activated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating session: {e}")
        raise HTTPException(status_code=500, detail="Failed to activate session")


@router.post("/{session_id}/deactivate")
async def deactivate_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate a session"""

    try:
        success = await session_service.deactivate_session(db, session_id, current_user.id)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"message": "Session deactivated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating session: {e}")
        raise HTTPException(status_code=500, detail="Failed to deactivate session")


@router.get("/{session_id}/stats")
async def get_session_stats(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get statistics for a session"""

    try:
        stats = await session_service.get_session_stats(db, session_id, current_user.id)
        if not stats:
            raise HTTPException(status_code=404, detail="Session not found")
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get session statistics")
