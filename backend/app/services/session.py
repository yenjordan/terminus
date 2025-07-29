from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from app.db.models import CodeSession, User, CodeFile
from app.schemas.code import CodeSessionCreate, CodeSessionUpdate, CodeSessionResponse
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class SessionService:
    """Service for managing user code sessions"""

    def __init__(self):
        self.max_sessions_per_user = 50

    async def create_session(
        self, db: AsyncSession, session_data: CodeSessionCreate, user_id: int
    ) -> CodeSessionResponse:
        """Create a new code session for the user"""

        # checking session count limit
        session_count_result = await db.execute(
            select(CodeSession).where(CodeSession.user_id == user_id)
        )
        session_count = len(session_count_result.scalars().all())
        if session_count >= self.max_sessions_per_user:
            raise ValueError(f"Maximum {self.max_sessions_per_user} sessions per user")

        # creating session
        db_session = CodeSession(
            name=session_data.name, description=session_data.description, user_id=user_id
        )

        db.add(db_session)
        await db.commit()
        await db.refresh(db_session)

        logger.info(f"Created session '{session_data.name}' for user {user_id}")
        return CodeSessionResponse.model_validate(db_session)

    async def get_session(
        self, db: AsyncSession, session_id: int, user_id: int
    ) -> Optional[CodeSessionResponse]:
        """Get a session by ID, ensuring user has access"""

        result = await db.execute(
            select(CodeSession).where(
                and_(CodeSession.id == session_id, CodeSession.user_id == user_id)
            )
        )
        session = result.scalar_one_or_none()

        if session:
            # updating last accessed time
            await self.update_last_accessed(db, session_id, user_id)

        return CodeSessionResponse.model_validate(session) if session else None

    async def get_user_sessions(
        self, db: AsyncSession, user_id: int, active_only: bool = False
    ) -> List[CodeSessionResponse]:
        """Get all sessions for a user"""

        query = select(CodeSession).where(CodeSession.user_id == user_id)

        if active_only:
            query = query.where(CodeSession.is_active == True)

        query = query.order_by(desc(CodeSession.last_accessed))

        result = await db.execute(query)
        sessions = result.scalars().all()

        return [CodeSessionResponse.model_validate(session) for session in sessions]

    async def update_session(
        self, db: AsyncSession, session_id: int, session_update: CodeSessionUpdate, user_id: int
    ) -> Optional[CodeSessionResponse]:
        """Update an existing session"""

        result = await db.execute(
            select(CodeSession).where(
                and_(CodeSession.id == session_id, CodeSession.user_id == user_id)
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            return None

        # updating fields
        update_data = session_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(session, field, value)

        await db.commit()
        await db.refresh(session)

        logger.info(f"Updated session {session_id}")
        return CodeSessionResponse.model_validate(session)

    async def delete_session(self, db: AsyncSession, session_id: int, user_id: int) -> bool:
        """Delete a session and all its files"""

        result = await db.execute(
            select(CodeSession).where(
                and_(CodeSession.id == session_id, CodeSession.user_id == user_id)
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            return False

        # deleting session (cascade will handle files)
        await db.delete(session)
        await db.commit()

        logger.info(f"Deleted session {session_id}")
        return True

    async def update_last_accessed(self, db: AsyncSession, session_id: int, user_id: int) -> None:
        """Update the last accessed time for a session"""

        result = await db.execute(
            select(CodeSession).where(
                and_(CodeSession.id == session_id, CodeSession.user_id == user_id)
            )
        )
        session = result.scalar_one_or_none()
        if session:
            # SQLAlchemy will handle updating last_accessed automatically bc of onupdate
            session.name = session.name  # touch session to trigger update
            await db.commit()

    async def activate_session(self, db: AsyncSession, session_id: int, user_id: int) -> bool:
        """Activate a session"""

        result = await db.execute(
            select(CodeSession).where(
                and_(CodeSession.id == session_id, CodeSession.user_id == user_id)
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            return False

        session.is_active = True
        await db.commit()

        logger.info(f"Activated session {session_id}")
        return True

    async def deactivate_session(self, db: AsyncSession, session_id: int, user_id: int) -> bool:
        """Deactivate a session"""

        result = await db.execute(
            select(CodeSession).where(
                and_(CodeSession.id == session_id, CodeSession.user_id == user_id)
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            return False

        session.is_active = False
        await db.commit()

        logger.info(f"Deactivated session {session_id}")
        return True

    async def get_session_stats(
        self, db: AsyncSession, session_id: int, user_id: int
    ) -> Optional[dict]:
        """Get statistics about a session"""

        # verifying session access
        result = await db.execute(
            select(CodeSession).where(
                and_(CodeSession.id == session_id, CodeSession.user_id == user_id)
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            return None

        # getting file count
        file_count_result = await db.execute(
            select(CodeFile).where(CodeFile.session_id == session_id)
        )
        files = file_count_result.scalars().all()

        total_size = sum(file.size_bytes for file in files)
        file_types = {}
        for file in files:
            file_type = file.file_type
            file_types[file_type] = file_types.get(file_type, 0) + 1

        return {
            "session_id": session_id,
            "name": session.name,
            "file_count": len(files),
            "total_size_bytes": total_size,
            "file_types": file_types,
            "created_at": session.created_at.isoformat(),
            "last_accessed": session.last_accessed.isoformat(),
            "is_active": session.is_active,
        }


# singleton instance
session_service = SessionService()
