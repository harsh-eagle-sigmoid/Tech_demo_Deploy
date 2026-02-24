"""
Safe SQL query executor with timeout and result normalization
"""
import psycopg2
import psycopg2.extras
import sqlite3
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from loguru import logger
from urllib.parse import urlparse

# Optional database connectors
try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

try:
    from pymongo import MongoClient
    HAS_MONGO = True
except ImportError:
    HAS_MONGO = False


@dataclass
class ExecutionResult:
    """Result of SQL execution"""
    success: bool
    columns: Optional[List[str]] = None
    rows: Optional[List[Tuple]] = None
    row_count: int = 0
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None


class TimeoutException(Exception):
    """Raised when query execution times out"""
    pass


class QueryExecutor:
    """
    Safely execute SQL queries with timeouts and result normalization.
    Supports PostgreSQL, MySQL, SQLite, MongoDB.
    """

    def __init__(self, timeout_seconds: int = 10, max_rows: int = 10000):
        """
        Args:
            timeout_seconds: Max execution time per query
            max_rows: Max rows to fetch (prevent memory issues)
        """
        self.timeout_seconds = timeout_seconds
        self.max_rows = max_rows

    def execute(self, sql: str, db_url: str) -> ExecutionResult:
        """
        Execute SQL query safely and return normalized results.

        Args:
            sql: SQL query to execute
            db_url: Database connection URL

        Returns:
            ExecutionResult with columns, rows, and metadata
        """
        # Validate SQL is read-only
        if not self._is_read_only(sql):
            return ExecutionResult(
                success=False,
                error="Query contains unsafe operations (only SELECT allowed)"
            )

        # Parse database type from URL
        db_type = self._get_db_type(db_url)

        # Execute based on database type
        try:
            if db_type == 'postgresql':
                return self._execute_postgres(sql, db_url)
            elif db_type == 'mysql':
                return self._execute_mysql(sql, db_url)
            elif db_type == 'sqlite':
                return self._execute_sqlite(sql, db_url)
            elif db_type == 'mongodb':
                return self._execute_mongo(sql, db_url)
            else:
                return ExecutionResult(
                    success=False,
                    error=f"Unsupported database type: {db_type}"
                )
        except TimeoutException as e:
            logger.warning(f"Query timeout: {str(e)}")
            return ExecutionResult(success=False, error=str(e))
        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            return ExecutionResult(success=False, error=str(e))

    def _is_read_only(self, sql: str) -> bool:
        """Check if SQL is read-only (SELECT only)"""
        sql_upper = sql.upper().strip()

        # Must start with SELECT or WITH (for CTEs)
        if not (sql_upper.startswith('SELECT') or sql_upper.startswith('WITH')):
            return False

        # Reject dangerous keywords
        dangerous_keywords = [
            'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
            'TRUNCATE', 'REPLACE', 'MERGE', 'GRANT', 'REVOKE'
        ]

        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                return False

        return True

    def _get_db_type(self, db_url: str) -> str:
        """Extract database type from connection URL"""
        parsed = urlparse(db_url)
        scheme = parsed.scheme.lower()

        if scheme in ['postgres', 'postgresql']:
            return 'postgresql'
        elif scheme == 'mysql':
            return 'mysql'
        elif scheme == 'sqlite':
            return 'sqlite'
        elif scheme == 'mongodb':
            return 'mongodb'
        else:
            return scheme

    def _execute_postgres(self, sql: str, db_url: str) -> ExecutionResult:
        """Execute on PostgreSQL with built-in timeout"""
        import time
        start = time.time()

        try:
            parsed = urlparse(db_url)
            # Use statement_timeout for thread-safe timeout (works in background tasks)
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port or 5432,
                database=parsed.path.lstrip('/'),
                user=parsed.username,
                password=parsed.password,
                options=f'-c statement_timeout={self.timeout_seconds * 1000}'  # milliseconds
            )

            cursor = conn.cursor()
            cursor.execute(sql)

            # Fetch results (limited)
            rows = cursor.fetchmany(self.max_rows)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            execution_time = (time.time() - start) * 1000  # ms

            cursor.close()
            conn.close()

            return ExecutionResult(
                success=True,
                columns=columns,
                rows=rows,
                row_count=len(rows),
                execution_time_ms=execution_time
            )
        except Exception as e:
            return ExecutionResult(success=False, error=str(e))

    def _execute_mysql(self, sql: str, db_url: str) -> ExecutionResult:
        """Execute on MySQL"""
        if not HAS_MYSQL:
            return ExecutionResult(
                success=False,
                error="MySQL connector not installed. Install with: pip install mysql-connector-python"
            )

        import time
        start = time.time()

        try:
            parsed = urlparse(db_url)
            conn = mysql.connector.connect(
                host=parsed.hostname,
                port=parsed.port or 3306,
                database=parsed.path.lstrip('/'),
                user=parsed.username,
                password=parsed.password,
                connection_timeout=self.timeout_seconds
            )

            cursor = conn.cursor()
            cursor.execute(sql)

            rows = cursor.fetchmany(self.max_rows)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            execution_time = (time.time() - start) * 1000

            cursor.close()
            conn.close()

            return ExecutionResult(
                success=True,
                columns=columns,
                rows=rows,
                row_count=len(rows),
                execution_time_ms=execution_time
            )
        except Exception as e:
            return ExecutionResult(success=False, error=str(e))

    def _execute_sqlite(self, sql: str, db_url: str) -> ExecutionResult:
        """Execute on SQLite"""
        import time
        start = time.time()

        try:
            # Extract file path from URL
            parsed = urlparse(db_url)
            db_path = parsed.path

            conn = sqlite3.connect(db_path, timeout=self.timeout_seconds)
            cursor = conn.cursor()
            cursor.execute(sql)

            rows = cursor.fetchmany(self.max_rows)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            execution_time = (time.time() - start) * 1000

            cursor.close()
            conn.close()

            return ExecutionResult(
                success=True,
                columns=columns,
                rows=rows,
                row_count=len(rows),
                execution_time_ms=execution_time
            )
        except Exception as e:
            return ExecutionResult(success=False, error=str(e))

    def _execute_mongo(self, sql: str, db_url: str) -> ExecutionResult:
        """
        Execute on MongoDB (limited - MongoDB uses MQL not SQL).
        This is a placeholder for future MongoDB support.
        """
        if not HAS_MONGO:
            return ExecutionResult(
                success=False,
                error="MongoDB connector not installed. Install with: pip install pymongo"
            )

        return ExecutionResult(
            success=False,
            error="MongoDB query execution not yet implemented"
        )
