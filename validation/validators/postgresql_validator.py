"""
PostgreSQL-Specific Validator

Implements validation checks for PostgreSQL databases.
"""

import psycopg2
from typing import List, Dict
from loguru import logger
from validation.validators.base_validator import BaseValidator


class PostgreSQLValidator(BaseValidator):
    """PostgreSQL-specific validator using pg_catalog and information_schema."""

    def connect(self):
        """Create PostgreSQL connection."""
        return psycopg2.connect(self.db_url)

    def disconnect(self, conn):
        """Close PostgreSQL connection."""
        if conn:
            conn.close()

    def check_primary_keys(self, conn, schema_name: str, table_name: str) -> Dict:
        """Check if table has primary key using information_schema."""
        cur = conn.cursor()

        cur.execute("""
            SELECT
                tc.constraint_name,
                string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) as pk_columns
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
                AND tc.table_name = kcu.table_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_schema = %s
                AND tc.table_name = %s
            GROUP BY tc.constraint_name
        """, (schema_name, table_name))

        result = cur.fetchone()
        cur.close()

        return {
            'has_pk': result is not None,
            'pk_columns': result[1] if result else None
        }

    def check_null_values(self, conn, schema_name: str, table_name: str, column_name: str) -> Dict:
        """Count NULL values using PostgreSQL casting syntax."""
        cur = conn.cursor()

        # Use :: for PostgreSQL casting
        cur.execute(f"""
            SELECT
                COUNT(*) as total_rows,
                COUNT(*) - COUNT("{column_name}") as null_count,
                ROUND(
                    ((COUNT(*) - COUNT("{column_name}"))::DECIMAL / NULLIF(COUNT(*), 0)) * 100,
                    2
                ) as percentage
            FROM "{schema_name}"."{table_name}"
        """)

        result = cur.fetchone()
        cur.close()

        return {
            'total_rows': result[0],
            'null_count': result[1],
            'percentage': float(result[2] or 0)
        }

    def check_duplicates(self, conn, schema_name: str, table_name: str, columns: List[str]) -> Dict:
        """Find duplicate rows using GROUP BY HAVING."""
        cur = conn.cursor()

        # Quote column names to handle special characters
        col_list = ', '.join([f'"{col}"' for col in columns[:10]])  # Limit to first 10 columns

        cur.execute(f"""
            SELECT COUNT(*) FROM (
                SELECT {col_list}
                FROM "{schema_name}"."{table_name}"
                GROUP BY {col_list}
                HAVING COUNT(*) > 1
            ) AS duplicates
        """)

        result = cur.fetchone()
        cur.close()

        return {'count': result[0]}

    def check_table_size(self, conn, schema_name: str, table_name: str) -> Dict:
        """Get table size using PostgreSQL-specific pg_total_relation_size()."""
        cur = conn.cursor()

        cur.execute(f"""
            SELECT
                pg_size_pretty(pg_total_relation_size('"{schema_name}"."{table_name}"')) as total_size,
                (SELECT COUNT(*) FROM "{schema_name}"."{table_name}") as row_count
        """)

        result = cur.fetchone()
        cur.close()

        return {
            'total_size': result[0],
            'row_count': result[1]
        }

    def check_indexes(self, conn, schema_name: str, table_name: str) -> Dict:
        """List indexes using pg_indexes."""
        cur = conn.cursor()

        cur.execute("""
            SELECT
                indexname,
                indexdef
            FROM pg_indexes
            WHERE schemaname = %s
                AND tablename = %s
                AND indexname NOT LIKE '%_pkey'  -- Exclude primary key index
        """, (schema_name, table_name))

        indexes = cur.fetchall()
        cur.close()

        return {
            'count': len(indexes),
            'indexes': [
                {
                    'name': idx[0],
                    'definition': idx[1]
                }
                for idx in indexes
            ]
        }
