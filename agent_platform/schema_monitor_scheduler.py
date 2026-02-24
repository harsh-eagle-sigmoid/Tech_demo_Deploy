"""
Background scheduler for monitoring schema changes every 10 hours
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from typing import List, Dict
from loguru import logger
from agent_platform.agent_manager import AgentManager
from agent_platform.schema_change_detector import SchemaChangeDetector
from agent_platform.incremental_gt_generator import IncrementalGTGenerator
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


class SchemaMonitorScheduler:
    """Monitors agent schemas for changes every 10 hours"""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.detector = SchemaChangeDetector()
        self.gt_generator = IncrementalGTGenerator()

    def start(self):
        """Start the 10-hour monitoring job"""
        self.scheduler.add_job(
            func=self._scan_all_agents,
            trigger=IntervalTrigger(hours=10),
            id='schema_monitor',
            name='Monitor agent schemas every 10 hours',
            replace_existing=True
        )
        self.scheduler.start()
        logger.info("🔄 Schema monitor scheduler started (10-hour interval)")

    def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Schema monitor scheduler stopped")

    def _scan_all_agents(self):
        """Scan all active agents for schema changes"""
        logger.info("=" * 60)
        logger.info("Starting scheduled schema change scan for all agents")
        logger.info("=" * 60)

        mgr = AgentManager()
        agents = mgr.get_all_agents()

        for agent in agents:
            try:
                self._scan_agent(agent['agent_id'], agent['agent_name'], agent['db_url'])
            except Exception as e:
                logger.error(f"Failed to scan agent {agent['agent_id']}: {e}")

    def _scan_agent(self, agent_id: int, agent_name: str, db_url: str):
        """Scan single agent for schema changes"""
        logger.info(f"Scanning agent {agent_id} ({agent_name}) for schema changes...")

        try:
            # Detect changes
            changes = self.detector.detect_changes(agent_id, db_url)

            if not changes['has_changes']:
                logger.info(f"No schema changes for agent {agent_id}")
                self._update_scan_timestamp(agent_id)
                return

            logger.info(f"Detected changes for agent {agent_id}: "
                       f"{changes['new_tables_count']} new tables, "
                       f"{changes['new_columns_count']} new columns")

            # Store changes in database
            self.detector.store_changes(agent_id, changes)

            # Store new schemas in discovered_schemas
            self._store_new_schemas(agent_id, changes['new_schemas'])

            # Generate incremental ground truth
            query_count = self.gt_generator.generate_for_new_schemas(
                agent_id, agent_name, db_url, changes['new_schemas']
            )

            # Update agent metadata
            self._update_agent_metadata(agent_id, changes, query_count)

            logger.info(f"✅ Schema scan complete for agent {agent_id}: "
                       f"Generated {query_count} new queries")

        except Exception as e:
            logger.error(f"Schema scan failed for agent {agent_id}: {e}")
            raise

    def _store_new_schemas(self, agent_id: int, new_schemas: List[Dict]):
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

    def _update_agent_metadata(self, agent_id: int, changes: Dict, query_count: int):
        """Update agent's schema scan metadata"""
        conn = _fw_conn()
        cursor = conn.cursor()

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
        cursor.close()
        conn.close()

    def _update_scan_timestamp(self, agent_id: int):
        """Update last scan timestamp (no changes detected)"""
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
