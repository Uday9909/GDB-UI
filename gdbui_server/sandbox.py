"""Per-session Docker container management for GDB sandboxing.

Each session gets a dedicated container with read-only rootfs and no network.
GDB and g++ are invoked via ``docker exec``. The session's output directory
is bind-mounted at /workspace so compiled binaries are immediately available.

Usage::

    from sandbox import start_container, stop_container

    name = start_container(session_id, output_dir)
    if name:
        GdbController(command=["docker", "exec", "-i", name, "gdb", "--interpreter=mi2"])
    stop_container(session_id)
"""

from __future__ import annotations

import logging
import os
import subprocess

logger = logging.getLogger(__name__)

SANDBOX_ENABLED = os.environ.get("GDBUI_DOCKER", "").lower() in ("1", "true", "yes")
SANDBOX_IMAGE = os.environ.get("GDBUI_SANDBOX_IMAGE", "gdbui-sandbox:latest")
CONTAINER_PREFIX = "gdbui-"


def _container_name(session_id: str) -> str:
    """Deterministic container name derived from session id."""
    return f"{CONTAINER_PREFIX}{session_id[:8]}"


def start_container(session_id: str, output_dir: str) -> str | None:
    """Start a sandbox container for *session_id*.

    The container stays alive (``sleep infinity``) until explicitly stopped.
    *output_dir* is bind-mounted at ``/workspace`` inside the container.

    Returns the container name, or ``None`` if sandboxing is disabled.
    """
    if not SANDBOX_ENABLED:
        return None

    name = _container_name(session_id)
    abs_output = os.path.abspath(output_dir)
    try:
        subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "--name",
                name,
                "-v",
                f"{abs_output}:/workspace",
                "--network",
                "none",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=64m",
                SANDBOX_IMAGE,
                "sleep",
                "86400",
            ],
            capture_output=True,
            check=True,
            timeout=30,
        )
        logger.info("Sandbox started: %s (%s)", name, session_id)
        return name
    except Exception:
        logger.exception("Failed to start sandbox for session %s", session_id)
        return None


def stop_container(session_id: str) -> None:
    """Stop and remove the sandbox container for *session_id*.

    Safe to call even if the container was never started or already removed.
    """
    if not SANDBOX_ENABLED:
        return

    name = _container_name(session_id)
    try:
        subprocess.run(
            ["docker", "rm", "-f", name],
            capture_output=True,
            timeout=15,
        )
        logger.info("Sandbox stopped: %s", name)
    except Exception:
        logger.exception("Failed to stop sandbox container %s", name)
