from __future__ import annotations

import asyncio
import io
import traceback
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from typing import Dict, Optional

# Maximum execution time for Python code (seconds)
DEFAULT_TIMEOUT = 30.0


@dataclass
class PythonExecutionResult:
    stdout: str
    stderr: str
    error: Optional[str]


def _execute_python_sync(code: str, global_ctx: Dict[str, object]) -> PythonExecutionResult:
    """Synchronous Python execution - runs in thread pool."""
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    try:
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            exec(code, global_ctx)
        return PythonExecutionResult(
            stdout=stdout_buffer.getvalue(),
            stderr=stderr_buffer.getvalue(),
            error=None,
        )
    except Exception:
        err = traceback.format_exc()
        return PythonExecutionResult(
            stdout=stdout_buffer.getvalue(),
            stderr=stderr_buffer.getvalue(),
            error=err,
        )


async def execute_python(
    code: str,
    global_ctx: Dict[str, object],
    timeout: float = DEFAULT_TIMEOUT,
) -> PythonExecutionResult:
    """Execute Python code with timeout protection.

    Args:
        code: Python code to execute
        global_ctx: Global context dictionary for exec()
        timeout: Maximum execution time in seconds (default: 30.0)

    Returns:
        PythonExecutionResult with stdout, stderr, and optional error
    """
    try:
        # Run in thread pool to avoid blocking event loop
        async with asyncio.timeout(timeout):
            result = await asyncio.to_thread(_execute_python_sync, code, global_ctx)
            return result
    except TimeoutError:
        return PythonExecutionResult(
            stdout="",
            stderr="",
            error=f"Execution timed out after {timeout} seconds",
        )
    except Exception as exc:
        return PythonExecutionResult(
            stdout="",
            stderr="",
            error=f"Unexpected error during execution: {exc}",
        )


