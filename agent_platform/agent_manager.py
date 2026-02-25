"""
platform/agent_manager.py

AgentManager — CRUD and schema-discovery for registered agents in platform.agents.
All methods are synchronous (called from FastAPI background tasks or the poller thread).
"""

import psycopg2
import psycopg2.extras
from loguru import logger
from config.settings import settings
from auth.api_keys import generate_api_key


def _fw_conn():
    """Return a connection to the framework's own DB (unilever_poc)."""
    return psycopg2.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
    )


def _agent_conn(db_url: str):
    """Return a connection to an external agent DB via its db_url."""
    return psycopg2.connect(db_url)


class AgentManager:
    # ──────────────────────────────────────────────────────────────
    # CRUD
    # ──────────────────────────────────────────────────────────────

    def register_agent(
        self,
        agent_name: str,
        db_url: str,
        display_name: str = None,
        description: str = None,
        agent_url: str = None,
        poll_interval_s: int = 30,
    ) -> dict:
        """Insert a new agent into platform.agents, generate API key, return record with key (one-time)."""
        full_key, key_hash, key_prefix = generate_api_key(agent_name)

        sql = """
            INSERT INTO platform.agents
                (agent_name, display_name, description, db_url, agent_url,
                 poll_interval_s, status, api_key_hash, api_key_prefix)
            VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, %s)
            RETURNING agent_id, agent_name, display_name, description,
                      db_url, agent_url, status, poll_interval_s,
                      api_key_prefix, created_at
        """
        try:
            conn = _fw_conn()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(sql, (agent_name, display_name or agent_name, description,
                              db_url, agent_url, poll_interval_s, key_hash, key_prefix))
            row = dict(cur.fetchone())
            conn.commit()
            cur.close()
            conn.close()
            row["api_key"] = full_key  # One-time: only returned at registration
            logger.info(f"Registered agent '{agent_name}' (id={row['agent_id']})")
            return row
        except Exception as e:
            logger.error(f"register_agent failed: {e}")
            raise

    def get_all_agents(self) -> list:
        """Return all agents from platform.agents."""
        try:
            conn = _fw_conn()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM platform.agents ORDER BY created_at DESC")
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"get_all_agents failed: {e}")
            return []

    def get_agent(self, agent_id: int) -> dict | None:
        """Return a single agent by ID."""
        try:
            conn = _fw_conn()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM platform.agents WHERE agent_id = %s", (agent_id,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"get_agent failed: {e}")
            return None

    def get_agent_by_name(self, agent_name: str) -> dict | None:
        """Return a single agent by name (case-insensitive)."""
        try:
            conn = _fw_conn()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM platform.agents WHERE LOWER(agent_name) = LOWER(%s)",
                (agent_name,)
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"get_agent_by_name failed: {e}")
            return None

    def get_agent_by_api_key_hash(self, key_hash: str) -> dict | None:
        """Lookup agent by hashed API key. Used by SDK ingest endpoint."""
        try:
            conn = _fw_conn()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM platform.agents WHERE api_key_hash = %s",
                (key_hash,)
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"get_agent_by_api_key_hash failed: {e}")
            return None

    def regenerate_api_key(self, agent_id: int) -> tuple[str, str]:
        """Generate new API key, update hash+prefix, return (full_key, prefix)."""
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError("Agent not found")
        full_key, key_hash, key_prefix = generate_api_key(agent["agent_name"])
        try:
            conn = _fw_conn()
            cur = conn.cursor()
            cur.execute(
                """UPDATE platform.agents
                   SET api_key_hash = %s, api_key_prefix = %s, updated_at = NOW()
                   WHERE agent_id = %s""",
                (key_hash, key_prefix, agent_id)
            )
            conn.commit()
            cur.close()
            conn.close()
            return full_key, key_prefix
        except Exception as e:
            logger.error(f"regenerate_api_key failed: {e}")
            raise

    def delete_agent(self, agent_id: int) -> bool:
        """Delete agent, its platform metadata, and ALL monitoring data (queries, evaluations, errors, drift, baseline)."""
        try:
            conn = _fw_conn()
            cur = conn.cursor()

            # Get agent_name before deleting (needed for monitoring cleanup)
            cur.execute("SELECT agent_name FROM platform.agents WHERE agent_id = %s", (agent_id,))
            row = cur.fetchone()
            if not row:
                cur.close()
                conn.close()
                return False
            agent_name = row[0]

            # 1. Delete monitoring data (order matters due to FK constraints)
            cur.execute("DELETE FROM monitoring.errors WHERE query_id IN (SELECT query_id FROM monitoring.queries WHERE agent_type = %s)", (agent_name,))
            cur.execute("DELETE FROM monitoring.drift_monitoring WHERE query_id IN (SELECT query_id FROM monitoring.queries WHERE agent_type = %s)", (agent_name,))
            cur.execute("DELETE FROM monitoring.evaluations WHERE agent_type = %s", (agent_name,))
            cur.execute("DELETE FROM monitoring.queries WHERE agent_type = %s", (agent_name,))
            cur.execute("DELETE FROM monitoring.baseline WHERE agent_type = %s", (agent_name,))

            # 2. Delete platform registry (cascades to discovered_schemas + query_log_config)
            cur.execute("DELETE FROM platform.agents WHERE agent_id = %s", (agent_id,))
            deleted = cur.rowcount

            conn.commit()
            logger.info(f"Agent '{agent_name}' (id={agent_id}) fully removed — all monitoring data cleaned.")
            cur.close()
            conn.close()
            return deleted > 0
        except Exception as e:
            logger.error(f"delete_agent failed: {e}")
            return False

    def update_agent_status(self, agent_id: int, status: str, error: str = None):
        """Update agent status and optional last_error."""
        try:
            conn = _fw_conn()
            cur = conn.cursor()
            cur.execute(
                """UPDATE platform.agents
                   SET status = %s, last_error = %s, updated_at = NOW()
                   WHERE agent_id = %s""",
                (status, error, agent_id)
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"update_agent_status failed: {e}")

    # ──────────────────────────────────────────────────────────────
    # Schema Discovery
    # ──────────────────────────────────────────────────────────────

    def discover_schemas(self, agent_id: int) -> bool:
        """
        Connect to the agent's external DB, discover schemas using database-agnostic discovery.
        Supports PostgreSQL, MySQL, MongoDB, SQLite.
        """
        from agent_platform.schema_discovery import SchemaDiscovery

        agent = self.get_agent(agent_id)
        if not agent:
            logger.error(f"discover_schemas: agent {agent_id} not found")
            return False

        self.update_agent_status(agent_id, "discovering")

        try:
            # ✨ Use database-agnostic schema discovery
            schemas = SchemaDiscovery.discover_schemas(agent["db_url"])

            if not schemas:
                logger.warning(f"No schemas found for agent {agent_id}")
                self.update_agent_status(agent_id, "error", "No user-defined schema found")
                return False

            # Wipe old discovery data then insert fresh
            fw_conn = _fw_conn()
            fw_cur = fw_conn.cursor()
            fw_cur.execute(
                "DELETE FROM platform.discovered_schemas WHERE agent_id = %s", (agent_id,)
            )
            psycopg2.extras.execute_values(
                fw_cur,
                """INSERT INTO platform.discovered_schemas
                   (agent_id, schema_name, table_name, column_name, data_type, is_nullable)
                   VALUES %s
                   ON CONFLICT (agent_id, schema_name, table_name, column_name) DO NOTHING""",
                [
                    (agent_id, s['schema_name'], s['table_name'],
                     s['column_name'], s['data_type'], s['is_nullable'])
                    for s in schemas
                ]
            )
            fw_conn.commit()
            fw_cur.close()
            fw_conn.close()

            logger.info(f"Discovered {len(schemas)} columns for agent {agent_id}")
            return True

        except Exception as e:
            logger.error(f"discover_schemas failed for agent {agent_id}: {e}")
            self.update_agent_status(agent_id, "error", str(e))
            return False

    # ──────────────────────────────────────────────────────────────
    # Query-Log Table Detection
    # ──────────────────────────────────────────────────────────────

    def detect_query_log_table(self, agent_id: int) -> bool:
        """
        Score tables in platform.discovered_schemas by column-name heuristics.
        Store the best match (score >= 6) in platform.query_log_config.
        """
        QUERY_TEXT_COLS = {"query_text", "question", "prompt", "user_query", "nl_query", "query"}
        SQL_COLS        = {"sql", "generated_sql", "sql_query", "response_sql", "query_sql"}
        TS_COLS         = {"created_at", "timestamp", "logged_at", "query_time", "executed_at"}
        STATUS_COLS     = {"status", "query_status", "state"}
        ERROR_COLS      = {"error", "error_message", "error_msg"}
        ID_COLS         = {"id", "query_id", "log_id", "row_id"}

        try:
            conn = _fw_conn()
            cur = conn.cursor()
            cur.execute(
                """SELECT schema_name, table_name, column_name
                   FROM platform.discovered_schemas
                   WHERE agent_id = %s
                   ORDER BY schema_name, table_name, column_name""",
                (agent_id,)
            )
            rows = cur.fetchall()
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"detect_query_log_table DB read failed: {e}")
            return False

        # Build table → {col_name} map
        tables: dict[tuple, set] = {}
        for schema_name, table_name, col_name in rows:
            key = (schema_name, table_name)
            tables.setdefault(key, set()).add(col_name.lower())

        best_score = 0
        best_table = None
        best_cols: dict = {}

        for (schema_name, table_name), cols in tables.items():
            score = 0
            matched: dict = {}

            qt = next((c for c in cols if c in QUERY_TEXT_COLS), None)
            if qt:
                score += 3
                matched["query_text_column"] = qt

            sq = next((c for c in cols if c in SQL_COLS), None)
            if sq:
                score += 3
                matched["sql_column"] = sq

            ts = next((c for c in cols if c in TS_COLS), None)
            if ts:
                score += 2
                matched["timestamp_column"] = ts

            st = next((c for c in cols if c in STATUS_COLS), None)
            if st:
                score += 1
                matched["status_column"] = st

            er = next((c for c in cols if c in ERROR_COLS), None)
            if er:
                score += 1
                matched["error_column"] = er

            id_ = next((c for c in cols if c in ID_COLS), None)
            if id_:
                matched["id_column"] = id_

            if score > best_score:
                best_score = score
                best_table = (schema_name, table_name)
                best_cols = matched

        if best_score < 6 or best_table is None:
            logger.info(
                f"No query log table detected for agent {agent_id} "
                f"(best score={best_score}) — agent will use SDK for ingestion"
            )
            return False

        schema_name, table_name = best_table
        logger.info(
            f"Detected query log table: {schema_name}.{table_name} "
            f"(score={best_score}) for agent {agent_id}"
        )

        try:
            conn = _fw_conn()
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO platform.query_log_config
                       (agent_id, schema_name, table_name,
                        query_text_column, sql_column, timestamp_column,
                        status_column, error_column, id_column,
                        last_seen_timestamp)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s, CURRENT_TIMESTAMP)
                   ON CONFLICT (agent_id) DO UPDATE SET
                       schema_name       = EXCLUDED.schema_name,
                       table_name        = EXCLUDED.table_name,
                       query_text_column = EXCLUDED.query_text_column,
                       sql_column        = EXCLUDED.sql_column,
                       timestamp_column  = EXCLUDED.timestamp_column,
                       status_column     = EXCLUDED.status_column,
                       error_column      = EXCLUDED.error_column,
                       id_column         = EXCLUDED.id_column,
                       last_seen_timestamp = CURRENT_TIMESTAMP""",
                (
                    agent_id, schema_name, table_name,
                    best_cols.get("query_text_column", "query_text"),
                    best_cols.get("sql_column", "sql"),
                    best_cols.get("timestamp_column", "created_at"),
                    best_cols.get("status_column"),
                    best_cols.get("error_column"),
                    best_cols.get("id_column"),
                )
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"detect_query_log_table write failed: {e}")
            return False

        self.update_agent_status(agent_id, "active")
        return True

    def discover_and_configure(self, agent_id: int) -> bool:
        """Run discovery: schemas (required) + query_log detection (optional bonus)."""
        ok = self.discover_schemas(agent_id)
        if not ok:
            return False

        # Schema discovery succeeded — agent is active regardless of query_log
        self.update_agent_status(agent_id, "active")

        # ✨ Generate ground truth queries
        self._generate_ground_truth(agent_id)

        # ✨ Run database validation
        self._run_database_validation(agent_id)

        # Try to detect query_log (bonus: enables polling)
        has_query_log = self.detect_query_log_table(agent_id)
        if has_query_log:
            logger.info(f"Agent {agent_id}: query_log detected, polling enabled")
        else:
            logger.info(f"Agent {agent_id}: no query_log found, use SDK for ingestion")

        return True

    def _run_database_validation(self, agent_id: int):
        """Run database validation and store results."""
        try:
            from validation.database_factory import DatabaseValidatorFactory
            import json

            logger.info(f"Starting database validation for agent {agent_id}")

            # Get agent info
            agent = self.get_agent(agent_id)
            if not agent:
                return

            # Get discovered schemas
            schema_info = self.get_agent_schema_info(agent_id)
            if not schema_info:
                logger.warning(f"No schema info found for agent {agent_id}, skipping validation")
                return

            # Create appropriate validator
            validator = DatabaseValidatorFactory.create_validator(agent_id, agent["db_url"])

            if not validator:
                logger.warning(f"No validator available for agent {agent_id}")
                return

            # Run validation
            issues = validator.validate_all(schema_info)

            # Store issues in database
            self._store_validation_issues(agent_id, issues)

            # Log summary
            critical_count = len([i for i in issues if i['severity'] == 'critical'])
            warning_count = len([i for i in issues if i['severity'] == 'warning'])
            info_count = len([i for i in issues if i['severity'] == 'info'])

            logger.info(
                f"Validation complete for agent {agent_id}: "
                f"{critical_count} critical, {warning_count} warnings, {info_count} info"
            )

        except Exception as e:
            logger.error(f"Database validation failed for agent {agent_id}: {e}")

    def _store_validation_issues(self, agent_id: int, issues: list):
        """Store validation issues in platform.data_quality_issues."""
        import json

        if not issues:
            logger.info(f"No validation issues found for agent {agent_id}")
            return

        try:
            conn = _fw_conn()
            cur = conn.cursor()

            # Clear old issues for this agent
            cur.execute(
                "DELETE FROM platform.data_quality_issues WHERE agent_id = %s",
                (agent_id,)
            )

            # Insert new issues
            for issue in issues:
                cur.execute("""
                    INSERT INTO platform.data_quality_issues
                        (agent_id, schema_name, table_name, column_name,
                         issue_type, severity, message, details,
                         affected_rows, total_rows, percentage)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    issue['agent_id'],
                    issue['schema_name'],
                    issue['table_name'],
                    issue['column_name'],
                    issue['issue_type'],
                    issue['severity'],
                    issue['message'],
                    json.dumps(issue['details']) if issue['details'] else None,
                    issue['affected_rows'],
                    issue['total_rows'],
                    issue['percentage']
                ))

            conn.commit()
            cur.close()
            conn.close()

            logger.info(f"Stored {len(issues)} validation issues for agent {agent_id}")

        except Exception as e:
            logger.error(f"Failed to store validation issues: {e}")

    def _generate_ground_truth(self, agent_id: int):
        """Generate ground truth queries for an agent with retry logic."""
        import time
        import json
        import os
        from agent_platform.ground_truth_generator import GroundTruthGenerator
        from agent_platform.schema_discovery import SchemaDiscovery

        max_retries = 3
        base_delay = 5  # seconds

        # Update status to 'in_progress'
        self._update_gt_status(agent_id, 'in_progress', None, None, None)

        for attempt in range(max_retries):
            try:
                logger.info(f"Ground truth generation attempt {attempt + 1}/{max_retries} for agent {agent_id}")

                # Get agent info
                agent = self.get_agent(agent_id)
                if not agent:
                    error_msg = f"Agent {agent_id} not found"
                    logger.warning(error_msg)
                    self._update_gt_status(agent_id, 'failed', error_msg, None, None)
                    return

                # Get discovered schemas
                schemas = SchemaDiscovery.discover_schemas(agent['db_url'])
                if not schemas:
                    error_msg = "No schemas found, cannot generate ground truth"
                    logger.warning(error_msg)
                    self._update_gt_status(agent_id, 'failed', error_msg, None, None)
                    return

                # Generate ground truth
                generator = GroundTruthGenerator()
                generator.generate_for_agent(
                    agent_id=agent_id,
                    agent_name=agent['agent_name'],
                    db_url=agent['db_url'],
                    schemas=schemas
                )

                # Check if file was created and get query count
                from agent_platform.gt_storage import get_gt_storage
                agent_name = agent['agent_name'].lower().replace(' ', '_')
                filename = f"{agent_name}_queries.json"
                gt_storage = get_gt_storage()
                data = gt_storage.load(filename)

                if data is not None:
                    query_count = data.get('total_queries', 0)

                    if query_count > 0:
                        # Success!
                        logger.info(f"Ground truth generation successful for agent {agent_id}: {query_count} queries")
                        self._update_gt_status(agent_id, 'success', None, query_count, None)

                        # Auto-create drift baseline from the newly generated GT file
                        try:
                            from monitoring.baseline_manager import _create_baseline_from_file
                            from monitoring.drift_detector import DriftDetector
                            detector = DriftDetector()
                            _create_baseline_from_file(agent['agent_name'], detector)
                            logger.info(f"Drift baseline auto-created for '{agent['agent_name']}'")
                        except Exception as be:
                            logger.warning(f"Baseline creation after GT gen failed (non-fatal): {be}")

                        return
                    else:
                        raise Exception("No queries were generated")
                else:
                    raise Exception(f"Ground truth file not found in storage: {filename}")

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Ground truth generation attempt {attempt + 1} failed for agent {agent_id}: {error_msg}")

                # If this was the last attempt, mark as failed
                if attempt == max_retries - 1:
                    self._update_gt_status(agent_id, 'failed', error_msg, None, attempt + 1)
                    return

                # Exponential backoff: 5s, 10s, 20s
                delay = base_delay * (2 ** attempt)
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)

                # Update retry count
                self._update_gt_retry_count(agent_id, attempt + 1)

    def _update_gt_status(self, agent_id: int, status: str, error: str, query_count: int, retry_count: int):
        """Update ground truth status in database."""
        try:
            conn = _fw_conn()
            cursor = conn.cursor()

            if status == 'success':
                cursor.execute("""
                    UPDATE platform.agents
                    SET gt_status = %s,
                        gt_error = NULL,
                        gt_generated_at = CURRENT_TIMESTAMP,
                        gt_query_count = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE agent_id = %s
                """, (status, query_count, agent_id))
            elif status == 'failed':
                cursor.execute("""
                    UPDATE platform.agents
                    SET gt_status = %s,
                        gt_error = %s,
                        gt_retry_count = COALESCE(%s, gt_retry_count),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE agent_id = %s
                """, (status, error, retry_count, agent_id))
            else:  # in_progress
                cursor.execute("""
                    UPDATE platform.agents
                    SET gt_status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE agent_id = %s
                """, (status, agent_id))

            conn.commit()
            cursor.close()
            conn.close()

        except Exception as e:
            logger.error(f"Failed to update GT status for agent {agent_id}: {e}")

    def _update_gt_retry_count(self, agent_id: int, retry_count: int):
        """Update ground truth retry count."""
        try:
            conn = _fw_conn()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE platform.agents
                SET gt_retry_count = %s,
                    gt_last_retry_at = CURRENT_TIMESTAMP
                WHERE agent_id = %s
            """, (retry_count, agent_id))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to update GT retry count for agent {agent_id}: {e}")

    def retry_ground_truth_generation(self, agent_id: int) -> dict:
        """
        Manually retry ground truth generation for a failed agent.
        Returns dict with status and message.
        """
        try:
            # Get current agent status
            agent = self.get_agent(agent_id)
            if not agent:
                return {"success": False, "message": f"Agent {agent_id} not found"}

            # Check if retry is needed
            gt_status = agent.get('gt_status', 'pending')
            if gt_status == 'in_progress':
                return {"success": False, "message": "Ground truth generation already in progress"}

            if gt_status == 'success':
                return {"success": False, "message": "Ground truth already generated successfully"}

            # Reset retry count and start fresh
            conn = _fw_conn()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE platform.agents
                SET gt_retry_count = 0
                WHERE agent_id = %s
            """, (agent_id,))
            conn.commit()
            cursor.close()
            conn.close()

            # Trigger generation
            logger.info(f"Manual retry triggered for agent {agent_id} ground truth generation")
            self._generate_ground_truth(agent_id)

            # Get updated status
            agent = self.get_agent(agent_id)
            final_status = agent.get('gt_status', 'unknown')

            if final_status == 'success':
                return {
                    "success": True,
                    "message": f"Ground truth generated successfully: {agent.get('gt_query_count', 0)} queries"
                }
            else:
                return {
                    "success": False,
                    "message": f"Generation failed: {agent.get('gt_error', 'Unknown error')}"
                }

        except Exception as e:
            logger.error(f"Manual retry failed for agent {agent_id}: {e}")
            return {"success": False, "message": str(e)}

    # ──────────────────────────────────────────────────────────────
    # Helpers for Evaluation Pipeline
    # ──────────────────────────────────────────────────────────────

    def get_agent_schema_info(self, agent_id: int) -> dict:
        """
        Return {schema.table: {col_name: data_type}} dict from discovered_schemas.
        Uses fully qualified names (schema.table) to support multiple schemas.
        Also includes unqualified names if table names are unique across schemas.
        """
        try:
            conn = _fw_conn()
            cur = conn.cursor()
            cur.execute(
                """SELECT schema_name, table_name, column_name, data_type
                   FROM platform.discovered_schemas
                   WHERE agent_id = %s
                   ORDER BY schema_name, table_name, column_name""",
                (agent_id,)
            )
            rows = cur.fetchall()
            cur.close()
            conn.close()

            schema_info: dict = {}
            schema_per_table = {}  # Track which schemas have each table name

            # First pass: build qualified names and track schema-table relationships
            for schema_name, table_name, col_name, data_type in rows:
                qualified_name = f"{schema_name}.{table_name}"
                schema_info.setdefault(qualified_name, {})[col_name] = data_type
                schema_per_table.setdefault(table_name, set()).add(schema_name)

            # Second pass: add unqualified names for unique tables (backward compatibility)
            for schema_name, table_name, col_name, data_type in rows:
                # Only add unqualified name if table appears in exactly one schema
                if len(schema_per_table[table_name]) == 1 and table_name not in schema_info:
                    schema_info.setdefault(table_name, {})[col_name] = data_type

            return schema_info
        except Exception as e:
            logger.error(f"get_agent_schema_info failed: {e}")
            return {}

    def get_agent_db_url(self, agent_id: int) -> str | None:
        """Return the db_url for an agent."""
        agent = self.get_agent(agent_id)
        return agent["db_url"] if agent else None

    # ──────────────────────────────────────────────────────────────
    # Schema Monitoring & Incremental GT Generation
    # ──────────────────────────────────────────────────────────────

    def scan_schema_changes(self, agent_id: int) -> dict:
        """
        Manually trigger schema change detection and incremental GT generation.
        Returns summary of changes and queries generated.
        """
        from agent_platform.schema_change_detector import SchemaChangeDetector
        from agent_platform.incremental_gt_generator import IncrementalGTGenerator

        try:
            # Get agent info
            agent = self.get_agent(agent_id)
            if not agent:
                return {"success": False, "message": f"Agent {agent_id} not found"}

            logger.info(f"Manual schema scan triggered for agent {agent_id}")

            # Detect changes
            detector = SchemaChangeDetector()
            changes = detector.detect_changes(agent_id, agent['db_url'])

            if not changes['has_changes']:
                self._update_scan_timestamp(agent_id)
                return {
                    "success": True,
                    "message": "No schema changes detected",
                    "changes": changes,
                    "queries_generated": 0
                }

            # Store changes
            detector.store_changes(agent_id, changes)

            # Store new schemas
            self._store_new_schemas(agent_id, changes['new_schemas'])

            # Generate incremental GT
            generator = IncrementalGTGenerator()
            query_count = generator.generate_for_new_schemas(
                agent_id,
                agent['agent_name'],
                agent['db_url'],
                changes['new_schemas']
            )

            # Update agent metadata
            self._update_agent_schema_metadata(agent_id, changes, query_count)

            return {
                "success": True,
                "message": f"Detected {changes['new_tables_count']} new tables, "
                          f"{changes['new_columns_count']} new columns. "
                          f"Generated {query_count} queries.",
                "changes": changes,
                "queries_generated": query_count
            }

        except Exception as e:
            logger.error(f"Schema scan failed for agent {agent_id}: {e}")
            return {"success": False, "message": str(e)}

    def _store_new_schemas(self, agent_id: int, new_schemas: list):
        """Store new schemas in platform.discovered_schemas"""
        conn = _fw_conn()
        cursor = conn.cursor()

        try:
            for schema in new_schemas:
                cursor.execute("""
                    INSERT INTO platform.discovered_schemas
                    (agent_id, schema_name, table_name, column_name, data_type, discovered_at)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (agent_id, schema_name, table_name, column_name) DO NOTHING
                """, (agent_id, schema.get('schema_name', 'public'),
                     schema['table_name'], schema['column_name'],
                     schema.get('data_type')))

            conn.commit()
            logger.info(f"Stored {len(new_schemas)} new schemas for agent {agent_id}")

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to store new schemas: {e}")
            raise
        finally:
            cursor.close()
            conn.close()

    def _update_agent_schema_metadata(self, agent_id: int, changes: dict, query_count: int):
        """Update agent's schema version and metadata"""
        conn = _fw_conn()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE platform.agents
                SET last_schema_scan_at = CURRENT_TIMESTAMP,
                    schema_version = COALESCE(schema_version, 0) + 1,
                    schema_change_count = COALESCE(schema_change_count, 0) + %s,
                    gt_query_count = COALESCE(gt_query_count, 0) + %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE agent_id = %s
            """, (changes['new_tables_count'] + changes['new_columns_count'],
                  query_count, agent_id))

            conn.commit()

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to update agent metadata: {e}")
            raise
        finally:
            cursor.close()
            conn.close()

    def _update_scan_timestamp(self, agent_id: int):
        """Update last scan timestamp when no changes detected"""
        conn = _fw_conn()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE platform.agents
            SET last_schema_scan_at = CURRENT_TIMESTAMP
            WHERE agent_id = %s
        """, (agent_id,))

        conn.commit()
        cursor.close()
        conn.close()

    def get_schema_changes_history(self, agent_id: int, limit: int = 50) -> list:
        """Get schema change history for an agent"""
        conn = _fw_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT change_id, change_type, schema_name, table_name, column_name,
                   data_type, detected_at, gt_generated, gt_query_count
            FROM platform.schema_changes
            WHERE agent_id = %s
            ORDER BY detected_at DESC
            LIMIT %s
        """, (agent_id, limit))

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        return [
            {
                'change_id': row[0],
                'change_type': row[1],
                'schema_name': row[2],
                'table_name': row[3],
                'column_name': row[4],
                'data_type': row[5],
                'detected_at': str(row[6]) if row[6] else None,
                'gt_generated': row[7],
                'gt_query_count': row[8]
            }
            for row in rows
        ]
