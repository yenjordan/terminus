import asyncio
import time
import tempfile
import os
import shutil
import psutil
import subprocess
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

# Global flag to check if Docker is available
DOCKER_AVAILABLE = False
try:
    import docker
    from docker.errors import ContainerError, ImageNotFound, APIError

    DOCKER_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    pass
import aiofiles
from app.utils.logger import setup_logger
import shlex

logger = setup_logger(__name__)


class CodeExecutionService:
    """Secure code execution service using Docker containers"""

    def __init__(self):
        self.max_execution_time = 30  # seconds
        self.max_memory = "512m"  # 512 MB
        self.max_cpu_count = 1

        # initializing Docker client if available
        self.docker_client = None
        global DOCKER_AVAILABLE
        if DOCKER_AVAILABLE:
            try:
                self.docker_client = docker.from_env()
                logger.info("Docker client initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Docker client: {e}")
                logger.warning("Code execution will run in fallback mode (non-containerized)")
                DOCKER_AVAILABLE = False

        # security settings
        self.blocked_imports = [
            "os",
            "subprocess",
            "sys",
            "socket",
            "urllib",
            "requests",
            "http",
            "ftplib",
            "smtplib",
            "telnetlib",
            "webbrowser",
            "__import__",
            "eval",
            "exec",
            "compile",
            "globals",
            "locals",
        ]

        self.allowed_builtins = [
            "abs",
            "all",
            "any",
            "bin",
            "bool",
            "chr",
            "dict",
            "dir",
            "divmod",
            "enumerate",
            "filter",
            "float",
            "format",
            "hex",
            "int",
            "len",
            "list",
            "map",
            "max",
            "min",
            "oct",
            "ord",
            "pow",
            "print",
            "range",
            "repr",
            "reversed",
            "round",
            "set",
            "sorted",
            "str",
            "sum",
            "tuple",
            "type",
            "zip",
        ]

    async def execute_code(
        self, code: str, language: str, session_id: int, input_data: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute code in the specified language
        Currently supports: python, javascript
        Returns execution results including output, errors, and metrics
        """
        logger.info(f"Executing {language} code for session {session_id}")

        # getting session files
        #  don't need to fetch files here as they're passed by the caller if needed

        if language.lower() == "python":
            result = await self.execute_python_code(code, session_id, None, input_data)
        else:
            # for unsupported languages, return an error
            result = {
                "status": "failed",
                "error": f"Unsupported language: {language}",
                "output": None,
                "exit_code": 1,
                "execution_time_ms": 0,
                "memory_usage_mb": 0,
            }

        # converting dictionary to object with attributes for compatibility
        from types import SimpleNamespace

        return SimpleNamespace(**result)

    async def prepare_execution_environment(self, session_id: int, files: Dict[str, str]) -> str:
        """
        Prepare a temporary directory with user files for execution
        Returns the path to the temporary directory
        """
        temp_dir = tempfile.mkdtemp(prefix=f"terminus_session_{session_id}_")

        try:
            # writing all files to temp directory
            for file_path, content in files.items():
                full_path = os.path.join(temp_dir, file_path.lstrip("/"))
                os.makedirs(os.path.dirname(full_path), exist_ok=True)

                async with aiofiles.open(full_path, "w") as f:
                    await f.write(content)

            logger.info(f"Prepared execution environment at {temp_dir}")
            return temp_dir

        except Exception as e:
            # cleaninng up on error
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.error(f"Failed to prepare execution environment: {str(e)}")
            raise

    async def sync_files_from_environment(
        self, temp_dir: str, original_files: Dict[str, str]
    ) -> Dict[str, str]:
        """
        Sync files back from the execution environment to detect changes
        Returns a dict of changed/new files
        """
        updated_files = {}

        try:
            # walking through the temp directory to find all files
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    # Get relative path from temp_dir
                    rel_path = os.path.relpath(full_path, temp_dir)
                    # Normalize path to use forward slashes
                    rel_path = rel_path.replace(os.sep, "/")
                    if not rel_path.startswith("/"):
                        rel_path = "/" + rel_path

                    try:
                        async with aiofiles.open(full_path, "r") as f:
                            content = await f.read()

                        # checking if file content has changed or is new
                        if rel_path not in original_files or original_files[rel_path] != content:
                            updated_files[rel_path] = content

                    except (UnicodeDecodeError, IsADirectoryError):
                        # skippung binary files or directories
                        continue

        except Exception as e:
            logger.error(f"Failed to sync files from environment: {str(e)}")

        return updated_files

    def validate_code_security(self, code: str) -> Tuple[bool, Optional[str]]:
        """
        Validate code for security issues
        Returns (is_safe, error_message)
        """
        # checking for blocked imports
        for blocked in self.blocked_imports:
            if f"import {blocked}" in code or f"from {blocked}" in code:
                return False, f"Import '{blocked}' is not allowed for security reasons"

        # checking for dangerous function calls
        dangerous_patterns = [
            "open(",
            "file(",
            "__import__(",
            "eval(",
            "exec(",
            "compile(",
            "globals(",
            "locals(",
            "vars(",
        ]

        for pattern in dangerous_patterns:
            if pattern in code:
                return (
                    False,
                    f"Function call '{pattern.rstrip('(')}' is not allowed for security reasons",
                )

        return True, None

    async def execute_python_code(
        self,
        code: str,
        session_id: int,
        files: Optional[Dict[str, str]] = None,
        input_data: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute Python code in a secure environment
        Returns execution results including output, errors, and metrics
        """
        # security validation
        is_safe, error_msg = self.validate_code_security(code)
        if not is_safe:
            return {
                "status": "failed",
                "error": error_msg,
                "output": None,
                "exit_code": 1,
                "execution_time_ms": 0,
                "memory_usage_mb": 0,
            }

        # checking if code contains a class Solution and a method, but no print statement
        # common in coding challenges where the user expects to see output
        if "class Solution" in code and "def " in code and "print(" not in code:
            # look for a method that returns something
            if "return " in code:
                # add code to instantiate the Solution class and print the result
                if "if __name__ == '__main__':" not in code:
                    # add test case execution code
                    if input_data and input_data.strip():
                        # use the provided input data
                        test_input = input_data.strip()
                        code += f"""

# Auto-added test execution code
if __name__ == '__main__':
    solution = Solution()
    test_input = {test_input}
    result = solution.{self._extract_method_name(code)}(test_input)
    print(result)
"""
                    else:
                        # add a generic test case for common LeetCode-style problems
                        code += """

# Auto-added test execution code
if __name__ == '__main__':
    solution = Solution()
    # Add a test case based on the method signature
    test_input = [0, 1, 1, 1, 0, 1, 1, 0, 1]
    result = solution.longestSubarray(test_input)
    print(result)
"""

        # use Docker if available, otherwise fall back to subprocess
        global DOCKER_AVAILABLE
        if DOCKER_AVAILABLE and self.docker_client:
            return await self._execute_python_code_docker(code, session_id, files, input_data)
        else:
            return await self._execute_python_code_subprocess(code, session_id, files, input_data)

    async def execute_python_code_from_file(
        self, file_path: str, input_data: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute Python code from a file path
        Returns execution results including output, errors, and metrics
        """
        start_time = time.time()
        try:
            logger.info(f"Executing Python code from file: {file_path}")

            # checking if file exists
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return {
                    "status": "failed",
                    "error": f"File not found: {file_path}",
                    "output": None,
                    "exit_code": 1,
                    "execution_time_ms": 0,
                    "memory_usage_mb": 0,
                }

            # reading the file content
            with open(file_path, "r") as f:
                code = f.read()

            # security validation
            is_safe, error_msg = self.validate_code_security(code)
            if not is_safe:
                return {
                    "status": "failed",
                    "error": error_msg,
                    "output": None,
                    "exit_code": 1,
                    "execution_time_ms": 0,
                    "memory_usage_mb": 0,
                }

            # executing the code directly using subprocess
            try:
                result = await self._execute_python_file_subprocess(file_path, input_data)
                execution_time = (time.time() - start_time) * 1000  # ms

                # adding execution time to result
                result["execution_time_ms"] = execution_time

                return result
            except Exception as e:
                logger.error(f"Error executing Python file subprocess: {e}")
                return {
                    "status": "failed",
                    "error": f"Execution error: {str(e)}",
                    "output": None,
                    "exit_code": 1,
                    "execution_time_ms": (time.time() - start_time) * 1000,
                    "memory_usage_mb": 0,
                }

        except Exception as e:
            logger.error(f"Error executing Python file: {e}", exc_info=True)
            return {
                "status": "failed",
                "error": f"Execution error: {str(e)}",
                "output": None,
                "exit_code": 1,
                "execution_time_ms": (time.time() - start_time) * 1000,
                "memory_usage_mb": 0,
            }

    async def _execute_python_code_docker(
        self,
        code: str,
        session_id: int,
        files: Optional[Dict[str, str]] = None,
        input_data: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute Python code in a secure Docker container"""
        start_time = time.time()
        temp_dir = None
        container = None

        try:
            # prepping execution environment
            if files is None:
                files = {}

            # adding the main script
            files["main.py"] = code
            temp_dir = await self.prepare_execution_environment(session_id, files)

            # creating Docker container with restrictions
            container = self.docker_client.containers.run(
                "python:3.11-slim",
                command=["python", "/workspace/main.py"],
                volumes={temp_dir: {"bind": "/workspace", "mode": "ro"}},
                working_dir="/workspace",
                mem_limit=self.max_memory,
                cpu_count=self.max_cpu_count,
                network_disabled=True,
                security_opt=["no-new-privileges:true"],
                user="nobody",
                stdin_open=bool(input_data),
                stdout=True,
                stderr=True,
                detach=True,
                remove=True,
            )

            # sending input if provided
            if input_data:
                container.exec_run(f"echo '{input_data}'", stdin=True)

            # waiting for execution with timeout
            try:
                result = container.wait(timeout=self.max_execution_time)
                exit_code = result["StatusCode"]
            except Exception:
                container.kill()
                return {
                    "status": "timeout",
                    "error": f"Execution timed out after {self.max_execution_time} seconds",
                    "output": None,
                    "exit_code": 124,  # Timeout exit code
                    "execution_time_ms": self.max_execution_time * 1000,
                    "memory_usage_mb": 0,
                }

            # getting output and logs
            logs = container.logs(stdout=True, stderr=True).decode("utf-8")

            # parsing stdout and stderr
            output_lines = []
            error_lines = []
            for line in logs.split("\n"):
                if line.strip():
                    output_lines.append(line)

            execution_time_ms = (time.time() - start_time) * 1000

            # getting memory stats (approximation)
            memory_usage_mb = 0
            try:
                stats = container.stats(stream=False)
                memory_usage_mb = stats["memory"]["usage"] / (1024 * 1024)
            except:
                pass

            status = "completed" if exit_code == 0 else "failed"
            output = "\n".join(output_lines) if output_lines else None
            error = "\n".join(error_lines) if error_lines and exit_code != 0 else None

            return {
                "status": status,
                "output": output,
                "error": error,
                "exit_code": exit_code,
                "execution_time_ms": execution_time_ms,
                "memory_usage_mb": memory_usage_mb,
            }

        except ImageNotFound:
            logger.error("Python Docker image not found")
            return {
                "status": "failed",
                "error": "Python execution environment not available",
                "output": None,
                "exit_code": 1,
                "execution_time_ms": 0,
                "memory_usage_mb": 0,
            }

        except APIError as e:
            logger.error(f"Docker API error: {str(e)}")
            return {
                "status": "failed",
                "error": "Container execution failed",
                "output": None,
                "exit_code": 1,
                "execution_time_ms": 0,
                "memory_usage_mb": 0,
            }

        except Exception as e:
            logger.error(f"Code execution error: {str(e)}")
            return {
                "status": "failed",
                "error": f"Execution error: {str(e)}",
                "output": None,
                "exit_code": 1,
                "execution_time_ms": (time.time() - start_time) * 1000,
                "memory_usage_mb": 0,
            }

        finally:
            # cleanup
            if container:
                try:
                    container.remove(force=True)
                except:
                    pass

            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    async def _execute_python_code_subprocess(
        self,
        code: str,
        session_id: int,
        files: Optional[Dict[str, str]] = None,
        input_data: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute Python code using subprocess (fallback method)"""
        start_time = time.time()
        temp_dir = None

        try:
            # prepping execution environment
            if files is None:
                files = {}

            # adding the main script
            files["main.py"] = code
            temp_dir = await self.prepare_execution_environment(session_id, files)

            # prepping input data file if provided
            input_file = None
            if input_data:
                input_file = os.path.join(temp_dir, "input.txt")
                async with aiofiles.open(input_file, "w") as f:
                    await f.write(input_data)

            # executing the code with resource limitations
            process = await asyncio.create_subprocess_exec(
                "python",
                os.path.join(temp_dir, "main.py"),
                stdin=asyncio.subprocess.PIPE if input_data else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=temp_dir,
            )

            # setting a timeout for execution
            try:
                if input_data:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(input=input_data.encode()),
                        timeout=self.max_execution_time,
                    )
                else:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(), timeout=self.max_execution_time
                    )

                output = stdout.decode() if stdout else ""
                error = stderr.decode() if stderr else ""
                exit_code = process.returncode

            except asyncio.TimeoutError:
                # killing the process if it times out
                try:
                    process.kill()
                except ProcessLookupError:
                    pass

                output = ""
                error = "Execution timed out"
                exit_code = -1

            # calcuating metrics
            execution_time_ms = (time.time() - start_time) * 1000
            memory_usage_mb = 0

            # detecting file changes
            original_files = files.copy()
            file_changes = await self.sync_files_from_environment(temp_dir, original_files)

            return {
                "status": "success" if exit_code == 0 else "failed",
                "output": output,
                "error": error,
                "exit_code": exit_code,
                "execution_time_ms": execution_time_ms,
                "memory_usage_mb": memory_usage_mb,
                "file_changes": file_changes,
            }

        except Exception as e:
            logger.error(f"Python code execution error: {str(e)}")
            return {
                "status": "failed",
                "error": f"Execution error: {str(e)}",
                "output": None,
                "exit_code": 1,
                "execution_time_ms": (time.time() - start_time) * 1000,
                "memory_usage_mb": 0,
                "file_changes": {},
            }

        finally:
            # cleanning up temp directory
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)

    async def _execute_python_file_subprocess(
        self, file_path: str, input_data: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute a Python file using subprocess"""
        try:
            # creating a process to run the Python file
            cmd = ["python", file_path]

            # setting up process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE if input_data else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # sending input if provided
            if input_data:
                process.stdin.write(input_data.encode())
                await process.stdin.drain()
                process.stdin.close()

            # capturing output with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self.max_execution_time
                )

                # getting memory usage
                memory_usage = 0
                try:
                    if process.pid:
                        process_info = psutil.Process(process.pid)
                        memory_info = process_info.memory_info()
                        memory_usage = memory_info.rss / (1024 * 1024)  # Convert to MB
                except (psutil.NoSuchProcess, ProcessLookupError, psutil.AccessDenied) as e:
                    # proc might have terminated already, which is fine
                    logger.debug(f"Could not get memory usage: {e}")
                except Exception as e:
                    logger.warning(f"Error getting memory usage: {e}")

                return {
                    "status": "completed" if process.returncode == 0 else "failed",
                    "output": stdout.decode("utf-8"),
                    "error": stderr.decode("utf-8"),
                    "exit_code": process.returncode,
                    "memory_usage_mb": memory_usage,
                }

            except asyncio.TimeoutError:
                # Kill the process if it times out
                if process.returncode is None:
                    try:
                        process.kill()
                    except:
                        pass

                return {
                    "status": "timeout",
                    "error": f"Execution timed out after {self.max_execution_time} seconds",
                    "output": None,
                    "exit_code": 124,  # Timeout exit code
                    "execution_time_ms": self.max_execution_time * 1000,
                    "memory_usage_mb": 0,
                }

        except Exception as e:
            logger.error(f"Error in subprocess execution: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "output": None,
                "exit_code": 1,
                "memory_usage_mb": 0,
            }

    async def execute_terminal_command(
        self,
        command: str,
        session_id: int,
        files: Optional[Dict[str, str]] = None,
        cwd: str = "/workspace",
        input_data: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute terminal command in a secure environment"""
        # use Docker if available, otherwise fall back to subprocess
        global DOCKER_AVAILABLE
        if DOCKER_AVAILABLE and self.docker_client:
            return await self._execute_terminal_command_docker(
                command, session_id, files, cwd, input_data
            )
        else:
            return await self._execute_terminal_command_subprocess(
                command, session_id, files, cwd, input_data
            )

    async def _execute_terminal_command_docker(
        self,
        command: str,
        session_id: int,
        files: Optional[Dict[str, str]] = None,
        cwd: str = "/workspace",
        input_data: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute terminal command in Docker container"""
        start_time = time.time()
        container = None
        temp_dir = None

        try:
            # prepping files
            if files is None:
                files = {}

            if files:
                temp_dir = await self.prepare_execution_environment(session_id, files)
            else:
                temp_dir = tempfile.mkdtemp(prefix=f"terminus_session_{session_id}_")

            # create a custom .bashrc file to set the PS1 prompt
            bashrc_path = os.path.join(temp_dir, ".bashrc")
            with open(bashrc_path, "w") as f:
                f.write('export PS1="@terminuside:~# "\n')
                f.write("clear\n")  # Clear the screen to remove any startup messages

            # sanitize command
            safe_command = self._sanitize_terminal_command(command)
            if not safe_command:
                return {
                    "status": "failed",
                    "error": "Command not allowed for security reasons",
                    "output": None,
                    "exit_code": 1,
                    "execution_time_ms": 0,
                }

            # wrap the command to source .bashrc first
            wrapped_command = f"bash -c 'source /workspace/.bashrc && {safe_command}'"

            # create container for terminal execution
            container = self.docker_client.containers.run(
                "python:3.11-slim",
                command=["bash", "-c", wrapped_command],
                volumes={temp_dir: {"bind": "/workspace", "mode": "rw"}},
                working_dir=cwd,
                mem_limit=self.max_memory,
                cpu_count=self.max_cpu_count,
                network_disabled=False,  # Allow network for pip install
                security_opt=["no-new-privileges:true"],
                stdout=True,
                stderr=True,
                detach=True,
                remove=True,
                hostname="terminuside",  # Set the hostname to terminuside
            )

            # send input if provided
            if input_data:
                container.exec_run(f"echo '{input_data}'", stdin=True)

            # wait for execution
            try:
                result = container.wait(timeout=self.max_execution_time)
                exit_code = result["StatusCode"]
            except:
                container.kill()
                return {
                    "status": "timeout",
                    "error": f"Command timed out after {self.max_execution_time} seconds",
                    "output": None,
                    "exit_code": 124,
                    "execution_time_ms": self.max_execution_time * 1000,
                }

            # get output
            logs = container.logs(stdout=True, stderr=True).decode("utf-8")
            execution_time_ms = (time.time() - start_time) * 1000

            status = "completed" if exit_code == 0 else "failed"

            # check for file changes after command execution
            file_changes = await self.sync_files_from_environment(temp_dir, files or {})

            return {
                "status": status,
                "output": logs if logs.strip() else None,
                "error": logs if exit_code != 0 and logs.strip() else None,
                "exit_code": exit_code,
                "execution_time_ms": execution_time_ms,
                "file_changes": file_changes,
            }

        except Exception as e:
            logger.error(f"Terminal command execution error: {str(e)}")
            return {
                "status": "failed",
                "error": f"Command execution error: {str(e)}",
                "output": None,
                "exit_code": 1,
                "execution_time_ms": (time.time() - start_time) * 1000,
            }

        finally:
            # Cleanup
            if container:
                try:
                    container.remove(force=True)
                except:
                    pass

            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    async def _execute_terminal_command_subprocess(
        self,
        command: str,
        session_id: int,
        files: Optional[Dict[str, str]] = None,
        cwd: str = "/workspace",
        input_data: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute terminal command using subprocess (fallback method)"""
        start_time = time.time()
        temp_dir = None

        try:
            # prepping execution environment
            if files is None:
                files = {}

            if files:
                temp_dir = await self.prepare_execution_environment(session_id, files)
            else:
                temp_dir = tempfile.mkdtemp(prefix=f"terminus_session_{session_id}_")

            # sanitizing command
            sanitized_command = self._sanitize_terminal_command(command)
            if not sanitized_command:
                return {
                    "status": "failed",
                    "error": "Command not allowed for security reasons",
                    "output": None,
                    "exit_code": 1,
                    "execution_time_ms": 0,
                }

            # creating environment variables
            env = {
                **os.environ,
                "TERM": "xterm-256color",
                "PS1": "@terminuside:~# ",
                "HOME": temp_dir,
                "SHELL": "/bin/bash",
                "PATH": f"{os.environ.get('PATH', '')}:/usr/local/bin:/usr/bin:/bin",
                "PYTHONPATH": temp_dir,
                "NODE_PATH": f"{temp_dir}/node_modules",
                "NPM_CONFIG_PREFIX": temp_dir,
                "EDITOR": "nano",
                "USER": "terminus",
                "HOSTNAME": "terminuside",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
            }

            # creating a script file to run the command
            script_path = os.path.join(temp_dir, ".run_command.sh")
            with open(script_path, "w") as f:
                f.write("#!/bin/bash\n")
                f.write('export PS1="@terminuside:~# "\n')
                f.write("clear\n")  # Clear screen before running command

                f.write(f"{sanitized_command}\n")
            os.chmod(script_path, 0o755)

            # executing command in subprocess
            process = await asyncio.create_subprocess_exec(
                "bash",
                script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=temp_dir,
                env=env,
            )

            # setting a timeout for execution
            try:
                if input_data:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(input=input_data.encode()),
                        timeout=self.max_execution_time,
                    )
                else:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(), timeout=self.max_execution_time
                    )

                output = stdout.decode() if stdout else ""
                error = stderr.decode() if stderr else ""
                exit_code = process.returncode

            except asyncio.TimeoutError:
                # killing the process if it times out
                try:
                    process.kill()
                except ProcessLookupError:
                    pass

                output = ""
                error = "Execution timed out"
                exit_code = -1

            # calcuating metrics
            execution_time_ms = (time.time() - start_time) * 1000

            # detecting file changes
            original_files = files.copy()
            file_changes = await self.sync_files_from_environment(temp_dir, original_files)

            return {
                "status": "success" if exit_code == 0 else "failed",
                "output": output,
                "error": error,
                "exit_code": exit_code,
                "execution_time_ms": execution_time_ms,
                "file_changes": file_changes,
            }

        except Exception as e:
            logger.error(f"Terminal command execution error: {str(e)}")
            return {
                "status": "failed",
                "error": f"Execution error: {str(e)}",
                "output": None,
                "exit_code": 1,
                "execution_time_ms": (time.time() - start_time) * 1000,
                "file_changes": {},
            }

        finally:
            # cleaning up temp directory
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _format_ls_output(self, output: Optional[str]) -> Optional[str]:
        """Format ls output to be more readable"""
        if not output:
            return output

        lines = output.strip().split("\n")
        formatted_lines = []

        for line in lines:
            if line.strip():
                formatted_lines.append(line)

        return "\n".join(formatted_lines)

    def _sanitize_terminal_command(self, command: str) -> Optional[str]:
        """
        Sanitize terminal commands for security
        Returns sanitized command or None if not allowed
        """
        # removing dangerous characters and commands
        dangerous_patterns = [
            "rm -rf /",
            "rm -rf /*",
            ":(){ :|:& };:",
            "dd if=",
            "mkfs",
            "fdisk",
            "mount",
            "umount",
            "sudo",
            "su",
            "passwd",
            "useradd",
            "userdel",
            "chmod 777",
            "wget",
            "curl http",
            "nc ",
            "netcat",
            "ssh",
            ">/dev/",
            "2>/dev/",
            "&>",
            "||",
            "&&",
        ]

        command_lower = command.lower()
        for pattern in dangerous_patterns:
            if pattern in command_lower:
                return None

        # allowing specific safe commands
        safe_commands = [
            "ls",
            "cat",
            "python",
            "python3",
            "pip",
            "pip3",
            "pip install",
            "echo",
            "pwd",
            "head",
            "tail",
            "grep",
            "find",
            "wc",
            "sort",
            "uniq",
            "cd",
            "mkdir",
            "touch",
            "cp",
            "mv",
            "tree",
            "file",
            "which",
            "env",
            "export",
            "alias",
            "history",
            "clear",
            "help",
            "man",
            "nano",
            "vim",
            "emacs",
            "less",
            "more",
            "basename",
            "dirname",
            "whoami",
            "date",
            "uptime",
            "df",
            "du",
            "free",
            "ps",
            "top",
            "npm",
            "node",
            "git",
            "make",
            "cmake",
            "gcc",
            "g++",
            "javac",
            "java",
        ]

        # checking if command starts with safe command
        for safe_cmd in safe_commands:
            if command_lower.startswith(safe_cmd):
                return command

        # default deny
        return None

    def _extract_method_name(self, code: str) -> str:
        """Extract the method name from a Solution class"""
        import re

        # looking for method definitions in the Solution class
        # pattern matches: def methodName(self, ...):
        pattern = r"def\s+(\w+)\s*\(\s*self"
        matches = re.findall(pattern, code)

        if matches:
            # returning the first method name found
            return matches[0]
        else:
            # default to a common method name if none found
            return "longestSubarray"


# singleton instance
code_execution_service = CodeExecutionService()
