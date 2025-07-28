import os
import shutil
import asyncio
import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import datetime
import aiofiles
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import CodeFile, CodeSession
from app.schemas.code import CodeFileCreate, CodeFileUpdate, CodeFileResponse
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class FileSystemService:
    """Service for managing files within user code sessions"""
    
    def __init__(self):
        self.max_file_size = 1024 * 1024  # 1MB per file
        self.max_files_per_session = 100
        self.allowed_extensions = {
            '.py', '.txt', '.md', '.json', '.csv', '.xml', '.html', 
            '.css', '.js', '.yaml', '.yml', '.ini', '.conf', '.sh'
        }

    def _is_binary(self, file_path: str) -> bool:
        """Check if a file is binary"""
        try:
            with open(file_path, 'tr') as check_file:
                check_file.read()
                return False
        except (UnicodeDecodeError, AttributeError):
            return True
            
    def _should_skip_file(self, file_path: str, file_name: str) -> bool:
        """Check if a file should be skipped during sync operations"""
        # skip hidden files and __pycache__
        if file_name.startswith('.') or '__pycache__' in file_path:
            return True
            
        # skip npm log files and other npm-related files
        if any([
            # npm log files
            file_name.endswith('-debug.log'),
            file_name.endswith('-debug-0.log'),
            file_name.startswith('npm-debug'),
            # npm cache and config files
            '.npm-cache' in file_path,
            '.npmrc' in file_path,
            'package-lock.json' in file_path,
            # package files
            file_name == 'package.json',
            # node_modules directory
            'node_modules' in file_path,
            # other npm related files
            file_name == '.npm' or file_path.endswith('/.npm'),
            # skip any file that has 'npm' in the path and is a log file
            ('npm' in file_path.lower() and file_name.endswith('.log'))
        ]):
            return True
            
        return False

    def get_workspace_path(self, session_id: int) -> str:
        """Get the workspace directory path for a session"""
        return f"/tmp/terminus_workspace/session_{session_id}"

    async def sync_workspace_to_db(self, db: AsyncSession, session_id: int, user_id: int):
        """Sync actual workspace files to the database"""
        try:
            workspace_path = self.get_workspace_path(session_id)
            if not os.path.exists(workspace_path):
                return
                
            # cleaning up npm log files before syncing
            await self.cleanup_npm_files(workspace_path)
            
            # getting existing files from database
            existing_files_result = await db.execute(
                select(CodeFile).where(CodeFile.session_id == session_id)
            )
            # normalzing paths in the database by stripping leading slashes
            existing_files = {f.path.lstrip('/'): f for f in existing_files_result.scalars().all()}
            
            # scanning workspace directory
            for root, dirs, files in os.walk(workspace_path):
                # skipping node_modules directory
                if 'node_modules' in dirs:
                    dirs.remove('node_modules')
                
                # skipping .npm directory
                if '.npm' in dirs:
                    dirs.remove('.npm')
                
                # skipping .npm-cache directory
                if '.npm-cache' in dirs:
                    dirs.remove('.npm-cache')
                
                for file_name in files:
                    file_path = os.path.join(root, file_name)
                    relative_path = os.path.relpath(file_path, workspace_path)
                    
                    # skipping files that should be excluded
                    if self._should_skip_file(relative_path, file_name):
                        logger.info(f"Skipping excluded file: {relative_path}")
                        continue
                    
                    # skipping binary files
                    if self._is_binary(file_path):
                        logger.warning(f"Skipping binary file: {relative_path}")
                        continue
                    
                    try:
                        # reading file content
                        async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = await f.read()
                        
                        # Skskippingip files that seem to be npm logs based on content
                        if content and (
                            content.startswith('0 verbose cli') or 
                            'npm ERR!' in content or
                            'timing npm:load:' in content
                        ):
                            logger.info(f"Skipping npm log file based on content: {relative_path}")
                            continue
                        
                        # checking if the file exists in the database (after normalizing paths)
                        if relative_path in existing_files:
                            # Update existing file if content changed
                            existing_file = existing_files[relative_path]
                            if existing_file.content != content:
                                existing_file.content = content
                                existing_file.updated_at = datetime.datetime.utcnow()
                                logger.info(f"Updated file {relative_path} in database")
                        else:
                            # creating new file in database
                            file_type = self._get_file_type(file_name)
                            new_file = CodeFile(
                                session_id=session_id,
                                name=file_name,
                                path=relative_path,
                                content=content,
                                file_type=file_type
                            )
                            db.add(new_file)
                            logger.info(f"Added new file {relative_path} to database")
                    
                    except Exception as e:
                        logger.error(f"Error syncing file {relative_path}: {e}")
            
            await db.commit()
            
        except Exception as e:
            logger.error(f"Error syncing workspace to database: {e}")

    async def cleanup_npm_files(self, workspace_path: str):
        """Clean up npm log files and other npm-related files from the workspace directory"""
        try:
            if not os.path.exists(workspace_path):
                return
                
            # patterns for files to delete
            npm_patterns = [
                '*.log',                  # Log files
                'npm-debug*',             # npm debug logs
                '*-debug.log',            # Debug logs
                '*-debug-*.log',          # Numbered debug logs
                '.npmrc',                 # npm config
                '.npm-cache',             # npm cache directory
                '.npm'                    # npm directory
            ]
            
            # finding and deleting npm log files
            for pattern in npm_patterns:
                for file_path in Path(workspace_path).glob('**/' + pattern):
                    if file_path.is_file():
                        try:
                            file_path.unlink()
                            logger.info(f"Deleted npm file: {file_path.relative_to(workspace_path)}")
                        except Exception as e:
                            logger.error(f"Failed to delete npm file {file_path}: {e}")
            
            # checking for content based npm log files
            for file_path in Path(workspace_path).glob('**/*'):
                if file_path.is_file() and file_path.stat().st_size < 100000:  # Only check reasonably sized files
                    try:
                        # reading first few lines to check if it's an npm log
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            first_lines = ''.join([f.readline() for _ in range(10)])
                            
                        # checking if it looks like an npm log
                        if (first_lines.startswith('0 verbose cli') or 
                            'npm ERR!' in first_lines or 
                            'timing npm:load:' in first_lines):
                            file_path.unlink()
                            logger.info(f"Deleted npm log file by content: {file_path.relative_to(workspace_path)}")
                    except Exception as e:
                        # ignoring errors reading files
                        pass
                        
        except Exception as e:
            logger.error(f"Error cleaning up npm files: {e}")

    async def sync_db_to_workspace(self, db: AsyncSession, session_id: int, user_id: int):
        """Sync database files to the actual workspace"""
        try:
            workspace_path = self.get_workspace_path(session_id)
            os.makedirs(workspace_path, exist_ok=True)
            
            # cleaning up npm log files before syncing
            await self.cleanup_npm_files(workspace_path)
            
            # getting files from database
            files_result = await db.execute(
                select(CodeFile).where(CodeFile.session_id == session_id)
            )
            files = files_result.scalars().all()
            
            # tracking synced files to detect stale files in workspace
            synced_file_paths = []
            db_file_paths = set()
            
            for file in files:
                try:
                    # normalizing path by removing leading slash if present
                    normalized_path = file.path.lstrip('/')
                    db_file_paths.add(normalized_path)
                    file_path = os.path.join(workspace_path, normalized_path)
                    file_dir = os.path.dirname(file_path)
                    
                    # creating directory if it doesn't exist
                    os.makedirs(file_dir, exist_ok=True)
                    
                    # checking if file exists and has different content
                    file_exists = os.path.exists(file_path)
                    content_changed = True
                    
                    if file_exists:
                        try:
                            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                                current_content = await f.read()
                                if current_content == file.content:
                                    content_changed = False
                        except Exception as e:
                            logger.warning(f"Error reading file {file_path}: {e}")
                            # assuming content changed if i can't read it
                            content_changed = True
                    
                    # write if file doesn't exist or content changed
                    if not file_exists or content_changed:
                        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                            await f.write(file.content or '')
                        logger.info(f"Synced file {file.path} to workspace (new/updated)")
                    else:
                        logger.debug(f"File {file.path} already up to date in workspace")
                    
                    # adding to synced files list
                    synced_file_paths.append(normalized_path)
                    
                except Exception as e:
                    logger.error(f"Error syncing file {file.path} to workspace: {e}")
            
            # removing files from workspace that no longer exist in the database and skipping hidden files and directories starting with .
            for root, dirs, files in os.walk(workspace_path):
                # skiping hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for file in files:
                    # skipping hidden files
                    if file.startswith('.'):
                        continue
                        
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, workspace_path)
                    
                    # if file exists in workspace but not in database then deleted
                    if relative_path not in db_file_paths:
                        try:
                            os.remove(file_path)
                            logger.info(f"Removed stale file from workspace: {relative_path}")
                        except Exception as e:
                            logger.error(f"Error removing stale file {relative_path}: {e}")
            
            # special file for debugging
            debug_info_path = os.path.join(workspace_path, '.sync_info.json')
            try:
                import json
                debug_info = {
                    'last_sync': str(datetime.datetime.now()),
                    'session_id': session_id,
                    'user_id': user_id,
                    'synced_files': synced_file_paths,
                    'db_files': list(db_file_paths)
                }
                async with aiofiles.open(debug_info_path, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(debug_info, indent=2))
            except Exception as e:
                logger.error(f"Error writing sync info file: {e}")
            
            logger.info(f"Successfully synced {len(synced_file_paths)} files to workspace for session {session_id}")
            
        except Exception as e:
            logger.error(f"Error syncing database to workspace: {e}")
            # re-raise to allow caller to handle
            raise

    def _get_file_type(self, filename: str) -> str:
        """Determine file type based on extension"""
        extension = Path(filename).suffix.lower()
        
        if extension == '.py':
            return 'python'
        elif extension in ['.js', '.jsx']:
            return 'javascript'
        elif extension in ['.ts', '.tsx']:
            return 'typescript'
        elif extension in ['.html', '.htm']:
            return 'html'
        elif extension == '.css':
            return 'css'
        elif extension in ['.json']:
            return 'json'
        elif extension in ['.md', '.markdown']:
            return 'markdown'
        elif extension in ['.yaml', '.yml']:
            return 'yaml'
        elif extension in ['.xml']:
            return 'xml'
        elif extension in ['.sh', '.bash']:
            return 'shell'
        else:
            return 'text'

    async def create_file(
        self, 
        db: AsyncSession, 
        session_id: int, 
        file_data: CodeFileCreate,
        user_id: int
    ) -> CodeFileResponse:
        """Create a new file in the user's session"""
        
        # verifying session belongs to user
        session_result = await db.execute(
            select(CodeSession).where(
                and_(CodeSession.id == session_id, CodeSession.user_id == user_id)
            )
        )
        session = session_result.scalar_one_or_none()
        if not session:
            raise ValueError("Session not found or access denied")
        
        # validating file
        self._validate_file(file_data.name, file_data.content)
        
        # checking file count limit
        file_count_result = await db.execute(
            select(CodeFile).where(CodeFile.session_id == session_id)
        )
        file_count = len(file_count_result.scalars().all())
        if file_count >= self.max_files_per_session:
            raise ValueError(f"Maximum {self.max_files_per_session} files per session")
        
        # checking if file already exists
        existing_file_result = await db.execute(
            select(CodeFile).where(
                and_(
                    CodeFile.session_id == session_id,
                    CodeFile.path == file_data.path
                )
            )
        )
        if existing_file_result.scalar_one_or_none():
            raise ValueError("File already exists at this path")
        
        # creating file record
        db_file = CodeFile(
            name=file_data.name,
            path=file_data.path,
            content=file_data.content,
            file_type=file_data.file_type,
            session_id=session_id,
            size_bytes=len(file_data.content.encode('utf-8'))
        )
        
        db.add(db_file)
        await db.commit()
        await db.refresh(db_file)
        
        logger.info(f"Created file {file_data.name} in session {session_id}")
        return CodeFileResponse.model_validate(db_file)

    async def get_file(
        self, 
        db: AsyncSession, 
        file_id: int, 
        user_id: int
    ) -> Optional[CodeFileResponse]:
        """Get a file by ID, ensuring user has access"""
        
        result = await db.execute(
            select(CodeFile)
            .join(CodeSession)
            .where(
                and_(
                    CodeFile.id == file_id,
                    CodeSession.user_id == user_id
                )
            )
        )
        file = result.scalar_one_or_none()
        return CodeFileResponse.model_validate(file) if file else None

    async def get_files_by_session(
        self, 
        db: AsyncSession, 
        session_id: int, 
        user_id: int
    ) -> List[CodeFileResponse]:
        """Get all files in a session"""
        
        # verifying session access
        session_result = await db.execute(
            select(CodeSession).where(
                and_(CodeSession.id == session_id, CodeSession.user_id == user_id)
            )
        )
        if not session_result.scalar_one_or_none():
            raise ValueError("Session not found or access denied")
        
        # getting files
        files_result = await db.execute(
            select(CodeFile)
            .where(CodeFile.session_id == session_id)
            .order_by(CodeFile.path)
        )
        files = files_result.scalars().all()
        
        return [CodeFileResponse.model_validate(file) for file in files]

    async def update_file(
        self, 
        db: AsyncSession, 
        file_id: int, 
        file_update: CodeFileUpdate,
        user_id: int
    ) -> Optional[CodeFileResponse]:
        """Update an existing file"""
        
        # getting file with session check
        result = await db.execute(
            select(CodeFile)
            .join(CodeSession)
            .where(
                and_(
                    CodeFile.id == file_id,
                    CodeSession.user_id == user_id
                )
            )
        )
        file = result.scalar_one_or_none()
        if not file:
            return None
        
        # update fields
        update_data = file_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == 'content' and value is not None:
                self._validate_file(file.name, value)
                setattr(file, field, value)
                file.size_bytes = len(value.encode('utf-8'))
            elif value is not None:
                setattr(file, field, value)
        
        await db.commit()
        await db.refresh(file)
        
        logger.info(f"Updated file {file.name} (ID: {file_id})")
        return CodeFileResponse.model_validate(file)

    async def delete_file(
        self, 
        db: AsyncSession, 
        file_id: int, 
        user_id: int
    ) -> bool:
        """Delete a file"""
        
        # getting file with session check
        result = await db.execute(
            select(CodeFile)
            .join(CodeSession)
            .where(
                and_(
                    CodeFile.id == file_id,
                    CodeSession.user_id == user_id
                )
            )
        )
        file = result.scalar_one_or_none()
        if not file:
            return False
        
        # getting file information before deletion
        session_id = file.session_id
        file_path = file.path
        file_name = file.name
        
        # deleting from database
        await db.delete(file)
        await db.commit()
        
        # also deleting from workspace filesystem
        try:
            workspace_path = self.get_workspace_path(session_id)
            normalized_path = file_path.lstrip('/')
            full_file_path = os.path.join(workspace_path, normalized_path)
            
            if os.path.exists(full_file_path):
                os.remove(full_file_path)
                logger.info(f"Deleted file from workspace: {normalized_path}")
                
                # cleaning up empty directories
                dir_path = os.path.dirname(full_file_path)
                while dir_path != workspace_path:
                    if os.path.exists(dir_path) and not os.listdir(dir_path):
                        os.rmdir(dir_path)
                        logger.info(f"Removed empty directory: {os.path.relpath(dir_path, workspace_path)}")
                        dir_path = os.path.dirname(dir_path)
                    else:
                        break
        except Exception as e:
            logger.error(f"Error deleting file from workspace: {e}")
            # continuing even if filesystem deletion fails
        
        logger.info(f"Deleted file {file_name} (ID: {file_id})")
        return True

    async def get_session_files_as_dict(
        self, 
        db: AsyncSession, 
        session_id: int, 
        user_id: int
    ) -> Dict[str, str]:
        """Get all files in a session as a dictionary for execution"""
        
        files = await self.get_files_by_session(db, session_id, user_id)
        return {file.path: file.content for file in files}

    async def list_directory(
        self, 
        db: AsyncSession, 
        session_id: int, 
        directory_path: str,
        user_id: int
    ) -> List[Dict[str, Any]]:
        """List files and directories in a session path"""
        
        # verifying session access
        session_result = await db.execute(
            select(CodeSession).where(
                and_(CodeSession.id == session_id, CodeSession.user_id == user_id)
            )
        )
        if not session_result.scalar_one_or_none():
            raise ValueError("Session not found or access denied")
        
        # normalizing directory path
        if directory_path == "/":
            directory_path = ""
        elif directory_path.startswith("/"):
            directory_path = directory_path[1:]
        
        # getting all files in session
        files_result = await db.execute(
            select(CodeFile).where(CodeFile.session_id == session_id)
        )
        files = files_result.scalars().all()
        
        # filtering files in the requested directory
        directory_contents = []
        subdirectories = set()
        
        for file in files:
            file_path = file.path
            if file_path.startswith("/"):
                file_path = file_path[1:]
            
            # checking if file is in the requested directory
            if directory_path == "":
                # root directory
                if "/" not in file_path:
                    # file in root
                    directory_contents.append({
                        "name": file.name,
                        "path": file.path,
                        "type": "file",
                        "size": file.size_bytes,
                        "modified": file.updated_at.isoformat()
                    })
                else:
                    # file in subdirectory, add subdirectory
                    subdir = file_path.split("/")[0]
                    subdirectories.add(subdir)
            else:
                if file_path.startswith(directory_path + "/"):
                    relative_path = file_path[len(directory_path) + 1:]
                    if "/" not in relative_path:
                        # direct file in directory
                        directory_contents.append({
                            "name": file.name,
                            "path": file.path,
                            "type": "file",
                            "size": file.size_bytes,
                            "modified": file.updated_at.isoformat()
                        })
                    else:
                        # file in subdirectory
                        subdir = relative_path.split("/")[0]
                        subdirectories.add(subdir)
        
        # adding subdirectories
        for subdir in subdirectories:
            directory_contents.append({
                "name": subdir,
                "path": f"{directory_path}/{subdir}" if directory_path else subdir,
                "type": "directory",
                "size": 0,
                "modified": None
            })
        
        return sorted(directory_contents, key=lambda x: (x["type"] == "file", x["name"]))

    async def get_file_by_path(
        self, 
        db: AsyncSession, 
        session_id: int, 
        user_id: int, 
        file_path: str
    ) -> Optional[CodeFile]:
        """Get a file by its path within a session"""
        
        result = await db.execute(
            select(CodeFile)
            .join(CodeSession)
            .where(
                and_(
                    CodeFile.path == file_path,
                    CodeFile.session_id == session_id,
                    CodeSession.user_id == user_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def update_file_content(
        self, 
        db: AsyncSession, 
        file_id: int, 
        user_id: int, 
        content: str
    ) -> Optional[CodeFileResponse]:
        """Update file content, ensuring user has access"""
        
        # verifying the user has access to this file
        result = await db.execute(
            select(CodeFile)
            .join(CodeSession)
            .where(
                and_(
                    CodeFile.id == file_id,
                    CodeSession.user_id == user_id
                )
            )
        )
        
        db_file = result.scalar_one_or_none()
        if not db_file:
            return None
        
        # updating the content and size
        db_file.content = content
        db_file.size_bytes = len(content.encode('utf-8'))
        db_file.updated_at = datetime.datetime.utcnow()
        
        await db.commit()
        await db.refresh(db_file)
        
        logger.info(f"Updated file {db_file.name} (ID: {file_id})")
        return CodeFileResponse.model_validate(db_file)

    def _validate_file(self, filename: str, content: str) -> None:
        """Validate file name and content"""
        
        # checking file size
        if len(content.encode('utf-8')) > self.max_file_size:
            raise ValueError(f"File size exceeds {self.max_file_size} bytes")
        
        # checking file extension
        file_ext = Path(filename).suffix.lower()
        if file_ext and file_ext not in self.allowed_extensions:
            raise ValueError(f"File extension '{file_ext}' not allowed")
        
        # checking for dangerous content
        dangerous_patterns = [
            "import os", "import subprocess", "import sys",
            "__import__", "eval(", "exec(", "compile("
        ]
        
        content_lower = content.lower()
        for pattern in dangerous_patterns:
            if pattern in content_lower:
                logger.warning(f"Potentially dangerous content detected in file: {pattern}")
                # i log but don't block, could be legit educational content


# Singleton instance
file_system_service = FileSystemService() 