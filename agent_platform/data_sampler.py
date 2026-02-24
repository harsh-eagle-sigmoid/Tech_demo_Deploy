"""
Sample data from agent databases for ground truth generation
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
except ImportError:
    MongoClient = None


class DataSampler:
    """Sample representative data from databases"""

    @staticmethod
    def sample_database(db_url: str, schemas: list, limit: int = 5) -> dict:
        """
        Sample data from all tables
        Returns dict: {table_name: [rows...]}
        """
        parsed = urlparse(db_url)
        db_type = parsed.scheme.lower()

        try:
            if db_type in ['postgresql', 'postgres']:
                return DataSampler._sample_postgresql(db_url, schemas, limit)
            elif db_type == 'mysql':
                return DataSampler._sample_mysql(db_url, schemas, limit)
            elif db_type in ['mongodb', 'mongodb+srv']:
                return DataSampler._sample_mongodb(db_url, schemas, limit)
            elif db_type == 'sqlite':
                return DataSampler._sample_sqlite(db_url, schemas, limit)
            else:
                return {}
        except Exception as e:
            logger.error(f"Failed to sample data: {e}")
            return {}

    @staticmethod
    def _sample_postgresql(db_url: str, schemas: list, limit: int) -> dict:
        """Sample data from PostgreSQL tables"""
        sample_data = {}

        try:
            conn = psycopg2.connect(db_url)
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            for schema in schemas:
                schema_name = schema['schema_name']

                for table in schema.get('tables', []):
                    table_name = table['table_name']
                    full_table = f"{schema_name}.{table_name}"

                    try:
                        cur.execute(f"SELECT * FROM {full_table} LIMIT {limit}")
                        rows = [dict(row) for row in cur.fetchall()]
                        sample_data[full_table] = rows
                    except Exception as e:
                        logger.debug(f"Could not sample {full_table}: {e}")
                        continue

            cur.close()
            conn.close()

            logger.info(f"Sampled {len(sample_data)} PostgreSQL tables")

        except Exception as e:
            logger.debug(f"PostgreSQL sampling failed: {e}")

        return sample_data

    @staticmethod
    def _sample_mysql(db_url: str, schemas: list, limit: int) -> dict:
        """Sample data from MySQL tables"""
        sample_data = {}

        if mysql is None:
            logger.warning("mysql-connector-python not installed, skipping MySQL sampling")
            return sample_data

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

            for schema in schemas:
                for table in schema.get('tables', []):
                    table_name = table['table_name']

                    try:
                        cur.execute(f"SELECT * FROM `{table_name}` LIMIT {limit}")
                        rows = cur.fetchall()
                        sample_data[table_name] = rows
                    except Exception as e:
                        logger.debug(f"Could not sample {table_name}: {e}")
                        continue

            cur.close()
            conn.close()

            logger.info(f"Sampled {len(sample_data)} MySQL tables")

        except Exception as e:
            logger.debug(f"MySQL sampling failed: {e}")

        return sample_data

    @staticmethod
    def _sample_mongodb(db_url: str, schemas: list, limit: int) -> dict:
        """Sample data from MongoDB collections"""
        sample_data = {}

        if MongoClient is None:
            logger.warning("pymongo not installed, skipping MongoDB sampling")
            return sample_data

        try:
            client = MongoClient(db_url)
            db = client.get_database()

            for schema in schemas:
                for table in schema.get('tables', []):
                    collection_name = table['table_name']

                    try:
                        docs = list(db[collection_name].find().limit(limit))
                        # Convert ObjectId to string for JSON serialization
                        for doc in docs:
                            if '_id' in doc:
                                doc['_id'] = str(doc['_id'])
                        sample_data[collection_name] = docs
                    except Exception as e:
                        logger.debug(f"Could not sample {collection_name}: {e}")
                        continue

            client.close()
            logger.info(f"Sampled {len(sample_data)} MongoDB collections")

        except Exception as e:
            logger.debug(f"MongoDB sampling failed: {e}")

        return sample_data

    @staticmethod
    def _sample_sqlite(db_url: str, schemas: list, limit: int) -> dict:
        """Sample data from SQLite tables"""
        sample_data = {}

        try:
            db_path = db_url.replace('sqlite:///', '').replace('sqlite://', '')
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            for schema in schemas:
                for table in schema.get('tables', []):
                    table_name = table['table_name']

                    try:
                        cur.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
                        rows = [dict(row) for row in cur.fetchall()]
                        sample_data[table_name] = rows
                    except Exception as e:
                        logger.debug(f"Could not sample {table_name}: {e}")
                        continue

            cur.close()
            conn.close()

            logger.info(f"Sampled {len(sample_data)} SQLite tables")

        except Exception as e:
            logger.debug(f"SQLite sampling failed: {e}")

        return sample_data
