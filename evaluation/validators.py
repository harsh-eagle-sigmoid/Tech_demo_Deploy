
import re
import psycopg2
from typing import Tuple, Optional
from loguru import logger
from config.settings import settings


class StructuralValidator:
    

    def __init__(self, schema_name: str):
        
        self.schema_name = schema_name
        self.schema_info = self._get_schema_info()

    def _get_db_connection(self):
        
        return psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD
        )

    def _get_schema_info(self) -> dict:
        
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            # Get tables
            cursor.execute(f"""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = '{self.schema_name}'
            """)
            tables = [row[0] for row in cursor.fetchall()]

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

    def validate_syntax(self, sql: str) -> Tuple[bool, Optional[str]]:
        
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            # Use EXPLAIN to validate without executing
            cursor.execute(f"EXPLAIN {sql}")

            cursor.close()
            conn.close()

            return True, None

        except Exception as e:
            error_msg = str(e)
            logger.warning(f"SQL syntax validation failed: {error_msg}")
            return False, error_msg

    def validate_schema(self, sql: str) -> Tuple[bool, list]:
        
        errors = []

        
        table_pattern = rf"{self.schema_name}\.(\w+)"
        tables_in_query = re.findall(table_pattern, sql, re.IGNORECASE)

        
        for table in tables_in_query:
            if table not in self.schema_info:
                errors.append(f"Table '{table}' does not exist in schema '{self.schema_name}'")

        # Extract column names (basic pattern)
        # This is a simplified check - more sophisticated parsing can be added
        for table in tables_in_query:
            if table in self.schema_info:
                # Check for explicit column references like table.column
                col_pattern = rf"{table}\.(\w+)"
                columns_in_query = re.findall(col_pattern, sql, re.IGNORECASE)

                for col in columns_in_query:
                    if col not in self.schema_info[table]:
                        errors.append(f"Column '{col}' does not exist in table '{table}'")

        is_valid = len(errors) == 0
        return is_valid, errors

    def validate(self, sql: str) -> dict:
        
        result = {
            "valid": False,
            "syntax_valid": False,
            "schema_valid": False,
            "errors": [],
            "score": 0.0
        }

        
        syntax_valid, syntax_error = self.validate_syntax(sql)
        result["syntax_valid"] = syntax_valid

        if not syntax_valid:
            result["errors"].append(f"Syntax error: {syntax_error}")
            result["score"] = 0.0
            return result

        
        schema_valid, schema_errors = self.validate_schema(sql)
        result["schema_valid"] = schema_valid

        if not schema_valid:
            result["errors"].extend(schema_errors)
            result["score"] = 0.5  
            return result

        
        result["valid"] = True
        result["score"] = 1.0

        return result
