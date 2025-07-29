from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Any, Optional
import json
import asyncio
import time
import os

from app.db import models
from app.db.database import get_db
from app.db.models import User, CodeExecution
from app.routes.auth import get_current_user
from app.services.auth import get_current_user_from_token
from app.schemas.code import (
    TerminalCommand,
    TerminalResponse,
    FileSystemOperation,
    FileSystemResponse,
    CodeExecutionCreate,
    CodeExecutionResponse,
)
from app.services.code_execution import code_execution_service
from app.services.file_system import file_system_service
from app.services.session import session_service
from app.services.shell_session import shell_manager
from app.utils.logger import setup_logger
from sqlalchemy import select
from fastapi.websockets import WebSocketState
import re
from app.schemas.code import CodeExecutionRequest

logger = setup_logger(__name__)
router = APIRouter(prefix="/terminal", tags=["terminal"])

# active WebSocket connections per user
active_connections: Dict[int, WebSocket] = {}


class ConnectionManager:
    """Manages WebSocket connections for real-time terminal communication"""

    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        # don't't call accept() here since we already accepted the connection
        self.active_connections[user_id] = websocket
        logger.info(f"WebSocket connected for user {user_id}")

    async def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"WebSocket disconnected for user {user_id}")

    async def send_personal_message(self, message: dict, user_id: int):
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message to user {user_id}: {e}")
                await self.disconnect(user_id)
                raise


manager = ConnectionManager()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket, session_id: int, db: AsyncSession = Depends(get_db)
):
    """WebSocket endpoint for real-time terminal communication"""

    user = None
    shell_session_id = None

    try:
        # accepting the connection first to avoid browser timeouts
        await websocket.accept()
        logger.info(f"WebSocket connection accepted for session {session_id}")

        # extracting token from query parameters
        query_params = dict(websocket.query_params)
        token = query_params.get("token")

        # authing user from token
        if not token:
            logger.error("No token provided in WebSocket connection")
            await websocket.send_json({"type": "error", "message": "Authentication required"})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        try:
            user = await get_current_user_from_token(token, db)
            if not user:
                logger.error("User not found from token")
                await websocket.send_json({"type": "error", "message": "Invalid authentication"})
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            await websocket.send_json({"type": "error", "message": "Authentication failed"})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        logger.info(f"User {user.id} authenticated for WebSocket")

        # verifying session access
        session = await session_service.get_session(db, session_id, user.id)
        if not session:
            logger.error(f"Session {session_id} not found or access denied for user {user.id}")
            await websocket.send_json(
                {"type": "error", "message": "Session not found or access denied"}
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        logger.info(f"Session {session_id} verified for user {user.id}")

        # sycning database files to workspace before starting shell
        try:
            await file_system_service.sync_db_to_workspace(db, session_id, user.id)
            logger.info(f"Files synced to workspace for session {session_id}")
        except Exception as e:
            logger.error(f"Error syncing files to workspace: {e}")

        # initializing workspace with session files
        files = await file_system_service.get_session_files_as_dict(db, session_id, user.id)

        # adding to connection manager
        await manager.connect(websocket, user.id)
        logger.info(f"WebSocket connected for user {user.id}")

        # creating shell output callback
        async def shell_output_callback(output: str):
            """Callback to send shell output to WebSocket"""
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json({"type": "shell_output", "data": output})
            except Exception as e:
                logger.error(f"Error sending shell output via callback: {e}")
                # don't't raise the exception to avoid breaking the shell session

        # creating or get shell session
        try:
            logger.info(f"Starting shell session creation for user {user.id}")
            # creating a new shell session if needed
            if not shell_session_id:
                logger.info(f"Creating new shell session for user {user.id}")
                shell_session_id = await shell_manager.create_session(
                    session_id=session_id,
                    user_id=user.id,
                    username=user.username,  # Pass the username
                    output_callback=shell_output_callback,
                )

            if not shell_session_id:
                logger.error(
                    f"Failed to create shell session for user {user.id} - session may be in use by another user"
                )
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "This IDE session is currently in use by another user. Please reload the page or try again later.",
                    }
                )
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
                return

            logger.info(f"Shell session {shell_session_id} created for user {user.id}")
        except Exception as e:
            logger.error(f"Error creating shell session: {e}")
            await websocket.send_json(
                {"type": "error", "message": "Failed to create shell session"}
            )
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            return

        # send welcome message directly via WebSocket instead of through manager
        try:
            logger.info(f"Sending welcome message for session {session_id}")
            # no welcome message sent anymore
            logger.info(f"No welcome message sent for session {session_id}")
        except Exception as e:
            logger.error(f"Error sending welcome message: {e}")
            # continue with the message loop even if welcome message fails

        # syncing workspace files to database periodically
        last_sync = time.time()
        sync_interval = 10  # seconds

        logger.info(f"Entering message loop for user {user.id}")

        # main message handling loop
        while True:
            try:
                # checking if we need to sync files
                current_time = time.time()
                if current_time - last_sync > sync_interval:
                    try:
                        await file_system_service.sync_workspace_to_db(db, session_id, user.id)
                        last_sync = current_time
                    except Exception as e:
                        logger.error(f"Error syncing workspace files: {e}")
                        # try to rollback the session if there was an error
                        try:
                            await db.rollback()
                        except Exception as rollback_error:
                            logger.error(f"Error rolling back database session: {rollback_error}")

                # wait for message from client
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                    message = json.loads(data)

                    command_type = message.get("type")
                    logger.debug(f"Received WebSocket message: {command_type}")

                    if command_type == "shell_input":
                        # handling shell input
                        input_data = message.get("data", "")
                        success = await shell_manager.write_to_session(user.id, input_data)
                        if not success:
                            logger.warning(f"Failed to write to shell session for user {user.id}")

                    elif command_type == "shell_resize":
                        # handling terminal resize
                        cols = message.get("cols", 80)
                        rows = message.get("rows", 24)
                        success = await shell_manager.resize_session(user.id, cols, rows)
                        if not success:
                            logger.warning(f"Failed to resize shell session for user {user.id}")

                    elif command_type == "ping":
                        # responding to ping
                        await websocket.send_json(
                            {"type": "pong", "timestamp": message.get("timestamp")}
                        )

                    elif command_type == "execute_code":
                        await handle_code_execution(message, session_id, user.id, db)
                    elif command_type == "terminal_command":
                        await handle_terminal_command(message, session_id, user.id, db)
                    elif command_type == "file_operation":
                        await handle_file_operation(message, session_id, user.id, db)
                    elif command_type == "file_change":
                        # immediately sync files when a file is created or modified
                        try:
                            logger.info(
                                f"File change detected, syncing to workspace for session {session_id}"
                            )
                            # first sync the database to the workspace
                            await file_system_service.sync_db_to_workspace(db, session_id, user.id)

                            # sending a confirmation message to the client
                            await websocket.send_json(
                                {
                                    "type": "file_sync_complete",
                                    "message": "Files synced to workspace successfully",
                                }
                            )

                            logger.info(
                                f"Files synced to workspace after change for session {session_id}"
                            )

                            # refreshing the workspace path to ensure it's up to date
                            workspace_path = file_system_service.get_workspace_path(session_id)
                            logger.info(f"Workspace path: {workspace_path}")

                            # listing files in workspace for debugging
                            if os.path.exists(workspace_path):
                                files_in_workspace = os.listdir(workspace_path)
                                logger.info(f"Files in workspace: {files_in_workspace}")
                        except Exception as e:
                            logger.error(f"Error syncing files after change: {e}")
                            await websocket.send_json(
                                {"type": "error", "message": f"Failed to sync files: {str(e)}"}
                            )
                    else:
                        logger.warning(f"Unknown command type: {command_type}")

                except asyncio.TimeoutError:
                    # timeout is normal, just continue the loop
                    continue
                except WebSocketDisconnect:
                    logger.info(f"WebSocket disconnected for user {user.id}")
                    break
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in WebSocket message: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing WebSocket message: {e}")
                    # don't break the loop for message processing errors
                    continue

            except Exception as e:
                logger.error(f"Error in WebSocket message loop: {e}")
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket endpoint: {e}")
        try:
            await websocket.send_json({"type": "error", "message": "Internal server error"})
        except:
            pass
    finally:
        # cleanup
        if user:
            logger.info(f"Cleaning up WebSocket connection for user {user.id}")
            try:
                await manager.disconnect(user.id)
            except Exception as e:
                logger.error(f"Error disconnecting from manager: {e}")

            # don't stop the shell session immediately, keep it running for reconnection
            # the shell session will be cleaned up by the session manager after a timeout


async def handle_code_execution(message: dict, session_id: int, user_id: int, db: AsyncSession):
    """Handle Python code execution requests"""

    try:
        code = message.get("code", "")
        input_data = message.get("input_data")
        language = message.get("language", "python")

        # getting session files
        files = await file_system_service.get_session_files_as_dict(db, session_id, user_id)

        # executing code
        result = await code_execution_service.execute_python_code(
            code=code, session_id=session_id, files=files, input_data=input_data
        )

        # cleaniung the output from any npm or terminal specific output
        if result.get("output"):
            output_lines = result.get("output").splitlines()
            cleaned_output = []

            # more filtering of npm and non-Python output
            skip_line = False
            for line in output_lines:
                # skip npm timing and progress lines
                if any(
                    [
                        # npm timing messages
                        "timing npm:" in line,
                        line.strip().startswith("timing") and "Completed in" in line,
                        # npm progress and status messages
                        line.startswith("added ") and "packages" in line,
                        "packages are looking for funding" in line,
                        "run `npm fund`" in line,
                        # npm audit messages
                        "found 0 vulnerabilities" in line,
                        "audited" in line and "packages in" in line,
                        # npm version info
                        line.strip().startswith("npm") and "v" in line and len(line.strip()) < 15,
                        # Other npm output that might cause issues
                        "up to date in" in line.lower(),
                        # Any line with a number followed by "timing" which could cause decimal literal errors
                        any(char.isdigit() and "timing" in line for char in line[:10]),
                    ]
                ):
                    skip_line = True
                    continue

                # skipping any line that starts with a number followed by text (likely to cause syntax errors)
                if (
                    line.strip()
                    and line.strip()[0].isdigit()
                    and not line.strip().startswith(
                        ("0.", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")
                    )
                ):
                    words = line.strip().split()
                    if len(words) > 1 and words[0].isdigit() and not words[1].startswith("."):
                        skip_line = True
                        continue

                # including this line in the output
                if not skip_line:
                    cleaned_output.append(line)
                skip_line = False

            # join the cleaned output lines
            result["output"] = "\n".join(cleaned_output)

        # storing execution record
        execution_record = CodeExecution(
            session_id=session_id,
            command=f"python_execution",
            input_data=input_data,
            output=result.get("output"),
            error=result.get("error"),
            exit_code=result.get("exit_code"),
            execution_time_ms=result.get("execution_time_ms"),
            memory_usage_mb=result.get("memory_usage_mb"),
            status=result.get("status"),
        )

        db.add(execution_record)
        await db.commit()

        # sending result back to client
        await manager.send_personal_message(
            {"type": "code_execution_result", "result": result}, user_id
        )

    except Exception as e:
        logger.error(f"Code execution error: {e}")
        await manager.send_personal_message(
            {"type": "error", "message": f"Code execution failed: {str(e)}"}, user_id
        )


async def handle_terminal_command(message: dict, session_id: int, user_id: int, db: AsyncSession):
    """Handle terminal command execution"""

    try:
        command = message.get("command", "")
        cwd = message.get("cwd", "/workspace")
        input_data = message.get("input_data", "")

        # getting session files
        files = await file_system_service.get_session_files_as_dict(db, session_id, user_id)

        # executong terminal command
        result = await code_execution_service.execute_terminal_command(
            command=command, session_id=session_id, files=files, cwd=cwd, input_data=input_data
        )

        # storing execution record
        execution_record = CodeExecution(
            session_id=session_id,
            command=command,
            input_data=input_data,
            output=result.get("output"),
            error=result.get("error"),
            exit_code=result.get("exit_code"),
            execution_time_ms=result.get("execution_time_ms"),
            status=result.get("status"),
        )

        db.add(execution_record)

        # handling file changes if any
        file_changes = result.get("file_changes", {})
        if file_changes:
            for file_path, content in file_changes.items():
                # getting file extension to determine type
                file_type = "python" if file_path.endswith(".py") else "text"
                file_name = file_path.split("/")[-1]

                # checking if file already exists
                existing_file = await file_system_service.get_file_by_path(
                    db, session_id, user_id, file_path
                )

                if existing_file:
                    # updating existing file
                    await file_system_service.update_file_content(db, existing_file.id, content)
                else:
                    # making new file
                    await file_system_service.create_file(
                        db,
                        session_id=session_id,
                        name=file_name,
                        path=file_path,
                        content=content,
                        file_type=file_type,
                    )

        await db.commit()

        # sending result back to client
        await manager.send_personal_message({"type": "terminal_result", "result": result}, user_id)

    except Exception as e:
        logger.error(f"Terminal command execution error: {e}")
        await manager.send_personal_message(
            {"type": "error", "message": f"Command execution failed: {str(e)}"}, user_id
        )


async def handle_file_operation(message: dict, session_id: int, user_id: int, db: AsyncSession):
    """Handle file system operations like ls, cat, etc."""

    try:
        operation = message.get("operation", "")
        path = message.get("path", "")

        if operation == "ls":
            # listing directory contents
            contents = await file_system_service.list_directory(db, session_id, path, user_id)
            await manager.send_personal_message(
                {
                    "type": "file_operation_result",
                    "operation": "ls",
                    "result": {"success": True, "files": contents},
                },
                user_id,
            )

        elif operation == "cat":
            # reading file contents
            files = await file_system_service.get_files_by_session(db, session_id, user_id)
            target_file = next((f for f in files if f.path == path), None)

            if target_file:
                await manager.send_personal_message(
                    {
                        "type": "file_operation_result",
                        "operation": "cat",
                        "result": {"success": True, "output": target_file.content},
                    },
                    user_id,
                )
            else:
                await manager.send_personal_message(
                    {
                        "type": "file_operation_result",
                        "operation": "cat",
                        "result": {"success": False, "error": f"File not found: {path}"},
                    },
                    user_id,
                )

        else:
            await manager.send_personal_message(
                {"type": "error", "message": f"Unsupported file operation: {operation}"}, user_id
            )

    except Exception as e:
        logger.error(f"File operation error: {e}")
        await manager.send_personal_message(
            {"type": "error", "message": f"File operation failed: {str(e)}"}, user_id
        )


@router.post("/execute", response_model=TerminalResponse)
async def execute_code(
    command: TerminalCommand,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute Python code (HTTP endpoint for non-WebSocket clients)"""

    try:
        # verifying session access
        session = await session_service.get_session(db, command.session_id, current_user.id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # getting session files
        files = await file_system_service.get_session_files_as_dict(
            db, command.session_id, current_user.id
        )

        # executing code
        result = await code_execution_service.execute_python_code(
            code=command.command,
            session_id=command.session_id,
            files=files,
            input_data=command.input_data,
        )

        # storing execution record
        execution_record = CodeExecution(
            session_id=command.session_id,
            command=command.command,
            input_data=command.input_data,
            output=result.get("output"),
            error=result.get("error"),
            exit_code=result.get("exit_code"),
            execution_time_ms=result.get("execution_time_ms"),
            memory_usage_mb=result.get("memory_usage_mb"),
            status=result.get("status"),
        )

        db.add(execution_record)
        await db.commit()

        return TerminalResponse(
            output=result.get("output"),
            error=result.get("error"),
            exit_code=result.get("exit_code"),
            execution_time_ms=result.get("execution_time_ms"),
            status=result.get("status"),
        )

    except Exception as e:
        logger.error(f"Code execution error: {e}")
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")


@router.post("/command", response_model=TerminalResponse)
async def execute_terminal_command(
    command: TerminalCommand,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute terminal command (HTTP endpoint)"""

    try:
        # verifying session access
        session = await session_service.get_session(db, command.session_id, current_user.id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # getting session files
        files = await file_system_service.get_session_files_as_dict(
            db, command.session_id, current_user.id
        )

        # executing command
        result = await code_execution_service.execute_terminal_command(
            command=command.command, session_id=command.session_id, files=files
        )

        # storing execution record
        execution_record = CodeExecution(
            session_id=command.session_id,
            command=command.command,
            output=result.get("output"),
            error=result.get("error"),
            exit_code=result.get("exit_code"),
            execution_time_ms=result.get("execution_time_ms"),
            status=result.get("status"),
        )

        db.add(execution_record)
        await db.commit()

        return TerminalResponse(
            output=result.get("output"),
            error=result.get("error"),
            exit_code=result.get("exit_code"),
            execution_time_ms=result.get("execution_time_ms"),
            status=result.get("status"),
        )

    except Exception as e:
        logger.error(f"Terminal command error: {e}")
        raise HTTPException(status_code=500, detail=f"Command failed: {str(e)}")


@router.post("/code/execute")
async def execute_code(
    data: CodeExecutionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute code and return the result"""
    try:
        # logging the request
        logger.info(f"Code execution request received for session {data.session_id}")
        logger.debug(f"Code to execute: {data.code[:100]}...")

        # executing the code
        result = await code_execution_service.execute_code(
            data.code, data.language, data.session_id, data.input_data
        )

        # logging the result
        if result.error:
            logger.warning(f"Code execution error: {result.error[:100]}...")
        else:
            logger.info(f"Code executed successfully, output length: {len(result.output or '')}")

        # converting SimpleNamespace to dict
        return {
            "status": result.status,
            "output": result.output,
            "error": result.error,
            "exit_code": result.exit_code,
            "execution_time_ms": result.execution_time_ms,
            "memory_usage_mb": getattr(result, "memory_usage_mb", 0),
        }
    except Exception as e:
        logger.error(f"Error executing code: {e}")
        return {"error": f"Error executing code: {e}", "output": None}


@router.get("/history/{session_id}")
async def get_execution_history(
    session_id: int,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get execution history for a session"""

    try:
        # verifying session access
        session = await session_service.get_session(db, session_id, current_user.id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # getting execution history
        from sqlalchemy import desc

        result = await db.execute(
            select(CodeExecution)
            .where(CodeExecution.session_id == session_id)
            .order_by(desc(CodeExecution.created_at))
            .limit(limit)
        )
        executions = result.scalars().all()

        return [CodeExecutionResponse.model_validate(execution) for execution in executions]

    except Exception as e:
        logger.error(f"Error getting execution history: {e}")
        raise HTTPException(status_code=500, detail="Failed to get execution history")
