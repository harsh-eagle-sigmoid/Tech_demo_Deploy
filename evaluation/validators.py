
import re
import psycopg2
import psycopg2.errors
from typing import Tuple, Optional
from loguru import logger
from config.settings import settings


class StructuralValidator:
    """Validates SQL syntax and schema correctness against the actual PostgreSQL database.
    Stage 1: EXPLAIN-based validation (catches syntax, missing tables/columns)
    Stage 2: Regex-based schema validation (additional cross-check)
    """

    def __init__(self, schema_name: str = None, schema_info: dict = None, db_url: str = None):
        """Load schema metadata from DB or use pre-loaded schema_info dict."""
        self.schema_name = schema_name
        self.db_url = db_url
        if schema_info:
            self.schema_info = schema_info
        elif schema_name:
            self.schema_info = self._get_schema_info()
        else:
            self.schema_info = {}

    def _get_db_connection(self):
        """Create a direct PostgreSQL connection — uses external db_url if set."""
        if self.db_url:
            return psycopg2.connect(self.db_url)
        return psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD
        )

    def _get_schema_info(self) -> dict:
        """Fetch all tables and their columns from the database schema."""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            # Get all table names in this schema
            cursor.execute(f"""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = '{self.schema_name}'
            """)
            tables = [row[0] for row in cursor.fetchall()]

            # For each table, get column names and data types
            schema = {}
            for table in tables:
                cursor.execute(f"""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = '{self.schema_name}'
                    AND table_name = '{table}'
                """)
                schema[table] = {col[0]: col[1] for col in cursor.fetchall()}

            cursor.close()
            conn.close()

            return schema

        except Exception as e:
            logger.error(f"Error getting schema info: {e}")
            return {}

    def validate_syntax(self, sql: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Validate SQL using EXPLAIN — catches syntax errors, missing tables/columns.
        Returns: (is_valid, error_message, error_type)
        error_type: 'SYNTAX_ERROR', 'UNDEFINED_TABLE', 'UNDEFINED_COLUMN', or None
        """
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            # EXPLAIN validates without executing — PostgreSQL parses and plans the query
            cursor.execute(f"EXPLAIN {sql}")

            cursor.close()
            conn.close()

            return True, None, None

        except psycopg2.errors.SyntaxError as e:
            return False, str(e), "SYNTAX_ERROR"

        except psycopg2.errors.UndefinedTable as e:
            return False, str(e), "UNDEFINED_TABLE"

        except psycopg2.errors.UndefinedColumn as e:
            return False, str(e), "UNDEFINED_COLUMN"

        except Exception as e:
            # Other errors (permissions, etc.) don't trigger error classification
            return False, str(e), None

    def validate_schema(self, sql: str) -> Tuple[bool, list]:
        """Regex-based schema validation — checks table/column names against cached schema.
        Supports both qualified (schema.table) and unqualified (table) names.
        """
        errors = []

        # Extract table references from FROM/JOIN clauses
        # Pattern matches: FROM schema.table, FROM table, JOIN schema.table alias, etc.
        table_ref_pattern = r'\b(?:FROM|JOIN)\s+([\w\.]+)(?:\s+\w+)?'
        table_matches = re.findall(table_ref_pattern, sql, re.IGNORECASE)

        # Check each table reference
        for table_ref in table_matches:
            # Could be: 'table', 'schema.table'
            table_exists = False

            if table_ref in self.schema_info:
                # Direct match (qualified or unqualified)
                table_exists = True
            elif '.' not in table_ref:
                # Unqualified table - check if it exists as schema.table anywhere
                for key in self.schema_info.keys():
                    if '.' in key and key.split('.')[-1] == table_ref:
                        table_exists = True
                        break

            if not table_exists:
                errors.append(f"Table '{table_ref}' does not exist in discovered schema")

        # Validate column references (table.column or alias.column)
        # Only validate columns if the table part exists in schema_info
        col_ref_pattern = r'(\w+)\.(\w+)'
        col_matches = re.findall(col_ref_pattern, sql, re.IGNORECASE)

        for first_part, second_part in col_matches:
            # Skip if this is a table reference (FROM/JOIN already validated)
            full_ref = f"{first_part}.{second_part}"
            if full_ref in self.schema_info:
                continue  # This is a table reference, not a column reference

            # Check if first_part is a known table (qualified or unqualified)
            if first_part in self.schema_info:
                # Validate that second_part is a column in this table
                if second_part not in self.schema_info[first_part]:
                    errors.append(f"Column '{second_part}' does not exist in table '{first_part}'")

        is_valid = len(errors) == 0
        return is_valid, errors

    def validate(self, sql: str) -> dict:
        """Run full structural validation: Stage 1 (EXPLAIN) → Stage 2 (regex schema check).
        Returns dict with score, errors, and classification flags.
        """
        result = {
            "valid": False,
            "syntax_valid": False,
            "schema_valid": False,
            "errors": [],
            "score": 0.0,
            "error_type": None,               # Error type for classification (SYNTAX_ERROR, etc.)
            "requires_classification": False   # Flag: should error classifier be called?
        }

        # Stage 1: EXPLAIN-based validation (catches real DB errors)
        syntax_valid, syntax_error, error_type = self.validate_syntax(sql)
        result["syntax_valid"] = syntax_valid

        if not syntax_valid:
            result["errors"].append(syntax_error)
            result["score"] = 0.0
            result["error_type"] = error_type

            # Only trigger error classification for specific error types
            if error_type in ["SYNTAX_ERROR", "UNDEFINED_TABLE", "UNDEFINED_COLUMN"]:
                result["requires_classification"] = True

            return result

        # Stage 2: Regex-based schema validation (additional safety check)
        schema_valid, schema_errors = self.validate_schema(sql)
        result["schema_valid"] = schema_valid

        if not schema_valid:
            result["errors"].extend(schema_errors)
            result["score"] = 0.5  # Partial score — syntax valid but schema mismatch
            return result

        # Both stages passed — SQL is structurally valid
        result["valid"] = True
        result["score"] = 1.0

        return result
