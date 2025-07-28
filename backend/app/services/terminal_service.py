import asyncio
import os
import pty
import subprocess
import signal
import threading
import time
from typing import Dict, Optional, Callable
import logging

logger = logging.getLogger(__name__)


class TerminalSession:
    """Manages a real shell session using pseudo-terminal"""

    def __init__(self, session_id: int, user_id: int, working_dir: str = "/workspace"):
        self.session_id = session_id
        self.user_id = user_id
        self.working_dir = working_dir
        self.master_fd: Optional[int] = None
        self.slave_fd: Optional[int] = None
        self.process: Optional[subprocess.Popen] = None
        self.is_running = False
        self.output_callback: Optional[Callable[[str], None]] = None
        self.read_thread: Optional[threading.Thread] = None

    def start(self, output_callback: Callable[[str], None]):
        """Start the shell session"""
        try:
            self.output_callback = output_callback

            # creating pseudo-terminal
            self.master_fd, self.slave_fd = pty.openpty()

            # setting terminal size
            import termios
            import struct
            import fcntl

            # setting terminal to 80x24 by default
            winsize = struct.pack("HHHH", 24, 80, 0, 0)
            fcntl.ioctl(self.slave_fd, termios.TIOCSWINSZ, winsize)

            # creating environment
            env = os.environ.copy()
            env.update(
                {
                    "TERM": "xterm-256color",
                    "SHELL": "/bin/bash",
                    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                    "HOME": "/workspace",
                    "USER": "root",
                    "LANG": "C.UTF-8",
                    "LC_ALL": "C.UTF-8",
                }
            )

            # making working directory exists
            os.makedirs(self.working_dir, exist_ok=True)

            # staring bash session
            self.process = subprocess.Popen(
                ["/bin/bash", "-l"],
                stdin=self.slave_fd,
                stdout=self.slave_fd,
                stderr=self.slave_fd,
                env=env,
                cwd=self.working_dir,
                preexec_fn=os.setsid,
            )

            # closing slave fd in parent process
            os.close(self.slave_fd)
            self.slave_fd = None

            self.is_running = True

            # starting reading thread
            self.read_thread = threading.Thread(target=self._read_output, daemon=True)
            self.read_thread.start()

            logger.info(f"Terminal session {self.session_id} started for user {self.user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to start terminal session: {e}")
            self.cleanup()
            return False

    def _read_output(self):
        """Read output from the terminal in a separate thread"""
        try:
            while self.is_running and self.master_fd is not None:
                try:
                    # using select to check if data is available
                    import select

                    ready, _, _ = select.select([self.master_fd], [], [], 0.1)

                    if ready:
                        data = os.read(self.master_fd, 1024)
                        if data:
                            try:
                                text = data.decode("utf-8", errors="replace")
                                if self.output_callback:
                                    self.output_callback(text)
                            except Exception as e:
                                logger.error(f"Error processing terminal output: {e}")
                        else:
                            # EOF - terminal closed
                            break
                except OSError:
                    # terminal closed
                    break
                except Exception as e:
                    logger.error(f"Error reading from terminal: {e}")
                    break

        except Exception as e:
            logger.error(f"Terminal read thread error: {e}")
        finally:
            self.is_running = False

    def write_input(self, data: str):
        """Write input to the terminal"""
        try:
            if self.master_fd is not None and self.is_running:
                os.write(self.master_fd, data.encode("utf-8"))
                return True
        except Exception as e:
            logger.error(f"Error writing to terminal: {e}")
        return False

    def resize(self, cols: int, rows: int):
        """Resize the terminal"""
        try:
            if self.master_fd is not None:
                import termios
                import struct
                import fcntl

                winsize = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
                return True
        except Exception as e:
            logger.error(f"Error resizing terminal: {e}")
        return False

    def cleanup(self):
        """Clean up the terminal session"""
        self.is_running = False

        try:
            if self.process:
                # sending SIGTERM to the process group
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)

                # wait a bit for graceful shutdown
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    # force kill if necessary
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                    self.process.wait()

                self.process = None
        except Exception as e:
            logger.error(f"Error terminating process: {e}")

        try:
            if self.master_fd is not None:
                os.close(self.master_fd)
                self.master_fd = None
        except Exception as e:
            logger.error(f"Error closing master fd: {e}")

        try:
            if self.slave_fd is not None:
                os.close(self.slave_fd)
                self.slave_fd = None
        except Exception as e:
            logger.error(f"Error closing slave fd: {e}")

        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=1)

        logger.info(f"Terminal session {self.session_id} cleaned up")


class TerminalManager:
    """Manages multiple terminal sessions"""

    def __init__(self):
        self.sessions: Dict[str, TerminalSession] = {}

    def create_session(
        self, session_id: int, user_id: int, output_callback: Callable[[str], None]
    ) -> bool:
        """Create a new terminal session"""
        session_key = f"{user_id}_{session_id}"

        # cleaning up existing session if any
        if session_key in self.sessions:
            self.close_session(session_id, user_id)

        # creating working directory based on session
        working_dir = f"/workspace/session_{session_id}"

        terminal_session = TerminalSession(session_id, user_id, working_dir)
        if terminal_session.start(output_callback):
            self.sessions[session_key] = terminal_session
            return True
        return False

    def get_session(self, session_id: int, user_id: int) -> Optional[TerminalSession]:
        """Get an existing terminal session"""
        session_key = f"{user_id}_{session_id}"
        return self.sessions.get(session_key)

    def write_to_session(self, session_id: int, user_id: int, data: str) -> bool:
        """Write data to a terminal session"""
        session = self.get_session(session_id, user_id)
        if session:
            return session.write_input(data)
        return False

    def resize_session(self, session_id: int, user_id: int, cols: int, rows: int) -> bool:
        """Resize a terminal session"""
        session = self.get_session(session_id, user_id)
        if session:
            return session.resize(cols, rows)
        return False

    def close_session(self, session_id: int, user_id: int):
        """Close a terminal session"""
        session_key = f"{user_id}_{session_id}"
        if session_key in self.sessions:
            session = self.sessions[session_key]
            session.cleanup()
            del self.sessions[session_key]

    def cleanup_all(self):
        """Clean up all sessions"""
        for session in list(self.sessions.values()):
            session.cleanup()
        self.sessions.clear()


# global terminal manager instance
terminal_manager = TerminalManager()
