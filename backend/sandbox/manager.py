"""
Sandbox Manager - Phase 4 (M5).

Spins up Docker containers with --network none and resource limits.
"""
from __future__ import annotations
import uuid
import logging
import time
import os
from typing import Any

try:
    import docker
except ImportError:
    docker = None

logger = logging.getLogger(__name__)


class SandboxManager:
    """
    Creates, manages, and destroys isolated Docker sandboxes.
    """

    def __init__(self):
        self.client = None
        if docker:
            try:
                self.client = docker.from_env()
            except Exception as e:
                logger.warning("Docker daemon not reachable: %s. Using subprocess fallback.", e)
        self._active_sandboxes: dict[str, Any] = {}

    def create_sandbox(
        self,
        task_id: str,
        image: str = "python:3.11-slim",
        memory_mb: int = 256,
        cpu_quota: float = 0.5,
    ) -> str:
        """
        Spawn a container for task_id with --network none.
        Returns the sandbox_id.
        """
        if not self.client:
            logger.warning("Docker SDK not installed. Falling back to subprocess.")
            return f"subprocess-{uuid.uuid4().hex}"

        sandbox_id = f"sandbox-_{task_id}-{uuid.uuid4().hex[:8]}"
        try:
            container = self.client.containers.run(
                image,
                command="tail -f /dev/null", # Keep alive
                name=sandbox_id,
                detach=True,
                network_mode="none",
                mem_limit=f"{memory_mb}m",
                cpu_quota=int(cpu_quota * 100000),
                cpu_period=100000,
            )
            self._active_sandboxes[sandbox_id] = container
            logger.info("Created sandbox %s for task %s", sandbox_id, task_id)
            return sandbox_id
        except Exception as e:
            logger.error("Failed to create sandbox: %s", e)
            raise RuntimeError(f"Sandbox creation failed: {e}")

    def execute_in_sandbox(
        self,
        sandbox_id: str,
        code: str,
        timeout_seconds: int = 30,
    ) -> dict:
        """
        Execute arbitrary Python code inside the sandbox.
        """
        if sandbox_id.startswith("subprocess-") or not self.client:
            return self.execute_python(code, timeout_seconds)

        container = self._active_sandboxes.get(sandbox_id)
        if not container:
            raise ValueError(f"Sandbox {sandbox_id} not found.")

        try:
            # Write code to a tmp file inside the container
            import tarfile
            import io
            
            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode='w') as tar:
                code_bytes = code.encode('utf-8')
                tarinfo = tarfile.TarInfo(name='script.py')
                tarinfo.size = len(code_bytes)
                tarinfo.mtime = int(time.time())
                tar.addfile(tarinfo, io.BytesIO(code_bytes))
            
            tar_stream.seek(0)
            container.put_archive("/tmp", tar_stream)

            # Exec run
            exec_res = container.exec_run(
                ["python", "/tmp/script.py"],
            )
            
            stdout_text = exec_res.output.decode('utf-8', 'replace')
            return {
                "stdout": stdout_text if exec_res.exit_code == 0 else "",
                "stderr": stdout_text if exec_res.exit_code != 0 else "",
                "exit_code": exec_res.exit_code,
            }
        except Exception as e:
            logger.error("Failed to execute in sandbox %s: %s", sandbox_id, e)
            return {
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
            }

    def destroy_sandbox(self, sandbox_id: str) -> None:
        """
        Forcefully remove the container.
        """
        if sandbox_id.startswith("subprocess-") or not self.client:
            return
            
        container = self._active_sandboxes.pop(sandbox_id, None)
        if container:
            try:
                container.stop(timeout=1)
                container.remove(force=True)
                logger.info("Destroyed sandbox %s", sandbox_id)
            except Exception as e:
                logger.error("Failed to destroy sandbox %s: %s", sandbox_id, e)

    def execute_python(self, code: str, timeout_seconds: int = 10) -> dict:
        """
        Subprocess fallback.
        """
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tf:
            tf.write(code)
            temp_path = tf.name

        try:
            result = subprocess.run(
                ["python", temp_path],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "stdout": exc.stdout.decode("utf-8", "replace") if exc.stdout else "",
                "stderr": f"Execution timed out after {timeout_seconds}s.",
                "exit_code": -1,
            }
        except Exception as exc:
            return {
                "stdout": "",
                "stderr": str(exc),
                "exit_code": -1,
            }
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


# Module-level singleton
sandbox_manager = SandboxManager()