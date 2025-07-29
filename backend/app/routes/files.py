from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
from sqlalchemy import select, and_

from app.db.database import get_db
from app.db.models import User
from app.routes.auth import get_current_user
from app.schemas.code import CodeFileCreate, CodeFileUpdate, CodeFileResponse
from app.services.file_system import file_system_service
from app.utils.logger import setup_logger
from app.db.models import CodeSession

logger = setup_logger(__name__)
router = APIRouter(prefix="/files", tags=["files"])


@router.post("/", response_model=CodeFileResponse)
async def create_file(
    session_id: int,
    file_data: CodeFileCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new file in a session"""

    try:
        file = await file_system_service.create_file(db, session_id, file_data, current_user.id)
        return file
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating file: {e}")
        raise HTTPException(status_code=500, detail="Failed to create file")


@router.get("/{file_id}", response_model=CodeFileResponse)
async def get_file(
    file_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Get a file by ID"""

    try:
        file = await file_system_service.get_file(db, file_id, current_user.id)
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
        return file
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file: {e}")
        raise HTTPException(status_code=500, detail="Failed to get file")


@router.get("/session/{session_id}", response_model=List[CodeFileResponse])
async def get_session_files(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all files in a session"""

    try:
        files = await file_system_service.get_files_by_session(db, session_id, current_user.id)
        return files
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting session files: {e}")
        raise HTTPException(status_code=500, detail="Failed to get session files")


@router.put("/{file_id}", response_model=CodeFileResponse)
async def update_file(
    file_id: int,
    file_update: CodeFileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a file"""

    try:
        file = await file_system_service.update_file(db, file_id, file_update, current_user.id)
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
        return file
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating file: {e}")
        raise HTTPException(status_code=500, detail="Failed to update file")


@router.delete("/{file_id}")
async def delete_file(
    file_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Delete a file"""

    try:
        success = await file_system_service.delete_file(db, file_id, current_user.id)
        if not success:
            raise HTTPException(status_code=404, detail="File not found")
        return {"message": "File deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete file")


@router.get("/session/{session_id}/directory")
async def list_directory(
    session_id: int,
    path: str = "",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List contents of a directory in a session"""

    try:
        contents = await file_system_service.list_directory(db, session_id, path, current_user.id)
        return {"path": path, "contents": contents}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing directory: {e}")
        raise HTTPException(status_code=500, detail="Failed to list directory")


@router.post("/session/{session_id}/upload")
async def upload_files(
    session_id: int,
    files: List[CodeFileCreate],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload multiple files to a session"""

    try:
        created_files = []
        for file_data in files:
            try:
                file = await file_system_service.create_file(
                    db, session_id, file_data, current_user.id
                )
                created_files.append(file)
            except ValueError as e:
                # Log error but continue with other files
                logger.warning(f"Failed to upload file {file_data.name}: {e}")
                continue

        return {
            "message": f"Successfully uploaded {len(created_files)} files",
            "files": created_files,
            "total_attempted": len(files),
            "successful": len(created_files),
            "failed": len(files) - len(created_files),
        }
    except Exception as e:
        logger.error(f"Error uploading files: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload files")


@router.post("/session/{session_id}/cleanup")
async def cleanup_session_files(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Clean up npm log files and other temporary files from a session"""

    try:
        # verifying session belongs to user
        session_result = await db.execute(
            select(CodeSession).where(
                and_(CodeSession.id == session_id, CodeSession.user_id == current_user.id)
            )
        )
        session = session_result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found or access denied")

        # getting workspace path
        workspace_path = file_system_service.get_workspace_path(session_id)

        # cleaning up npm files
        await file_system_service.cleanup_npm_files(workspace_path)

        # resyncing workspace to DB to ensure clean state
        await file_system_service.sync_workspace_to_db(db, session_id, current_user.id)

        # getting updated files
        files = await file_system_service.get_files_by_session(db, session_id, current_user.id)

        return {
            "message": "Session files cleaned up successfully",
            "session_id": session_id,
            "file_count": len(files),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cleaning up session files: {e}")
        raise HTTPException(status_code=500, detail="Failed to clean up session files")


@router.get("/session/{session_id}/export")
async def export_session_files(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export all files in a session as a structured response"""

    try:
        files = await file_system_service.get_files_by_session(db, session_id, current_user.id)

        # grouping files by directory
        file_tree = {}
        for file in files:
            path_parts = file.path.split("/")
            current_level = file_tree

            # directory structure
            for i, part in enumerate(path_parts[:-1]):
                if part not in current_level:
                    current_level[part] = {}
                current_level = current_level[part]

            # adding file to the structure
            filename = path_parts[-1]
            current_level[filename] = {
                "id": file.id,
                "name": file.name,
                "content": file.content,
                "file_type": file.file_type,
                "size_bytes": file.size_bytes,
                "created_at": file.created_at.isoformat(),
                "updated_at": file.updated_at.isoformat(),
            }

        return {
            "session_id": session_id,
            "file_count": len(files),
            "total_size": sum(f.size_bytes for f in files),
            "file_tree": file_tree,
            "files": [f.model_dump() for f in files],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error exporting session files: {e}")
        raise HTTPException(status_code=500, detail="Failed to export session files")


@router.post("/session/{session_id}/duplicate")
async def duplicate_file(
    session_id: int,
    file_id: int,
    new_name: str,
    new_path: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Duplicate a file within the same session"""

    try:
        # getting original file
        original_file = await file_system_service.get_file(db, file_id, current_user.id)
        if not original_file:
            raise HTTPException(status_code=404, detail="Original file not found")

        # creating new file with duplicated content
        new_file_data = CodeFileCreate(
            name=new_name,
            path=new_path,
            content=original_file.content,
            file_type=original_file.file_type,
        )

        new_file = await file_system_service.create_file(
            db, session_id, new_file_data, current_user.id
        )
        return new_file

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error duplicating file: {e}")
        raise HTTPException(status_code=500, detail="Failed to duplicate file")


@router.get("/session/{session_id}/search")
async def search_files(
    session_id: int,
    query: str,
    search_content: bool = True,
    search_names: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search files in a session by name or content"""

    try:
        files = await file_system_service.get_files_by_session(db, session_id, current_user.id)

        matching_files = []
        query_lower = query.lower()

        for file in files:
            matches = False
            match_reasons = []

            # searching in file names
            if search_names and query_lower in file.name.lower():
                matches = True
                match_reasons.append("filename")

            # searching in file content
            if search_content and query_lower in file.content.lower():
                matches = True
                match_reasons.append("content")

                # finding matching lines
                matching_lines = []
                for i, line in enumerate(file.content.split("\n"), 1):
                    if query_lower in line.lower():
                        matching_lines.append({"line_number": i, "content": line.strip()})

                if matching_lines:
                    file_dict = file.model_dump()
                    file_dict["matching_lines"] = matching_lines[:5]  # limiting to first 5 matches
                    matching_files.append({"file": file_dict, "match_reasons": match_reasons})
            elif matches:
                matching_files.append({"file": file.model_dump(), "match_reasons": match_reasons})

        return {
            "query": query,
            "session_id": session_id,
            "total_files_searched": len(files),
            "matching_files_count": len(matching_files),
            "matches": matching_files,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error searching files: {e}")
        raise HTTPException(status_code=500, detail="Failed to search files")
