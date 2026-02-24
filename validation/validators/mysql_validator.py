"""
MySQL-Specific Validator

Implements validation checks for MySQL databases.
"""

from urllib.parse import urlparse
from typing import List, Dict
from loguru import logger
from validation.validators.base_validator import BaseValidator


class MySQLValidator(BaseValidator):
    """MySQL-specific validator using information_schema."""

    def connect(self):
        """Create MySQL connection."""
        try:
            import mysql.connector

            parsed = urlparse(self.db_url)
            return mysql.connector.connect(
                host=parsed.hostname,
                port=parsed.port or 3306,
                user=parsed.username,
                password=parsed.password,
                database=parsed.path.lstrip('/') if parsed.path else None
            )
        except ImportError:
            logger.error("mysql-connector-python not installed")
            raise

    def disconnect(self, conn):
        """Close MySQL connection."""
        if conn:
            conn.close()

    def check_primary_keys(self, conn, schema_name: str, table_name: str) -> Dict:
        """Check if table has primary key."""
        cur = conn.cursor()

        cur.execute("""
            SELECT COLUMN_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = %s
                AND TABLE_NAME = %s
                AND CONSTRAINT_NAME = 'PRIMARY'
        """, (schema_name, table_name))

        result = cur.fetchall()
        cur.close()

        return {
            'has_pk': len(result) > 0,
            'pk_columns': ', '.join([row[0] for row in result]) if result else None
        }

    def check_null_values(self, conn, schema_name: str, table_name: str, column_name: str) -> Dict:
        """Count NULL values using MySQL syntax."""
        cur = conn.cursor()

        # Use backticks for MySQL identifiers
        cur.execute(f"""
            SELECT
                COUNT(*) as total_rows,
                COUNT(*) - COUNT(`{column_name}`) as null_count,
                ROUND(
                    ((COUNT(*) - COUNT(`{column_name}`)) / NULLIF(COUNT(*), 0)) * 100,
                    2
                ) as percentage
            FROM `{schema_name}`.`{table_name}`
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

        col_list = ', '.join([f'`{col}`' for col in columns[:10]])

        cur.execute(f"""
            SELECT COUNT(*) FROM (
                SELECT {col_list}
                FROM `{schema_name}`.`{table_name}`
                GROUP BY {col_list}
                HAVING COUNT(*) > 1
            ) AS duplicates
        """)

        result = cur.fetchone()
        cur.close()

        return {'count': result[0]}

    def check_table_size(self, conn, schema_name: str, table_name: str) -> Dict:
        """Get table size from information_schema."""
        cur = conn.cursor()

        cur.execute("""
            SELECT
                CONCAT(ROUND(DATA_LENGTH / 1024 / 1024, 2), ' MB') as total_size,
                TABLE_ROWS as row_count
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s
                AND TABLE_NAME = %s
        """, (schema_name, table_name))

        result = cur.fetchone()
        cur.close()

        return {
            'total_size': result[0] if result else '0 MB',
            'row_count': result[1] if result else 0
        }

    def check_indexes(self, conn, schema_name: str, table_name: str) -> Dict:
        """List indexes using SHOW INDEX."""
        cur = conn.cursor()

        cur.execute(f"SHOW INDEX FROM `{schema_name}`.`{table_name}`")

        indexes = cur.fetchall()
        cur.close()

        # Group by index name and exclude PRIMARY
        unique_indexes = {}
        for idx in indexes:
            index_name = idx[2]
            if index_name != 'PRIMARY' and index_name not in unique_indexes:
                unique_indexes[index_name] = {'name': index_name}

        return {
            'count': len(unique_indexes),
            'indexes': list(unique_indexes.values())
        }
