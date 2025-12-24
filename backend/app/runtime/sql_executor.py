from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import asyncpg

# Maximum number of rows to return from SQL queries
DEFAULT_ROW_LIMIT = 1000

# Pattern to match {{variable}} placeholders
PLACEHOLDER_PATTERN = re.compile(r"\{\{(\s*[a-zA-Z_][a-zA-Z0-9_]*\s*)\}\}")


@dataclass
class SqlExecutionResult:
    rows: List[dict[str, Any]]
    status: str
    error: Optional[str]
    row_count: int  # Total rows returned
    truncated: bool  # Whether results were truncated due to row limit


def _substitute_variables(sql_code: str, python_globals: Dict[str, object]) -> tuple[str, Optional[str]]:
    """Substitute {{var}} placeholders with values from Python globals.

    Args:
        sql_code: SQL query with {{var}} placeholders
        python_globals: Python global context dictionary

    Returns:
        Tuple of (substituted_sql, error_message)
        If error_message is not None, substitution failed
    """
    def replace_placeholder(match: re.Match[str]) -> str:
        var_name = match.group(1).strip()
        if var_name not in python_globals:
            raise KeyError(f"Variable '{var_name}' not found in Python context")

        value = python_globals[var_name]

        # Convert Python value to SQL literal
        if value is None:
            return "NULL"
        elif isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            # Escape single quotes by doubling them (SQL standard)
            escaped = value.replace("'", "''")
            return f"'{escaped}'"
        elif isinstance(value, (list, tuple)):
            # Convert list/tuple to SQL array literal
            elements = [str(v) if isinstance(v, (int, float)) else f"'{str(v)}'" for v in value]
            return f"({', '.join(elements)})"
        else:
            # For other types, convert to string and quote
            escaped = str(value).replace("'", "''")
            return f"'{escaped}'"

    try:
        substituted = PLACEHOLDER_PATTERN.sub(replace_placeholder, sql_code)
        return substituted, None
    except KeyError as exc:
        return sql_code, str(exc)
    except Exception as exc:
        return sql_code, f"Variable substitution error: {exc}"


async def execute_sql(
    pool: asyncpg.Pool,
    code: str,
    python_globals: Dict[str, object],
    row_limit: int = DEFAULT_ROW_LIMIT,
) -> SqlExecutionResult:
    """Execute SQL query using connection pool with row limit and variable substitution.

    Args:
        pool: asyncpg connection pool
        code: SQL query to execute (may contain {{var}} placeholders)
        python_globals: Python global context for variable substitution
        row_limit: Maximum number of rows to return (default: 1000)

    Returns:
        SqlExecutionResult with query results or error
    """
    # Substitute {{var}} placeholders with Python variables
    substituted_sql, subst_error = _substitute_variables(code, python_globals)
    print(f"[DEBUG] SQL substitution - Original: {code[:100]}...")
    print(f"[DEBUG] Available Python vars: {list(python_globals.keys())}")
    if subst_error:
        print(f"[DEBUG] Substitution error: {subst_error}")
        return SqlExecutionResult(
            rows=[],
            status="substitution_error",
            error=subst_error,
            row_count=0,
            truncated=False,
        )
    print(f"[DEBUG] Substituted SQL: {substituted_sql[:100]}...")

    try:
        async with pool.acquire() as conn:
            # Fetch up to row_limit + 1 to detect truncation
            rows = await conn.fetch(substituted_sql, timeout=30.0)

            truncated = len(rows) > row_limit
            limited_rows = rows[:row_limit] if truncated else rows
            parsed = [dict(row) for row in limited_rows]

            return SqlExecutionResult(
                rows=parsed,
                status="ok",
                error=None,
                row_count=len(parsed),
                truncated=truncated,
            )
    except asyncpg.PostgresError as exc:
        return SqlExecutionResult(
            rows=[],
            status="query_error",
            error=f"PostgreSQL error: {exc}",
            row_count=0,
            truncated=False,
        )
    except asyncio.TimeoutError:
        return SqlExecutionResult(
            rows=[],
            status="timeout_error",
            error="Query execution timed out after 30 seconds",
            row_count=0,
            truncated=False,
        )
    except Exception as exc:
        return SqlExecutionResult(
            rows=[],
            status="execution_error",
            error=f"Unexpected error: {exc}",
            row_count=0,
            truncated=False,
        )


