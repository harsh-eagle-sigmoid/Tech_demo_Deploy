"""
Discover table relationships (foreign keys) across different database types
"""
from urllib.parse import urlparse
import psycopg2
import psycopg2.extras
import sqlite3
from loguru import logger

# Optional imports
try:
    import mysql.connector
except ImportError:
    mysql = None

try:
    from pymongo import MongoClient
    from bson import ObjectId
except ImportError:
    MongoClient = None
    ObjectId = None


class RelationshipDiscovery:
    """Discover table relationships for different database types"""

    @staticmethod
    def discover_relationships(db_url: str) -> list:
        """
        Main entry point - discover relationships based on DB type
        Returns list of relationship dicts
        """
        parsed = urlparse(db_url)
        db_type = parsed.scheme.lower()

        try:
            if db_type in ['postgresql', 'postgres']:
                return RelationshipDiscovery._discover_postgresql(db_url)
            elif db_type == 'mysql':
                return RelationshipDiscovery._discover_mysql(db_url)
            elif db_type in ['mongodb', 'mongodb+srv']:
                return RelationshipDiscovery._discover_mongodb(db_url)
            elif db_type == 'sqlite':
                return RelationshipDiscovery._discover_sqlite(db_url)
            else:
                logger.warning(f"Unsupported database type: {db_type}")
                return []
        except Exception as e:
            logger.error(f"Failed to discover relationships: {e}")
            return []

    @staticmethod
    def _discover_postgresql(db_url: str) -> list:
        """Discover foreign keys in PostgreSQL"""
        relationships = []

        try:
            conn = psycopg2.connect(db_url)
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            query = """
            SELECT
                tc.table_schema AS source_schema,
                tc.table_name AS source_table,
                kcu.column_name AS source_column,
                ccu.table_schema AS target_schema,
                ccu.table_name AS target_table,
                ccu.column_name AS target_column,
                tc.constraint_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY tc.table_schema, tc.table_name
            """

            cur.execute(query)
            rows = cur.fetchall()

            for row in rows:
                relationships.append({
                    'source_schema': row['source_schema'],
                    'source_table': row['source_table'],
                    'source_column': row['source_column'],
                    'target_schema': row['target_schema'],
                    'target_table': row['target_table'],
                    'target_column': row['target_column'],
                    'relationship_type': 'foreign_key',
                    'constraint_name': row['constraint_name']
                })

            cur.close()
            conn.close()

            logger.info(f"Discovered {len(relationships)} foreign keys in PostgreSQL")

        except Exception as e:
            logger.debug(f"PostgreSQL relationship discovery failed: {e}")

        return relationships

    @staticmethod
    def _discover_mysql(db_url: str) -> list:
        """Discover foreign keys in MySQL"""
        relationships = []

        if mysql is None:
            logger.warning("mysql-connector-python not installed, skipping MySQL discovery")
            return relationships

        try:
            parsed = urlparse(db_url)
            conn = mysql.connector.connect(
                host=parsed.hostname,
                port=parsed.port or 3306,
                user=parsed.username,
                password=parsed.password,
                database=parsed.path.strip('/')
            )
            cur = conn.cursor(dictionary=True)

            query = """
            SELECT
                TABLE_SCHEMA AS source_schema,
                TABLE_NAME AS source_table,
                COLUMN_NAME AS source_column,
                REFERENCED_TABLE_SCHEMA AS target_schema,
                REFERENCED_TABLE_NAME AS target_table,
                REFERENCED_COLUMN_NAME AS target_column,
                CONSTRAINT_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE REFERENCED_TABLE_NAME IS NOT NULL
                AND TABLE_SCHEMA = DATABASE()
            ORDER BY TABLE_NAME
            """

            cur.execute(query)
            rows = cur.fetchall()

            for row in rows:
                relationships.append({
                    'source_schema': row['source_schema'],
                    'source_table': row['source_table'],
                    'source_column': row['source_column'],
                    'target_schema': row['target_schema'],
                    'target_table': row['target_table'],
                    'target_column': row['target_column'],
                    'relationship_type': 'foreign_key',
                    'constraint_name': row['CONSTRAINT_NAME']
                })

            cur.close()
            conn.close()

            logger.info(f"Discovered {len(relationships)} foreign keys in MySQL")

        except Exception as e:
            logger.debug(f"MySQL relationship discovery failed: {e}")

        return relationships

    @staticmethod
    def _discover_mongodb(db_url: str) -> list:
        """Infer relationships in MongoDB by analyzing field patterns"""
        relationships = []

        if MongoClient is None:
            logger.warning("pymongo not installed, skipping MongoDB discovery")
            return relationships

        try:
            client = MongoClient(db_url)
            db = client.get_database()

            seen_relationships = set()

            for collection_name in db.list_collection_names():
                # Sample documents
                sample_docs = list(db[collection_name].find().limit(10))

                for doc in sample_docs:
                    for field, value in doc.items():
                        # Pattern: field ends with '_id' and value is ObjectId
                        if field.endswith('_id') and field != '_id' and isinstance(value, ObjectId):
                            # Infer target collection
                            target_collection = field[:-3] + 's'  # e.g., customer_id → customers

                            # Avoid duplicates
                            rel_key = (collection_name, field, target_collection)
                            if rel_key not in seen_relationships:
                                seen_relationships.add(rel_key)

                                relationships.append({
                                    'source_schema': db.name,
                                    'source_table': collection_name,
                                    'source_column': field,
                                    'target_schema': db.name,
                                    'target_table': target_collection,
                                    'target_column': '_id',
                                    'relationship_type': 'inferred',
                                    'constraint_name': None
                                })

            client.close()
            logger.info(f"Inferred {len(relationships)} relationships in MongoDB")

        except Exception as e:
            logger.debug(f"MongoDB relationship discovery failed: {e}")

        return relationships

    @staticmethod
    def _discover_sqlite(db_url: str) -> list:
        """Discover foreign keys in SQLite"""
        relationships = []

        try:
            # Extract file path from URL
            db_path = db_url.replace('sqlite:///', '').replace('sqlite://', '')
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()

            # Get all tables
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cur.fetchall()]

            for table in tables:
                # Get foreign keys for this table
                cur.execute(f"PRAGMA foreign_key_list({table})")
                fks = cur.fetchall()

                for fk in fks:
                    relationships.append({
                        'source_schema': 'main',
                        'source_table': table,
                        'source_column': fk[3],  # from column
                        'target_schema': 'main',
                        'target_table': fk[2],   # to table
                        'target_column': fk[4],  # to column
                        'relationship_type': 'foreign_key',
                        'constraint_name': None
                    })

            cur.close()
            conn.close()

            logger.info(f"Discovered {len(relationships)} foreign keys in SQLite")

        except Exception as e:
            logger.debug(f"SQLite relationship discovery failed: {e}")

        return relationships
