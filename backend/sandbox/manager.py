"""
Sandbox Manager — Phase 0 scaffold (M5).

In Phase 4 this will spin up Docker containers with --network none
and resource limits as described in architecture §10.
"""
from __future__ import annotations
import uuid


class SandboxManager:
    """
    Creates, manages, and destroys isolated Docker sandboxes.

    Phase 0: stub — all methods raise NotImplementedError.
    Phase 4: full Docker API integration with resource limits.
    """

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
        TODO Phase 4.
        """
        raise NotImplementedError("Sandbox creation implemented in Phase 4.")

    def execute_in_sandbox(
        self,
        sandbox_id: str,
        code: str,
        timeout_seconds: int = 30,
    ) -> dict:
        """
        Execute arbitrary Python code inside the sandbox.
        Returns {"stdout": str, "stderr": str, "exit_code": int}.
        TODO Phase 4.
        """
        raise NotImplementedError("Sandbox execution implemented in Phase 4.")

    def destroy_sandbox(self, sandbox_id: str) -> None:
        """
        Forcefully remove the container and clean up its working directory.
        TODO Phase 4.
        """
        raise NotImplementedError("Sandbox destruction implemented in Phase 4.")

    def execute_python(self, code: str) -> dict:
        """
        Phase 2 bare version (no sandbox): runs code in a subprocess.
        Replaced by execute_in_sandbox() in Phase 4.
        TODO Phase 2.
        """
        raise NotImplementedError("Bare Python execution implemented in Phase 2.")


# Module-level singleton
sandbox_manager = SandboxManager()
