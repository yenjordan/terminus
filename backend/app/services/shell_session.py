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
    
    def __init__(self, session_id: int, user_id: int, username: str = "user", working_dir: str = "/workspace"):
        """Initialize a new shell session"""
        self.session_id = session_id
        self.user_id = user_id
        self.username = username  # Store the username
        # Create a unique working directory for each user and session
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
            
            # Create a pseudo-terminal
            self.master_fd, self.slave_fd = pty.openpty()
            
            # Set the working directory - use a persistent location
            self.working_dir = f"/tmp/terminus_workspace/session_{self.session_id}"
            os.makedirs(self.working_dir, exist_ok=True)
            
            # Create some basic files if they don't exist for testing
            self._setup_workspace()
            
            # Set terminal size
            import termios
            import struct
            import fcntl
            
            # Set terminal to 80x24 by default
            winsize = struct.pack('HHHH', 24, 80, 0, 0)
            fcntl.ioctl(self.slave_fd, termios.TIOCSWINSZ, winsize)
            
            # Start the shell process
            self.process = subprocess.Popen(
                ["/bin/bash", "--rcfile", os.path.join(self.working_dir, ".bashrc"), "-i"],
                stdin=self.slave_fd,
                stdout=self.slave_fd,
                stderr=self.slave_fd,
                cwd=self.working_dir,
                env={
                    **os.environ,
                    "TERM": "xterm-256color",
                    "PS1": "@terminuside:~# ",
                    "HOME": self.working_dir,
                    "SHELL": "/bin/bash",
                    "PATH": f"{os.environ.get('PATH', '')}:/usr/local/bin:/usr/bin:/bin:/usr/local/lib/node_modules/npm/bin",
                    "PYTHONPATH": self.working_dir,
                    "NODE_PATH": f"{self.working_dir}/node_modules",
                    "NPM_CONFIG_PREFIX": self.working_dir,
                    "EDITOR": "nano",
                    "USER": "terminus",
                    "HOSTNAME": "terminuside",
                    "LANG": "C.UTF-8",
                    "LC_ALL": "C.UTF-8"
                },
                preexec_fn=os.setsid
            )
            
            # Close slave fd in parent process
            os.close(self.slave_fd)
            self.slave_fd = None
            
            self.is_running = True
            
            # Start reading output in a separate thread
            self.read_thread = threading.Thread(target=self._read_output, daemon=True)
            self.read_thread.start()
            
            # Send initial commands to set up the environment
            await asyncio.sleep(0.5)  # Give shell time to start
            
            # Send commands to set prompt and clear screen
            os.write(self.master_fd, 'export PS1="@terminuside:~# "\n'.encode('utf-8'))
            os.write(self.master_fd, 'clear\n'.encode('utf-8'))
            
            logger.info(f"Shell session {self.shell_id} started for user {self.user_id} in {self.working_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start shell session: {e}")
            await self.stop()
            return False
    
    def _setup_workspace(self):
        """Set up workspace directory structure"""
        try:
            # Just ensure the directory exists
            os.makedirs(self.working_dir, exist_ok=True)
            
            # Create a package.json file with minimal content
            package_json_path = os.path.join(self.working_dir, "package.json")
            with open(package_json_path, 'w') as f:
                f.write('{\n  "private": true\n}\n')
            
            # Create a .bashrc file with minimal output and default color prompt
            bashrc_path = os.path.join(self.working_dir, ".bashrc")
            with open(bashrc_path, 'w') as f:
                f.write('''
# Set custom prompt with default color
export PS1="@terminuside:~# "

# Add system Node.js and npm to PATH
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/local/lib/node_modules/npm/bin:$PATH"

# Ensure npm works correctly
if ! command -v npm &>/dev/null; then
    echo "npm not found in PATH. Adding NodeSource paths..."
    # Try to find npm in common locations
    for npm_path in /usr/bin/npm /usr/local/bin/npm /opt/node/bin/npm; do
        if [ -x "$npm_path" ]; then
            export PATH="$(dirname $npm_path):$PATH"
            break
        fi
    done
fi

# Create custom ls alias to hide package.json and bin directory
alias ls='ls --hide=package.json --hide=.npm* --hide=node_modules --hide=bin'

# Silently set up Python environment
if command -v python3 &>/dev/null; then
    # Check if pandas is available
    if ! python3 -c "import pandas" &>/dev/null; then
        pip install pandas --quiet > /dev/null 2>&1
    fi
    
    # Check if scipy is available
    if ! python3 -c "import scipy" &>/dev/null; then
        pip install scipy --quiet > /dev/null 2>&1
    fi
    
    # Create a Python startup file to auto-import pandas and scipy
    if [ ! -f "$HOME/.pyrc" ]; then
        cat > "$HOME/.pyrc" << 'EOF' > /dev/null 2>&1
# Python startup file
try:
    import pandas as pd
    import scipy as sp
    import numpy as np
except ImportError:
    pass
EOF
    fi
fi

# Set PYTHONSTARTUP to auto-import libraries
export PYTHONSTARTUP="$HOME/.pyrc"

# Clear the screen to remove any startup messages
clear
''')
            
            # Create a .profile file that sources .bashrc
            profile_path = os.path.join(self.working_dir, ".profile")
            with open(profile_path, 'w') as f:
                f.write('''
if [ -f "$HOME/.bashrc" ]; then
    source "$HOME/.bashrc" > /dev/null 2>&1
fi
''')
            
            logger.info(f"Workspace set up in {self.working_dir}")
        except Exception as e:
            logger.error(f"Failed to set up workspace: {e}")
    
    def _read_output(self):
        """Read output from the terminal in a separate thread"""
        try:
            while self.is_running:
                try:
                    # Read from master fd
                    data = os.read(self.master_fd, 1024)
                    if not data:
                        break
                    
                    # Decode the data
                    output = data.decode('utf-8', errors='replace')
                    
                    # Send the output via callback
                    if self.output_callback:
                        asyncio.run_coroutine_threadsafe(
                            self.output_callback(output), 
                            self._loop
                        )
                except OSError:
                    # Terminal closed
                    break
                except Exception as e:
                    logger.error(f"Error reading from terminal: {e}")
                    break
        except Exception as e:
            logger.error(f"Error in read thread: {e}")
        finally:
            if self.is_running:
                asyncio.run_coroutine_threadsafe(
                    self.stop(),
                    self._loop
                )
    
    async def write_input(self, data: str):
        """Write input to the terminal"""
        try:
            if not self.is_running:
                return False
            
            # Write to master fd
            os.write(self.master_fd, data.encode('utf-8'))
            return True
        except Exception as e:
            logger.error(f"Error writing to terminal: {e}")
        return False
    
    async def resize(self, cols: int, rows: int):
        """Resize the terminal"""
        try:
            if not self.is_running:
                return False
            
            # Resize the terminal
            import termios
            import struct
            import fcntl
            
            winsize = struct.pack('HHHH', rows, cols, 0, 0)
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
            return True
        except Exception as e:
            logger.error(f"Error resizing terminal: {e}")
        return False
    
    async def stop(self):
        """Stop the shell session"""
        try:
            self.is_running = False
            
            # Kill the process if it's still running
            if self.process and self.process.poll() is None:
                try:
                    # Send SIGTERM to the process group
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                    
                    # Wait for a short time for process to terminate
                    for _ in range(5):
                        if self.process.poll() is not None:
                            break
                        await asyncio.sleep(0.1)
                    
                    # If process is still running, force kill
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


class ShellSessionManager:
    """Manages multiple shell sessions"""
    
    def __init__(self):
        self.sessions: Dict[str, ShellSession] = {}
        self.user_sessions: Dict[int, str] = {}  # user_id -> shell_id
        self.session_users: Dict[int, int] = {}  # session_id -> user_id
        self._lock = asyncio.Lock()
    
    async def create_session(self, session_id: int, user_id: int, username: str = "user", output_callback: Callable[[str], Awaitable[None]] = None) -> Optional[str]:
        """Create a new shell session for a user"""
        try:
            async with self._lock:
                # Check if this session is already being used by another user
                existing_user_id = self.session_users.get(session_id)
                if existing_user_id is not None and existing_user_id != user_id:
                    logger.warning(f"Session {session_id} is already in use by user {existing_user_id}, denying access to user {user_id}")
                    return None
                
                # Stop any existing session for this user
                await self.stop_user_session(user_id)
                
                # Create new shell session
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
                # Session is dead, clean it up
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
            # Remove from session_users mapping
            if session.session_id in self.session_users:
                del self.session_users[session.session_id]
            # Stop the session
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


# Global shell session manager
shell_manager = ShellSessionManager() 