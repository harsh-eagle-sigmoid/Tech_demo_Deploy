"""
Migration: Add schema monitoring and change tracking
"""
import sys
sys.path.insert(0, '/home/lenovo/New_tech_demo')

import psycopg2
from loguru import logger
from config.settings import settings


def migrate():
    """Add schema monitoring columns and tables"""
    try:
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD
        )
        cursor = conn.cursor()

        # Add columns to platform.agents
        migrations = [
            "ALTER TABLE platform.agents ADD COLUMN IF NOT EXISTS last_schema_scan_at TIMESTAMP",
            "ALTER TABLE platform.agents ADD COLUMN IF NOT EXISTS schema_version INTEGER DEFAULT 1",
            "ALTER TABLE platform.agents ADD COLUMN IF NOT EXISTS schema_change_count INTEGER DEFAULT 0",

            # Create schema_changes table
            """
            CREATE TABLE IF NOT EXISTS platform.schema_changes (
                change_id SERIAL PRIMARY KEY,
                agent_id INTEGER NOT NULL REFERENCES platform.agents(agent_id) ON DELETE CASCADE,
                change_type VARCHAR(20) NOT NULL,
                schema_name VARCHAR(100),
                table_name VARCHAR(200),
                column_name VARCHAR(200),
                data_type VARCHAR(100),
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                gt_generated BOOLEAN DEFAULT FALSE,
                gt_query_count INTEGER DEFAULT 0
            )
            """,

            # Create indexes for faster queries
            "CREATE INDEX IF NOT EXISTS idx_schema_changes_agent ON platform.schema_changes(agent_id)",
            "CREATE INDEX IF NOT EXISTS idx_schema_changes_detected ON platform.schema_changes(detected_at DESC)"
        ]

        for migration_sql in migrations:
            cursor.execute(migration_sql)
            logger.info(f"Executed: {migration_sql[:80]}...")

        conn.commit()
        cursor.close()
        conn.close()

        logger.info("✅ Migration complete: Schema monitoring columns and tables added")
        return True

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False


if __name__ == "__main__":
    migrate()
