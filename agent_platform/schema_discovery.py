"""
Multi-Database Schema Discovery Module

Discovers schemas from any database type:
- PostgreSQL
- MySQL
- MongoDB
- SQL Server
- SQLite
"""

from urllib.parse import urlparse
from typing import List, Dict
from loguru import logger
import psycopg2


class SchemaDiscovery:
    """Database-agnostic schema discovery."""

    @staticmethod
    def discover_schemas(db_url: str) -> List[Dict]:
        """
        Discover schemas from any database type.

        Args:
            db_url: Database connection URL

        Returns:
            List of dicts with keys: schema_name, table_name, column_name, data_type, is_nullable
        """
        parsed = urlparse(db_url)
        db_type = parsed.scheme.lower()

        logger.info(f"Discovering schemas for database type: {db_type}")

        if db_type in ['postgresql', 'postgres']:
            return SchemaDiscovery._discover_postgresql(db_url)
        elif db_type == 'mysql':
            return SchemaDiscovery._discover_mysql(db_url)
        elif db_type in ['mongodb', 'mongodb+srv']:
            return SchemaDiscovery._discover_mongodb(db_url)
        elif db_type == 'sqlite':
            return SchemaDiscovery._discover_sqlite(db_url)
        else:
            raise ValueError(f"Unsupported database type: {db_type}")

    @staticmethod
    def _discover_postgresql(db_url: str) -> List[Dict]:
        """Discover PostgreSQL schemas using information_schema."""
        logger.info("Using PostgreSQL schema discovery")

        try:
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()

            cur.execute("""
                SELECT
                    table_schema,
                    table_name,
                    column_name,
                    data_type,
                    is_nullable
                FROM information_schema.columns
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                ORDER BY table_schema, table_name, ordinal_position
            """)

            results = cur.fetchall()
            cur.close()
            conn.close()

            schemas = [
                {
                    'schema_name': row[0],
                    'table_name': row[1],
                    'column_name': row[2],
                    'data_type': row[3],
                    'is_nullable': row[4] == 'YES'
                }
                for row in results
            ]

            logger.info(f"Discovered {len(schemas)} columns from PostgreSQL")
            return schemas

        except Exception as e:
            logger.error(f"PostgreSQL schema discovery failed: {e}")
            raise

    @staticmethod
    def _discover_mysql(db_url: str) -> List[Dict]:
        """Discover MySQL schemas using information_schema."""
        logger.info("Using MySQL schema discovery")

        try:
            import mysql.connector

            parsed = urlparse(db_url)
            conn = mysql.connector.connect(
                host=parsed.hostname,
                port=parsed.port or 3306,
                user=parsed.username,
                password=parsed.password,
                database=parsed.path.lstrip('/') if parsed.path else None
            )

            cur = conn.cursor()
            cur.execute("""
                SELECT
                    TABLE_SCHEMA,
                    TABLE_NAME,
                    COLUMN_NAME,
                    DATA_TYPE,
                    IS_NULLABLE
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys')
                ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
            """)

            results = cur.fetchall()
            cur.close()
            conn.close()

            schemas = [
                {
                    'schema_name': row[0],
                    'table_name': row[1],
                    'column_name': row[2],
                    'data_type': row[3],
                    'is_nullable': row[4] == 'YES'
                }
                for row in results
            ]

            logger.info(f"Discovered {len(schemas)} columns from MySQL")
            return schemas

        except ImportError:
            logger.error("mysql-connector-python not installed. Run: pip install mysql-connector-python")
            raise
        except Exception as e:
            logger.error(f"MySQL schema discovery failed: {e}")
            raise

    @staticmethod
    def _discover_mongodb(db_url: str) -> List[Dict]:
        """Discover MongoDB schemas by sampling documents."""
        logger.info("Using MongoDB schema discovery (sampling)")

        try:
            from pymongo import MongoClient

            client = MongoClient(db_url)
            schemas = []

            # Get all databases
            for db_name in client.list_database_names():
                if db_name in ['admin', 'config', 'local']:
                    continue

                db = client[db_name]

                # Get all collections
                for coll_name in db.list_collection_names():
                    collection = db[coll_name]

                    # Sample first document to infer schema
                    sample = collection.find_one()

                    if sample:
                        for field_name, field_value in sample.items():
                            schemas.append({
                                'schema_name': db_name,
                                'table_name': coll_name,
                                'column_name': field_name,
                                'data_type': type(field_value).__name__,
                                'is_nullable': True  # MongoDB fields are always optional
                            })

            client.close()
            logger.info(f"Discovered {len(schemas)} fields from MongoDB")
            return schemas

        except ImportError:
            logger.error("pymongo not installed. Run: pip install pymongo")
            raise
        except Exception as e:
            logger.error(f"MongoDB schema discovery failed: {e}")
            raise

    @staticmethod
    def _discover_sqlite(db_url: str) -> List[Dict]:
        """Discover SQLite schemas using sqlite_master."""
        logger.info("Using SQLite schema discovery")

        try:
            import sqlite3

            # Remove sqlite:/// prefix
            db_path = db_url.replace('sqlite:///', '').replace('sqlite://', '')
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()

            schemas = []

            # Get all tables
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = cur.fetchall()

            for (table_name,) in tables:
                # Get column info for each table
                cur.execute(f"PRAGMA table_info({table_name})")
                columns = cur.fetchall()

                for col in columns:
                    schemas.append({
                        'schema_name': 'main',  # SQLite default schema
                        'table_name': table_name,
                        'column_name': col[1],
                        'data_type': col[2],
                        'is_nullable': col[3] == 0  # 0 = nullable, 1 = not null
                    })

            cur.close()
            conn.close()

            logger.info(f"Discovered {len(schemas)} columns from SQLite")
            return schemas

        except Exception as e:
            logger.error(f"SQLite schema discovery failed: {e}")
            raise
