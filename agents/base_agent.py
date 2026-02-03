"""
Base Agent Class for Text-to-SQL
"""
import psycopg2
from typing import Dict, List, Optional, Tuple
from loguru import logger
from agents.llm_client import LLMClient
from config.settings import settings


class BaseAgent:
    """Base class for Text-to-SQL agents"""

    def __init__(self, schema_name: str, agent_type: str):
        """
        Initialize base agent

        Args:
            schema_name: Database schema name (e.g., 'spend_data')
            agent_type: Agent type ('spend' or 'demand')
        """
        self.schema_name = schema_name
        self.agent_type = agent_type
        self.llm = LLMClient(provider=settings.AGENT_LLM_PROVIDER)

        # Get schema information
        self.schema_info = self._get_schema_info()

        logger.info(f"Initialized {agent_type} agent with schema: {schema_name}")

    def _get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD
        )

    def _get_schema_info(self) -> str:
        """Get database schema information"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            # Get tables in schema
            cursor.execute(f"""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = '{self.schema_name}'
                ORDER BY table_name;
            """)
            tables = [row[0] for row in cursor.fetchall()]

            # Get columns for each table
            schema_info = []
            for table in tables:
                cursor.execute(f"""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = '{self.schema_name}'
                    AND table_name = '{table}'
                    ORDER BY ordinal_position;
                """)
                columns = cursor.fetchall()

                col_info = ", ".join([f"{col[0]} {col[1]}" for col in columns])
                schema_info.append(f"{self.schema_name}.{table}({col_info})")

            cursor.close()
            conn.close()

            return "\n".join(schema_info)

        except Exception as e:
            logger.error(f"Error getting schema info: {e}")
            return ""

    def _validate_sql(self, sql: str) -> Tuple[bool, Optional[str]]:
        """
        Validate SQL syntax

        Returns:
            (is_valid, error_message)
        """
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            # Use EXPLAIN to validate without executing
            cursor.execute(f"EXPLAIN {sql}")

            cursor.close()
            conn.close()
            return True, None

        except Exception as e:
            return False, str(e)

    def _execute_sql(self, sql: str) -> Tuple[List[Dict], Optional[str]]:
        """
        Execute SQL query

        Returns:
            (results, error_message)
        """
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()

            # Convert to list of dicts
            results = [dict(zip(columns, row)) for row in rows]

            cursor.close()
            conn.close()

            return results, None

        except Exception as e:
            logger.error(f"SQL execution error: {e}")
            return [], str(e)

    def generate_sql(self, user_query: str) -> Tuple[str, str]:
        """
        Generate SQL from natural language query

        Args:
            user_query: Natural language query

        Returns:
            (generated_sql, reasoning)
        """
        try:
            # Build prompt
            system_prompt = f"""You are an expert SQL query generator for PostgreSQL.

Database Schema:
{self.schema_info}

Instructions:
1. Generate a valid PostgreSQL SQL query based on the user's question
2. Use proper table references with schema name (e.g., {self.schema_name}.table_name)
3. Return ONLY the SQL query without any explanations or markdown
4. Use appropriate JOINs, WHERE clauses, GROUP BY, ORDER BY as needed
5. For aggregations, use proper SQL aggregate functions (SUM, AVG, COUNT, etc.)
6. Always limit results to 100 rows unless specified otherwise

Return format:
SQL: <your sql query here>
"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ]

            response = self.llm.generate(
                messages=messages,
                temperature=0.0,  # Deterministic for SQL generation
                max_tokens=1000
            )

            # Extract SQL from response
            sql = self._extract_sql(response)

            return sql, response

        except Exception as e:
            logger.error(f"Error generating SQL: {e}")
            return "", str(e)

    def _extract_sql(self, response: str) -> str:
        """Extract SQL query from LLM response"""
        # Remove markdown code blocks if present
        sql = response.strip()

        if "```sql" in sql:
            sql = sql.split("```sql")[1].split("```")[0].strip()
        elif "```" in sql:
            sql = sql.split("```")[1].split("```")[0].strip()

        # Extract SQL: prefix if present
        if "SQL:" in sql:
            sql = sql.split("SQL:")[1].strip()

        return sql.strip()

    def process_query(self, user_query: str) -> Dict:
        """
        Process user query end-to-end

        Args:
            user_query: Natural language query

        Returns:
            Dict with query, sql, results, and status
        """
        result = {
            "query": user_query,
            "sql": None,
            "results": [],
            "status": "success",
            "error": None,
            "reasoning": None
        }

        try:
            # Step 1: Generate SQL
            logger.info(f"Processing query: {user_query}")
            sql, reasoning = self.generate_sql(user_query)

            if not sql:
                result["status"] = "error"
                result["error"] = "Failed to generate SQL"
                return result

            result["sql"] = sql
            result["reasoning"] = reasoning

            # Step 2: Validate SQL
            is_valid, validation_error = self._validate_sql(sql)

            if not is_valid:
                result["status"] = "error"
                result["error"] = f"SQL validation failed: {validation_error}"
                return result

            # Step 3: Execute SQL
            results, execution_error = self._execute_sql(sql)

            if execution_error:
                result["status"] = "error"
                result["error"] = f"SQL execution failed: {execution_error}"
                return result

            result["results"] = results
            result["status"] = "success"

            logger.info(f"Query processed successfully. Returned {len(results)} rows.")

            return result

        except Exception as e:
            logger.error(f"Error processing query: {e}")
            result["status"] = "error"
            result["error"] = str(e)
            return result
