"""
Enhanced Ground Truth Generator
Generates GT with query, SQL, AND expected output for accurate validation
"""
import json
import psycopg2
from typing import Dict, List, Tuple, Optional
from loguru import logger
from datetime import datetime, date
from decimal import Decimal


def json_serial(obj):
    """JSON serializer for objects not serializable by default"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


class GTGenerator:
    """
    Enhanced Ground Truth Generator
    Executes SQL queries and stores their outputs for accurate validation
    """

    def __init__(self, db_url: str):
        """
        Initialize GT Generator

        Args:
            db_url: Database connection URL for executing queries
        """
        self.db_url = db_url
        logger.info(f"Initialized GTGenerator with DB URL: {db_url[:30]}...")

    def execute_sql(self, sql: str, timeout_ms: int = 5000) -> Dict:
        """
        Execute SQL query and capture output

        Args:
            sql: SQL query to execute
            timeout_ms: Query timeout in milliseconds

        Returns:
            Dict with execution results
        """
        try:
            # Parse connection URL
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()

            # Set statement timeout
            cursor.execute(f"SET statement_timeout = {timeout_ms}")

            # Execute query
            start_time = datetime.now()
            cursor.execute(sql)
            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            # Fetch results
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall() if cursor.description else []
            row_count = len(rows)

            cursor.close()
            conn.close()

            # Convert rows to serializable format
            serialized_rows = []
            for row in rows[:20]:  # Store first 20 rows as sample
                serialized_row = []
                for val in row:
                    if isinstance(val, Decimal):
                        serialized_row.append(float(val))
                    elif isinstance(val, (datetime, date)):
                        serialized_row.append(val.isoformat())
                    else:
                        serialized_row.append(val)
                serialized_rows.append(serialized_row)

            return {
                "success": True,
                "columns": columns,
                "rows": serialized_rows,
                "row_count": row_count,
                "execution_time_ms": round(execution_time, 2),
                "error": None
            }

        except psycopg2.OperationalError as e:
            if "timeout" in str(e).lower():
                logger.warning(f"Query timeout after {timeout_ms}ms")
                return {
                    "success": False,
                    "error": f"Query timeout after {timeout_ms}ms",
                    "columns": [],
                    "rows": [],
                    "row_count": 0,
                    "execution_time_ms": timeout_ms
                }
            else:
                logger.error(f"Database connection error: {e}")
                return {
                    "success": False,
                    "error": f"Connection error: {str(e)}",
                    "columns": [],
                    "rows": [],
                    "row_count": 0,
                    "execution_time_ms": 0
                }

        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "columns": [],
                "rows": [],
                "row_count": 0,
                "execution_time_ms": 0
            }

    def generate_gt_entry(
        self,
        query_text: str,
        sql: str,
        complexity: str = "medium"
    ) -> Dict:
        """
        Generate a complete GT entry with output validation

        Args:
            query_text: Natural language query
            sql: SQL query
            complexity: Query complexity level

        Returns:
            Complete GT entry with expected output
        """
        logger.info(f"Generating GT for: {query_text[:60]}...")

        # Execute SQL and capture output
        execution_result = self.execute_sql(sql)

        if not execution_result["success"]:
            logger.warning(f"Failed to execute GT SQL: {execution_result['error']}")
            return {
                "query": query_text,
                "sql": sql,
                "complexity": complexity,
                "expected_output": None,
                "generation_error": execution_result["error"],
                "generated_at": datetime.now().isoformat()
            }

        # Build GT entry with output
        gt_entry = {
            "query": query_text,
            "sql": sql,
            "complexity": complexity,
            "expected_output": {
                "columns": execution_result["columns"],
                "row_count": execution_result["row_count"],
                "sample_rows": execution_result["rows"],
                "execution_time_ms": execution_result["execution_time_ms"]
            },
            "generated_at": datetime.now().isoformat()
        }

        logger.info(
            f"GT generated successfully: {execution_result['row_count']} rows, "
            f"{len(execution_result['columns'])} columns"
        )

        return gt_entry

    def generate_gt_file(
        self,
        queries: List[Tuple[str, str, str]],
        output_file: str
    ) -> bool:
        """
        Generate complete GT file with outputs for multiple queries

        Args:
            queries: List of (query_text, sql, complexity) tuples
            output_file: Path to output JSON file

        Returns:
            True if successful
        """
        logger.info(f"Generating GT file with {len(queries)} queries...")

        gt_entries = []
        success_count = 0
        fail_count = 0

        for query_text, sql, complexity in queries:
            try:
                gt_entry = self.generate_gt_entry(query_text, sql, complexity)
                gt_entries.append(gt_entry)

                if gt_entry.get("expected_output"):
                    success_count += 1
                else:
                    fail_count += 1

            except Exception as e:
                logger.error(f"Failed to generate GT for query: {e}")
                fail_count += 1

        # Save to file
        try:
            with open(output_file, 'w') as f:
                json.dump(gt_entries, f, indent=2, default=json_serial)

            logger.info(
                f"GT file saved: {output_file} "
                f"(Success: {success_count}, Failed: {fail_count})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to save GT file: {e}")
            return False


# Example usage
if __name__ == "__main__":
    # Example: Generate GT file for marketing agent
    db_url = "postgresql://postgres:postgres@localhost:5432/unilever_poc"

    sample_queries = [
        (
            "Show top 10 campaigns by revenue",
            "SELECT campaign_name, revenue FROM marketing_data.campaigns ORDER BY revenue DESC LIMIT 10",
            "medium"
        ),
        (
            "List campaigns with revenue > 100000",
            "SELECT campaign_name, revenue FROM marketing_data.campaigns WHERE revenue > 100000",
            "easy"
        ),
        (
            "Show total revenue per campaign",
            "SELECT campaign_name, SUM(revenue) AS total_revenue FROM marketing_data.campaigns GROUP BY campaign_name",
            "medium"
        ),
    ]

    generator = GTGenerator(db_url)
    generator.generate_gt_file(
        sample_queries,
        "data/ground_truth/marketing_agent_queries_with_output.json"
    )
