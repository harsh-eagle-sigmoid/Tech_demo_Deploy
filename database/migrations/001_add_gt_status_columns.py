"""
Migration: Add ground truth status tracking columns to agents table
"""
import sys
sys.path.insert(0, '/home/lenovo/New_tech_demo')

import psycopg2
from loguru import logger
from config.settings import settings


def migrate():
    """Add GT status columns to platform.agents table"""
    try:
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD
        )
        cursor = conn.cursor()

        # Add GT status columns
        migrations = [
            "ALTER TABLE platform.agents ADD COLUMN IF NOT EXISTS gt_status VARCHAR(20) DEFAULT 'pending'",
            "ALTER TABLE platform.agents ADD COLUMN IF NOT EXISTS gt_error TEXT",
            "ALTER TABLE platform.agents ADD COLUMN IF NOT EXISTS gt_generated_at TIMESTAMP",
            "ALTER TABLE platform.agents ADD COLUMN IF NOT EXISTS gt_query_count INTEGER",
            "ALTER TABLE platform.agents ADD COLUMN IF NOT EXISTS gt_retry_count INTEGER DEFAULT 0",
            "ALTER TABLE platform.agents ADD COLUMN IF NOT EXISTS gt_last_retry_at TIMESTAMP"
        ]

        for migration_sql in migrations:
            cursor.execute(migration_sql)
            logger.info(f"Executed: {migration_sql}")

        conn.commit()
        cursor.close()
        conn.close()

        logger.info("✅ Migration complete: GT status columns added")
        return True

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False


if __name__ == "__main__":
    migrate()
