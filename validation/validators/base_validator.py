"""
Base Validator Interface

Abstract base class for database-specific validators.
All validators must implement these methods.
"""

from abc import ABC, abstractmethod
from typing import List, Dict
from loguru import logger


class BaseValidator(ABC):
    """Abstract base class for database-specific validators."""

    def __init__(self, agent_id: int, db_url: str):
        self.agent_id = agent_id
        self.db_url = db_url
        self.issues = []

    @abstractmethod
    def connect(self):
        """Create database connection."""
        pass

    @abstractmethod
    def disconnect(self, conn):
        """Close database connection."""
        pass

    @abstractmethod
    def check_primary_keys(self, conn, schema_name: str, table_name: str) -> Dict:
        """
        Check if table has primary key.

        Returns:
            {
                'has_pk': bool,
                'pk_columns': str (comma-separated column names)
            }
        """
        pass

    @abstractmethod
    def check_null_values(self, conn, schema_name: str, table_name: str, column_name: str) -> Dict:
        """
        Count NULL values in column.

        Returns:
            {
                'total_rows': int,
                'null_count': int,
                'percentage': float
            }
        """
        pass

    @abstractmethod
    def check_duplicates(self, conn, schema_name: str, table_name: str, columns: List[str]) -> Dict:
        """
        Find duplicate rows.

        Returns:
            {
                'count': int (number of duplicate groups)
            }
        """
        pass

    @abstractmethod
    def check_table_size(self, conn, schema_name: str, table_name: str) -> Dict:
        """
        Get table size and row count.

        Returns:
            {
                'total_size': str (human-readable size),
                'row_count': int
            }
        """
        pass

    @abstractmethod
    def check_indexes(self, conn, schema_name: str, table_name: str) -> Dict:
        """
        List all indexes on table.

        Returns:
            {
                'count': int,
                'indexes': List[Dict] (name, columns, etc.)
            }
        """
        pass

    def validate_all(self, discovered_schemas: dict) -> List[Dict]:
        """
        Run all validation checks on discovered schemas.

        Args:
            discovered_schemas: Dict like {"schema.table": {"col": "type"}}

        Returns:
            List of validation issues
        """
        logger.info(f"Starting validation for agent {self.agent_id}")

        try:
            conn = self.connect()

            for full_table_name, columns in discovered_schemas.items():
                # Parse schema and table name
                if '.' in full_table_name:
                    schema_name, table_name = full_table_name.split('.', 1)
                else:
                    schema_name = 'public'  # Default schema
                    table_name = full_table_name

                # Run validation checks for this table
                self._validate_table(conn, schema_name, table_name, columns)

            self.disconnect(conn)

            logger.info(f"Validation complete: {len(self.issues)} issues found")
            return self.issues

        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return self.issues

    def _validate_table(self, conn, schema_name: str, table_name: str, columns: dict):
        """Run all checks for a single table."""

        # 1. Check for primary key
        try:
            pk_result = self.check_primary_keys(conn, schema_name, table_name)
            if not pk_result.get('has_pk'):
                self.issues.append({
                    'agent_id': self.agent_id,
                    'schema_name': schema_name,
                    'table_name': table_name,
                    'column_name': None,
                    'issue_type': 'missing_primary_key',
                    'severity': 'warning',
                    'message': f"Table {schema_name}.{table_name} has no primary key",
                    'details': {},
                    'affected_rows': None,
                    'total_rows': None,
                    'percentage': None
                })
        except Exception as e:
            logger.debug(f"Primary key check failed for {schema_name}.{table_name}: {e}")

        # 2. Check NULL values in each column
        for col_name in columns.keys():
            try:
                null_result = self.check_null_values(conn, schema_name, table_name, col_name)

                # Report if >20% NULL values
                if null_result and null_result['percentage'] > 20:
                    self.issues.append({
                        'agent_id': self.agent_id,
                        'schema_name': schema_name,
                        'table_name': table_name,
                        'column_name': col_name,
                        'issue_type': 'high_null_percentage',
                        'severity': 'warning',
                        'message': f"Column '{col_name}' has {null_result['percentage']:.1f}% NULL values",
                        'details': null_result,
                        'affected_rows': null_result['null_count'],
                        'total_rows': null_result['total_rows'],
                        'percentage': null_result['percentage']
                    })
            except Exception as e:
                logger.debug(f"NULL check failed for {schema_name}.{table_name}.{col_name}: {e}")

        # 3. Check for duplicate rows
        try:
            dup_result = self.check_duplicates(conn, schema_name, table_name, list(columns.keys()))

            if dup_result and dup_result['count'] > 0:
                self.issues.append({
                    'agent_id': self.agent_id,
                    'schema_name': schema_name,
                    'table_name': table_name,
                    'column_name': None,
                    'issue_type': 'duplicate_rows',
                    'severity': 'info',
                    'message': f"{dup_result['count']} duplicate row groups found",
                    'details': dup_result,
                    'affected_rows': dup_result['count'],
                    'total_rows': None,
                    'percentage': None
                })
        except Exception as e:
            logger.debug(f"Duplicate check failed for {schema_name}.{table_name}: {e}")

        # 4. Check table size and indexes
        try:
            size_result = self.check_table_size(conn, schema_name, table_name)

            # If large table (>100K rows), check if it has indexes
            if size_result and size_result['row_count'] > 100000:
                index_result = self.check_indexes(conn, schema_name, table_name)

                if index_result['count'] == 0:
                    self.issues.append({
                        'agent_id': self.agent_id,
                        'schema_name': schema_name,
                        'table_name': table_name,
                        'column_name': None,
                        'issue_type': 'large_table_no_index',
                        'severity': 'warning',
                        'message': f"Large table ({size_result['row_count']:,} rows) with no indexes",
                        'details': {'size': size_result['total_size'], 'rows': size_result['row_count']},
                        'affected_rows': size_result['row_count'],
                        'total_rows': size_result['row_count'],
                        'percentage': None
                    })
        except Exception as e:
            logger.debug(f"Size/index check failed for {schema_name}.{table_name}: {e}")
