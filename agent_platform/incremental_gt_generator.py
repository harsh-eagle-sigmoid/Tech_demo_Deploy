"""
Generates ground truth queries for NEW schemas only (incremental)
"""
import json
import os
from typing import Dict, List
from datetime import datetime
from urllib.parse import urlparse
from loguru import logger
from agent_platform.llm_client import LLMClient
from agent_platform.relationship_discovery import RelationshipDiscovery
from agent_platform.data_sampler import DataSampler
import psycopg2
from config.settings import settings


def _fw_conn():
    """Create a framework database connection"""
    return psycopg2.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD
    )


class IncrementalGTGenerator:
    """Generate ground truth queries incrementally for new schemas"""

    def __init__(self):
        self.llm_client = LLMClient(provider='azure', model='gpt-4o-harshal')
        self.ground_truth_dir = "data/ground_truth"
        os.makedirs(self.ground_truth_dir, exist_ok=True)
        self.db_url = None  # Will be set during generation

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
            from decimal import Decimal

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
                    elif isinstance(val, (datetime.date, datetime)):
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

        except Exception as e:
            logger.warning(f"Failed to execute SQL: {e}")
            return {
                "success": False,
                "error": str(e),
                "columns": [],
                "rows": [],
                "row_count": 0,
                "execution_time_ms": 0
            }

    def generate_for_new_schemas(
        self,
        agent_id: int,
        agent_name: str,
        db_url: str,
        new_schemas: List[Dict]
    ) -> int:
        """
        Generate queries ONLY for new schemas and append to existing GT file.
        Returns: number of new queries generated
        """
        if not new_schemas:
            logger.info(f"No new schemas to generate queries for agent {agent_id}")
            return 0

        # Store db_url for SQL execution
        self.db_url = db_url

        try:
            logger.info(f"Generating incremental GT for {len(new_schemas)} new columns/tables")

            # Transform to nested structure
            nested_schemas = self._transform_schemas(new_schemas)

            # Discover relationships for new schemas
            relationships = RelationshipDiscovery.discover_relationships(db_url)

            # Sample data from new tables only
            sample_data = DataSampler.sample_database(db_url, nested_schemas, limit=5)

            # Build prompt for incremental generation
            db_type = self._get_db_type(db_url)

            # Calculate number of queries (10 per new table, max 100)
            num_tables = len(set((s['schema_name'], s['table_name']) for s in new_schemas))
            num_queries = min(num_tables * 10, 100)

            prompt = self._build_incremental_prompt(
                agent_name, db_type, nested_schemas,
                relationships, sample_data, num_queries
            )

            # Call LLM
            logger.info(f"Calling LLM to generate {num_queries} incremental queries...")
            response = self.llm_client.generate(prompt, temperature=0.7, max_tokens=8000)

            # Parse queries
            queries = self._parse_queries(response)
            logger.info(f"Parsed {len(queries)} incremental queries")

            if not queries:
                logger.warning("No queries generated by LLM")
                return 0

            # Load existing GT file and append
            query_count = self._append_to_gt_file(agent_id, agent_name, queries)

            # Update database
            self._mark_changes_as_generated(agent_id, len(queries))

            return query_count

        except Exception as e:
            logger.error(f"Incremental GT generation failed for agent {agent_id}: {e}")
            raise

    def _transform_schemas(self, flat_schemas: List[Dict]) -> List[Dict]:
        """Transform flat schema list to nested structure"""
        nested = {}
        for item in flat_schemas:
            schema_name = item.get('schema_name', 'public')
            table_name = item.get('table_name')

            if schema_name not in nested:
                nested[schema_name] = {'schema_name': schema_name, 'tables': {}}

            if table_name not in nested[schema_name]['tables']:
                nested[schema_name]['tables'][table_name] = {
                    'table_name': table_name,
                    'columns': []
                }

            nested[schema_name]['tables'][table_name]['columns'].append({
                'name': item.get('column_name'),
                'type': item.get('data_type')
            })

        result = []
        for schema_data in nested.values():
            schema_data['tables'] = list(schema_data['tables'].values())
            result.append(schema_data)

        return result

    def _build_incremental_prompt(
        self, agent_name: str, db_type: str, schemas: List,
        relationships: List, sample_data: Dict, num_queries: int
    ) -> str:
        """Build prompt for incremental query generation"""

        schema_str = json.dumps(schemas, indent=2)
        sample_str = json.dumps(sample_data, indent=2) if sample_data else "{}"

        prompt = f"""You are a database expert. Generate {num_queries} SQL queries for the NEW tables/columns below.

Database Type: {db_type}
Agent: {agent_name}

NEW Schemas (just added):
{schema_str}

Sample Data:
{sample_str}

Generate {num_queries} diverse queries focusing on these NEW schemas:
- Simple SELECT queries (40%)
- Aggregations with COUNT, SUM, AVG, GROUP BY (30%)
- WHERE clauses with various conditions (20%)
- JOINs if relationships exist (10%)

IMPORTANT: Return ONLY a valid JSON array with this exact format:
[
  {{"natural_language": "Get all records from new table", "sql": "SELECT * FROM schema.table;"}},
  {{"natural_language": "Count records by category", "sql": "SELECT category, COUNT(*) FROM schema.table GROUP BY category;"}}
]

Do not include any markdown, explanations, or text outside the JSON array.
"""
        return prompt

    def _parse_queries(self, response: str) -> List[Dict]:
        """Parse LLM response and extract queries"""
        try:
            # Extract JSON from response
            start = response.find('[')
            end = response.rfind(']') + 1
            if start == -1 or end == 0:
                logger.warning("No JSON array found in LLM response")
                return []

            json_str = response[start:end]
            queries = json.loads(json_str)

            # Validate structure
            if not isinstance(queries, list):
                logger.warning("LLM response is not a list")
                return []

            return queries

        except Exception as e:
            logger.error(f"Failed to parse queries: {e}")
            return []

    def _append_to_gt_file(self, agent_id: int, agent_name: str, new_queries: List[Dict]) -> int:
        """Append new queries to existing GT file with expected outputs"""
        filename = f"{agent_name.lower().replace(' ', '_')}_queries.json"
        filepath = os.path.join(self.ground_truth_dir, filename)

        # Load existing file or create new structure
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                data = json.load(f)
        else:
            data = {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "total_queries": 0,
                "queries": [],
                "metadata": {
                    "incremental_updates": []
                }
            }

        # Execute each query and capture output
        enriched_queries = []
        success_count = 0
        fail_count = 0

        logger.info(f"Executing {len(new_queries)} queries to capture outputs...")

        start_id = len(data['queries']) + 1
        for i, q in enumerate(new_queries):
            try:
                sql = q.get('sql', '')
                if not sql:
                    q['id'] = start_id + i
                    q['generated_at'] = datetime.now().isoformat()
                    q['incremental'] = True
                    q['expected_output'] = None
                    enriched_queries.append(q)
                    fail_count += 1
                    continue

                # Execute SQL and capture output
                execution_result = self.execute_sql(sql)

                # Add expected_output to query
                if execution_result["success"]:
                    q["expected_output"] = {
                        "columns": execution_result["columns"],
                        "row_count": execution_result["row_count"],
                        "sample_rows": execution_result["rows"],
                        "execution_time_ms": execution_result["execution_time_ms"]
                    }
                    success_count += 1
                else:
                    q["expected_output"] = None
                    q["generation_error"] = execution_result["error"]
                    fail_count += 1

                q['id'] = start_id + i
                q['generated_at'] = datetime.now().isoformat()
                q['incremental'] = True
                enriched_queries.append(q)

            except Exception as e:
                logger.warning(f"Failed to execute query: {e}")
                q['id'] = start_id + i
                q['generated_at'] = datetime.now().isoformat()
                q['incremental'] = True
                q["expected_output"] = None
                q["generation_error"] = str(e)
                enriched_queries.append(q)
                fail_count += 1

        # Append enriched queries to data
        data['queries'].extend(enriched_queries)

        # Update metadata
        data['total_queries'] = len(data['queries'])
        if 'metadata' not in data:
            data['metadata'] = {"incremental_updates": []}

        data['metadata']['incremental_updates'].append({
            "timestamp": datetime.now().isoformat(),
            "query_count": len(enriched_queries),
            "success_count": success_count,
            "fail_count": fail_count
        })

        # Save file
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(
            f"Appended {len(enriched_queries)} queries to {filepath} "
            f"(Success: {success_count}, Failed: {fail_count})"
        )
        return len(enriched_queries)

    def _mark_changes_as_generated(self, agent_id: int, query_count: int):
        """Mark schema changes as having GT generated"""
        conn = _fw_conn()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE platform.schema_changes
            SET gt_generated = TRUE,
                gt_query_count = %s
            WHERE agent_id = %s AND gt_generated = FALSE
        """, (query_count, agent_id))

        conn.commit()
        cursor.close()
        conn.close()

    def _get_db_type(self, db_url: str) -> str:
        """Extract database type from URL"""
        parsed = urlparse(db_url)
        return parsed.scheme.replace('postgresql', 'postgres')
