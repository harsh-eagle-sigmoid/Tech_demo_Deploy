"""
SQLite-Specific Validator

Implements validation checks for SQLite databases.
"""

import sqlite3
from typing import List, Dict
from loguru import logger
from validation.validators.base_validator import BaseValidator


class SQLiteValidator(BaseValidator):
    """SQLite-specific validator using sqlite3."""

    def __init__(self, agent_id: int, db_url: str):
        super().__init__(agent_id, db_url)
        # Remove sqlite:/// prefix
        self.db_path = db_url.replace('sqlite:///', '').replace('sqlite://', '')

    def connect(self):
        """Create SQLite connection."""
        return sqlite3.connect(self.db_path)

    def disconnect(self, conn):
        """Close SQLite connection."""
        if conn:
            conn.close()

    def check_primary_keys(self, conn, schema_name: str, table_name: str) -> Dict:
        """Check if table has primary key using PRAGMA table_info."""
        cur = conn.cursor()

        cur.execute(f"PRAGMA table_info({table_name})")
        columns = cur.fetchall()
        cur.close()

        # Column format: (cid, name, type, notnull, dflt_value, pk)
        # pk = 1 means it's part of primary key
        pk_columns = [col[1] for col in columns if col[5] == 1]

        return {
            'has_pk': len(pk_columns) > 0,
            'pk_columns': ', '.join(pk_columns) if pk_columns else None
        }

    def check_null_values(self, conn, schema_name: str, table_name: str, column_name: str) -> Dict:
        """Count NULL values in column."""
        cur = conn.cursor()

        cur.execute(f"""
            SELECT
                COUNT(*) as total_rows,
                COUNT(*) - COUNT("{column_name}") as null_count,
                ROUND(
                    (CAST(COUNT(*) - COUNT("{column_name}") AS FLOAT) / NULLIF(COUNT(*), 0)) * 100,
                    2
                ) as percentage
            FROM "{table_name}"
        """)

        result = cur.fetchone()
        cur.close()

        return {
            'total_rows': result[0],
            'null_count': result[1],
            'percentage': float(result[2] or 0)
        }

    def check_duplicates(self, conn, schema_name: str, table_name: str, columns: List[str]) -> Dict:
        """Find duplicate rows."""
        cur = conn.cursor()

        # Limit to first 10 columns
        col_list = ', '.join([f'"{col}"' for col in columns[:10]])

        cur.execute(f"""
            SELECT COUNT(*) FROM (
                SELECT {col_list}
                FROM "{table_name}"
                GROUP BY {col_list}
                HAVING COUNT(*) > 1
            )
        """)

        result = cur.fetchone()
        cur.close()

        return {'count': result[0]}

    def check_table_size(self, conn, schema_name: str, table_name: str) -> Dict:
        """Get table size and row count."""
        cur = conn.cursor()

        # Get row count
        cur.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        row_count = cur.fetchone()[0]

        # Get table size (approximate)
        cur.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
        db_size = cur.fetchone()[0]

        cur.close()

        # Approximate table size (SQLite doesn't have per-table size info)
        return {
            'total_size': f"{db_size / 1024 / 1024:.2f} MB (approx)",
            'row_count': row_count
        }

    def check_indexes(self, conn, schema_name: str, table_name: str) -> Dict:
        """List indexes on table using PRAGMA index_list."""
        cur = conn.cursor()

        cur.execute(f"PRAGMA index_list({table_name})")
        indexes = cur.fetchall()

        # Filter out auto-created indexes
        non_auto_indexes = [
            idx for idx in indexes
            if not idx[1].startswith('sqlite_autoindex_')
        ]

        index_details = []
        for idx in non_auto_indexes:
            index_name = idx[1]

            # Get index columns
            cur.execute(f"PRAGMA index_info({index_name})")
            columns = cur.fetchall()

            index_details.append({
                'name': index_name,
                'columns': ', '.join([col[2] for col in columns])
            })

        cur.close()

        return {
            'count': len(index_details),
            'indexes': index_details
        }
