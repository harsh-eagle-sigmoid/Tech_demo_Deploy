"""
Generate ground truth queries using LLM
"""
import json
import os
from loguru import logger
from agent_platform.llm_client import LLMClient
from agent_platform.prompt_builder import PromptBuilder
from agent_platform.relationship_discovery import RelationshipDiscovery
from agent_platform.data_sampler import DataSampler
from agent_platform.gt_storage import get_gt_storage
from urllib.parse import urlparse
import psycopg2
from datetime import datetime, date
from decimal import Decimal


class GroundTruthGenerator:
    """Generate ground truth test queries"""

    def __init__(self):
        # Use Azure GPT-4o for ground truth generation
        self.llm_client = LLMClient(provider='azure', model='gpt-4o-harshal')
        self.ground_truth_dir = "data/ground_truth"
        self.db_url = None  # Will be set during generation

    def execute_sql(self, sql: str, timeout_ms: int = 5000) -> dict:
        """
        Execute SQL query and capture output

        Args:
            sql: SQL query to execute
            timeout_ms: Query timeout in milliseconds

        Returns:
            Dict with execution results
        """
        try:
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

    def generate_for_agent(self, agent_id: int, agent_name: str, db_url: str, schemas: list):
        """
        Generate ground truth queries for an agent
        """
        logger.info(f"Starting ground truth generation for agent {agent_id} ({agent_name})")

        # Store db_url for SQL execution
        self.db_url = db_url

        # Get database type
        db_type = urlparse(db_url).scheme

        # Transform flat schema list to nested structure
        nested_schemas = self._transform_schemas(schemas)

        # 1. Discover relationships (in-memory)
        logger.info("Discovering table relationships...")
        relationships = RelationshipDiscovery.discover_relationships(db_url)
        logger.info(f"Found {len(relationships)} relationships")

        # 2. Sample data (in-memory)
        logger.info("Sampling data from tables...")
        sample_data = DataSampler.sample_database(db_url, nested_schemas, limit=5)
        logger.info(f"Sampled {len(sample_data)} tables")

        # 3. Generate queries in batches to avoid token limit
        logger.info("Generating 100 queries in 4 batches of 25...")
        all_queries = []
        batch_size = 25
        num_batches = 4

        for batch_num in range(num_batches):
            logger.info(f"Generating batch {batch_num + 1}/{num_batches} ({batch_size} queries)...")

            # Build prompt for this batch
            prompt = PromptBuilder.build_ground_truth_prompt(
                agent_name=agent_name,
                db_type=db_type,
                schemas=nested_schemas,
                relationships=relationships,
                sample_data=sample_data,
                num_queries=batch_size
            )

            # Generate queries for this batch
            try:
                response = self.llm_client.generate(prompt, temperature=0.7, max_tokens=8000)
                batch_queries = self._parse_response(response)

                if batch_queries:
                    all_queries.extend(batch_queries)
                    logger.info(f"Batch {batch_num + 1} generated {len(batch_queries)} queries")
                else:
                    logger.warning(f"Batch {batch_num + 1} generated no queries")

            except Exception as e:
                logger.error(f"Batch {batch_num + 1} failed: {e}")
                # Continue with next batch even if one fails

        queries = all_queries

        if not queries:
            logger.warning(f"No queries generated for agent {agent_id}")
            return

        logger.info(f"Generated total of {len(queries)} queries across all batches")

        # 4. Save to JSON file
        self._save_to_file(agent_id, agent_name, queries)

        logger.info(f"Ground truth generation complete for agent {agent_id}")

    def _transform_schemas(self, flat_schemas: list) -> list:
        """
        Transform flat schema list to nested structure.
        Input: [{'schema_name': 'x', 'table_name': 'y', 'column_name': 'z', ...}, ...]
        Output: [{'schema_name': 'x', 'tables': [{'table_name': 'y', 'columns': [...]}]}]
        """
        nested = {}

        for item in flat_schemas:
            schema_name = item.get('schema_name', 'public')
            table_name = item.get('table_name')
            column_name = item.get('column_name')

            if not table_name or not column_name:
                continue

            # Initialize schema if not exists
            if schema_name not in nested:
                nested[schema_name] = {}

            # Initialize table if not exists
            if table_name not in nested[schema_name]:
                nested[schema_name][table_name] = []

            # Add column
            nested[schema_name][table_name].append({
                'name': column_name,
                'type': item.get('data_type', 'unknown')
            })

        # Convert to list format
        result = []
        for schema_name, tables in nested.items():
            result.append({
                'schema_name': schema_name,
                'tables': [
                    {'table_name': table_name, 'columns': columns}
                    for table_name, columns in tables.items()
                ]
            })

        return result

    def _parse_response(self, response: str) -> list:
        """Parse LLM JSON response"""
        try:
            # Strip whitespace
            response = response.strip()

            # Remove markdown code blocks if present
            if response.startswith('```'):
                lines = response.split('\n')
                # Find start and end of JSON
                start_idx = 0
                end_idx = len(lines)

                for i, line in enumerate(lines):
                    if line.strip().startswith('```'):
                        if start_idx == 0:
                            start_idx = i + 1
                        else:
                            end_idx = i
                            break

                response = '\n'.join(lines[start_idx:end_idx])

                # Remove json indicator if present
                if response.strip().startswith('json'):
                    response = response.strip()[4:].strip()

            # Parse JSON
            queries = json.loads(response)

            # Validate structure
            if not isinstance(queries, list):
                logger.error("Response is not a JSON array")
                return []

            for query in queries:
                if 'natural_language' not in query or 'sql' not in query:
                    logger.warning(f"Invalid query structure: {query}")

            # Filter out invalid queries
            valid_queries = [q for q in queries
                           if 'natural_language' in q and 'sql' in q
                           and q['natural_language'] and q['sql']]

            return valid_queries

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response was: {response[:500]}")
            return []
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return []

    def _save_to_file(self, agent_id: int, agent_name: str, queries: list):
        """
        Save queries to JSON (S3 or local filesystem via GTStorage)
        """
        storage = get_gt_storage()

        # Determine filename
        filename = f"{agent_name.lower().replace(' ', '_')}_queries.json"

        # Execute each query and capture output
        enriched_queries = []
        success_count = 0
        fail_count = 0

        logger.info(f"Executing {len(queries)} queries to capture outputs...")

        for query in queries:
            try:
                sql = query.get('sql', '')
                if not sql:
                    enriched_queries.append(query)
                    fail_count += 1
                    continue

                # Execute SQL and capture output
                execution_result = self.execute_sql(sql)

                # Add expected_output to query
                if execution_result["success"]:
                    query["expected_output"] = {
                        "columns": execution_result["columns"],
                        "row_count": execution_result["row_count"],
                        "sample_rows": execution_result["rows"],
                        "execution_time_ms": execution_result["execution_time_ms"]
                    }
                    success_count += 1
                else:
                    query["expected_output"] = None
                    query["generation_error"] = execution_result["error"]
                    fail_count += 1

                query["generated_at"] = datetime.now().isoformat()
                enriched_queries.append(query)

            except Exception as e:
                logger.warning(f"Failed to execute query: {e}")
                query["expected_output"] = None
                query["generation_error"] = str(e)
                enriched_queries.append(query)
                fail_count += 1

        # Prepare output
        output = {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "total_queries": len(enriched_queries),
            "queries": enriched_queries,
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "success_count": success_count,
                "fail_count": fail_count
            }
        }

        # Save via GTStorage (S3 or local)
        storage.save(filename, output)

        logger.info(
            f"Saved {len(enriched_queries)} queries to {filename} "
            f"(Success: {success_count}, Failed: {fail_count})"
        )
