"""
Detects schema changes by comparing current DB state with stored schemas
"""
from typing import Dict, List
from loguru import logger
from agent_platform.schema_discovery import SchemaDiscovery
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


class SchemaChangeDetector:
    """Detects and tracks schema changes in agent databases"""

    def detect_changes(self, agent_id: int, db_url: str) -> Dict:
        """
        Compare current DB schemas with stored schemas.
        Returns dict with new/removed tables and columns.
        """
        try:
            logger.info(f"Detecting schema changes for agent {agent_id}...")

            # Get current schemas from agent's database
            current_schemas = SchemaDiscovery.discover_schemas(db_url)

            # Get stored schemas from platform database
            stored_schemas = self._get_stored_schemas(agent_id)

            # Compute differences
            changes = self._compute_diff(current_schemas, stored_schemas)

            logger.info(f"Schema change detection for agent {agent_id}: "
                       f"{changes['new_tables_count']} new tables, "
                       f"{changes['new_columns_count']} new columns")

            return changes

        except Exception as e:
            logger.error(f"Failed to detect schema changes for agent {agent_id}: {e}")
            raise

    def _get_stored_schemas(self, agent_id: int) -> List[Dict]:
        """Fetch schemas stored in platform.discovered_schemas"""
        conn = _fw_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT schema_name, table_name, column_name, data_type
            FROM platform.discovered_schemas
            WHERE agent_id = %s
        """, (agent_id,))

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        return [
            {
                'schema_name': row[0],
                'table_name': row[1],
                'column_name': row[2],
                'data_type': row[3]
            }
            for row in rows
        ]

    def _compute_diff(self, current: List[Dict], stored: List[Dict]) -> Dict:
        """Compare current and stored schemas to find differences"""

        # Convert to sets for comparison
        current_set = {
            (s['schema_name'], s['table_name'], s['column_name'])
            for s in current
        }
        stored_set = {
            (s['schema_name'], s['table_name'], s['column_name'])
            for s in stored
        }

        # Find new and removed columns
        new_columns = current_set - stored_set
        removed_columns = stored_set - current_set

        # Extract new tables
        current_tables = {(s['schema_name'], s['table_name']) for s in current}
        stored_tables = {(s['schema_name'], s['table_name']) for s in stored}
        new_tables = current_tables - stored_tables
        removed_tables = stored_tables - current_tables

        # Build detailed change objects
        new_column_details = [
            s for s in current
            if (s['schema_name'], s['table_name'], s['column_name']) in new_columns
        ]

        new_table_details = list(new_tables)

        return {
            'new_tables': new_table_details,
            'new_tables_count': len(new_table_details),
            'new_columns': new_column_details,
            'new_columns_count': len(new_column_details),
            'removed_tables': list(removed_tables),
            'removed_columns': list(removed_columns),
            'has_changes': len(new_columns) > 0 or len(new_tables) > 0,
            'new_schemas': [s for s in current if (s['schema_name'], s['table_name'], s['column_name']) in new_columns]
        }

    def store_changes(self, agent_id: int, changes: Dict) -> None:
        """Store detected changes in platform.schema_changes table"""
        if not changes['has_changes']:
            logger.info(f"No schema changes detected for agent {agent_id}")
            return

        conn = _fw_conn()
        cursor = conn.cursor()

        try:
            # Store new table changes
            for schema_name, table_name in changes['new_tables']:
                cursor.execute("""
                    INSERT INTO platform.schema_changes
                    (agent_id, change_type, schema_name, table_name, gt_generated)
                    VALUES (%s, 'table_added', %s, %s, FALSE)
                """, (agent_id, schema_name, table_name))

            # Store new column changes
            for col in changes['new_columns']:
                cursor.execute("""
                    INSERT INTO platform.schema_changes
                    (agent_id, change_type, schema_name, table_name, column_name, data_type, gt_generated)
                    VALUES (%s, 'column_added', %s, %s, %s, %s, FALSE)
                """, (agent_id, col['schema_name'], col['table_name'],
                     col['column_name'], col.get('data_type')))

            conn.commit()
            logger.info(f"Stored {changes['new_tables_count']} table and "
                       f"{changes['new_columns_count']} column changes for agent {agent_id}")

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to store schema changes: {e}")
            raise
        finally:
            cursor.close()
            conn.close()
