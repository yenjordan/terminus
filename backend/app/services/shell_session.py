import asyncio
import os
import pty
import signal
import subprocess
import threading
import time
from typing import Dict, Optional, Callable, Awaitable
import uuid

from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class ShellSession:
    """Manages a real shell session with PTY support"""

    def __init__(
        self, session_id: int, user_id: int, username: str = "user", working_dir: str = "/workspace"
    ):
        """Initialize a new shell session"""
        self.session_id = session_id
        self.user_id = user_id
        self.username = username  # Store the username
        # creating a unique working directory for each user/session
        self.working_dir = f"/tmp/terminus_workspace/session_{session_id}_user_{user_id}"
        self.shell_id = str(uuid.uuid4())
        self.process = None
        self.master_fd = None
        self.slave_fd = None
        self.is_running = False
        self.output_callback = None
        self.read_thread = None
        self._loop = None

    async def start(self, output_callback: Callable[[str], Awaitable[None]] = None):
        """Start the shell session"""
        try:
            self.output_callback = output_callback
            self._loop = asyncio.get_event_loop()

            # pseudo-terminal
            self.master_fd, self.slave_fd = pty.openpty()

            # setting the working directoryby using a persistent location
            self.working_dir = f"/tmp/terminus_workspace/session_{self.session_id}"
            os.makedirs(self.working_dir, exist_ok=True)

            # creating some basic files if they don't exist for testing
            self._setup_workspace()

            # setting terminal size
            import termios
            import struct
            import fcntl

            # setting terminal to 80x24 by default
            winsize = struct.pack("HHHH", 24, 80, 0, 0)
            fcntl.ioctl(self.slave_fd, termios.TIOCSWINSZ, winsize)

            # starting shell process with a custom PS1 prompt - using standard bash
            self.process = subprocess.Popen(
                ["/bin/bash"],
                stdin=self.slave_fd,
                stdout=self.slave_fd,
                stderr=self.slave_fd,
                cwd=self.working_dir,
                env={
                    **os.environ,
                    "TERM": "xterm-256color",
                    "PS1": "terminuside:~# ",
                    "HOME": self.working_dir,
                    "SHELL": "/bin/bash",
                    "PATH": f"{os.environ.get('PATH', '')}:/usr/local/bin:/usr/bin:/bin",
                    "PYTHONPATH": self.working_dir,
                    "USER": "terminus",
                    "HOSTNAME": "terminuside",
                    "LANG": "C.UTF-8",
                    "LC_ALL": "C.UTF-8",
                },
                preexec_fn=os.setsid,
            )

            # closing slave fd in parent process
            os.close(self.slave_fd)
            self.slave_fd = None

            self.is_running = True

            # starting reading output in a separate thread
            self.read_thread = threading.Thread(target=self._read_output, daemon=True)
            self.read_thread.start()

            # Wait a bit for shell to start
            await asyncio.sleep(0.5)

            logger.info(
                f"Shell session {self.shell_id} started for user {self.user_id} in {self.working_dir}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to start shell session: {e}")
            await self.stop()
            return False

    def _setup_workspace(self):
        """Set up the workspace directory with basic files"""
        try:
            # creating workspace directory if it doesn't exist
            os.makedirs(self.working_dir, exist_ok=True)

            # creating a package.json file with min content
            package_json_path = os.path.join(self.working_dir, "package.json")
            with open(package_json_path, "w") as f:
                f.write('{\n  "private": true\n}\n')

            # creating a .bashrc file with minimal content - just set prompt
            bashrc_path = os.path.join(self.working_dir, ".bashrc")
            with open(bashrc_path, "w") as f:
                f.write(
                    """
# Set simple prompt
export PS1="terminuside:~# "

# Add system Node.js and npm to PATH
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/local/lib/node_modules/npm/bin:$PATH"

# Create custom ls alias to hide only package.json, npm files, and node_modules
alias ls='ls --hide=package.json --hide=.npm* --hide=node_modules'
"""
                )

            logger.info(f"Workspace set up successfully in {self.working_dir}")
        except Exception as e:
            logger.error(f"Failed to set up workspace: {e}")

    def _read_output(self):
        """Read output from the terminal in a separate thread"""
        try:
            while self.is_running:
                try:
                    # reading from master fd
                    data = os.read(self.master_fd, 1024)
                    if not data:
                        break

                    output = data.decode("utf-8", errors="replace")

                    # sending output via callback
                    if self.output_callback:
                        asyncio.run_coroutine_threadsafe(self.output_callback(output), self._loop)
                except OSError:
                    # terminal closed
                    break
                except Exception as e:
                    logger.error(f"Error reading from terminal: {e}")
                    break
        except Exception as e:
            logger.error(f"Error in read thread: {e}")
        finally:
            if self.is_running:
                asyncio.run_coroutine_threadsafe(self.stop(), self._loop)

    async def write_input(self, data: str):
        """Write input to the shell session"""
        if not self.is_running or not self.master_fd:
            logger.error("Cannot write to shell: session not running")
            return False

        try:
            # Write the data to the master file descriptor
            os.write(self.master_fd, data.encode("utf-8"))
            return True
        except Exception as e:
            logger.error(f"Failed to write to shell: {e}")
            return False

    async def resize(self, cols: int, rows: int):
        """Resize the terminal"""
        try:
            if not self.is_running:
                return False

            # resizing terminal
            import termios
            import struct
            import fcntl

            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
            return True
        except Exception as e:
            logger.error(f"Error resizing terminal: {e}")
        return False

    async def stop(self):
        """Stop the shell session"""
        try:
            self.is_running = False

            # killing the process if it's still running
            if self.process and self.process.poll() is None:
                try:
                    # sending SIGTERM to the process group
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)

                    # waiting for a short time for process to terminate
                    for _ in range(5):
                        if self.process.poll() is not None:
                            break
                        await asyncio.sleep(0.1)

                    # if process is still running then force kill
                    if self.process.poll() is None:
                        os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                except Exception as e:
                    logger.error(f"Error killing process: {e}")

            # Close master fd
            if self.master_fd is not None:
                try:
                    os.close(self.master_fd)
                except Exception:
                    pass
                self.master_fd = None

            logger.info(f"Shell session {self.shell_id} stopped")
        except Exception as e:
            logger.error(f"Error stopping shell session: {e}")

    def _start_keep_alive(self):
        """Start a thread to keep the shell session alive and responsive"""

        def keep_alive():
            while self.is_running:
                try:
                    if self.master_fd:
                        # Send a null byte every 30 seconds to keep the session alive
                        os.write(self.master_fd, b"\0")
                    time.sleep(30)
                except Exception as e:
                    logger.error(f"Keep-alive error: {e}")
                    break

        # Start the keep-alive thread
        keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
        keep_alive_thread.start()


class ShellSessionManager:
    """Manages multiple shell sessions"""

    def __init__(self):
        self.sessions: Dict[str, ShellSession] = {}
        self.user_sessions: Dict[int, str] = {}  # user_id -> shell_id
        self.session_users: Dict[int, int] = {}  # session_id -> user_id
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        session_id: int,
        user_id: int,
        username: str = "user",
        output_callback: Callable[[str], Awaitable[None]] = None,
    ) -> Optional[str]:
        """Create a new shell session for a user"""
        try:
            async with self._lock:
                # checking if session is already being used by another user
                existing_user_id = self.session_users.get(session_id)
                if existing_user_id is not None and existing_user_id != user_id:
                    logger.warning(
                        f"Session {session_id} is already in use by user {existing_user_id}, denying access to user {user_id}"
                    )
                    return None

                # stopping any existing session for this user
                await self.stop_user_session(user_id)

                # creating new shell session
                shell_session = ShellSession(session_id, user_id, username)

                if await shell_session.start(output_callback):
                    self.sessions[shell_session.shell_id] = shell_session
                    self.user_sessions[user_id] = shell_session.shell_id
                    self.session_users[session_id] = user_id
                    return shell_session.shell_id
        except Exception as e:
            logger.error(f"Failed to create shell session: {e}")

        return None

    async def get_session(self, user_id: int) -> Optional[ShellSession]:
        """Get the shell session for a user"""
        shell_id = self.user_sessions.get(user_id)
        if shell_id and shell_id in self.sessions:
            session = self.sessions[shell_id]
            if session.is_running:
                return session
            else:
                # session is dead
                await self.stop_user_session(user_id)
        return None

    async def write_to_session(self, user_id: int, data: str) -> bool:
        """Write data to a user's shell session"""
        session = await self.get_session(user_id)
        if session:
            return await session.write_input(data)
        return False

    async def resize_session(self, user_id: int, cols: int, rows: int) -> bool:
        """Resize a user's terminal"""
        session = await self.get_session(user_id)
        if session:
            return await session.resize(cols, rows)
        return False

    async def stop_user_session(self, user_id: int):
        """Stop a user's shell session"""
        shell_id = self.user_sessions.get(user_id)
        if shell_id and shell_id in self.sessions:
            session = self.sessions[shell_id]
            # removing from session_users mapping
            if session.session_id in self.session_users:
                del self.session_users[session.session_id]
            # stopping the session
            await session.stop()
            del self.sessions[shell_id]
            del self.user_sessions[user_id]

    async def stop_all_sessions(self):
        """Stop all shell sessions"""
        for session in list(self.sessions.values()):
            await session.stop()
        self.sessions.clear()
        self.user_sessions.clear()
        self.session_users.clear()


shell_manager = ShellSessionManager()
