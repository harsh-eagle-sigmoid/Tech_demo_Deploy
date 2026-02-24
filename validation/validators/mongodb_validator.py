"""
MongoDB-Specific Validator

Implements validation checks for MongoDB databases.
Note: MongoDB is schemaless, so validation focuses on data quality.
"""

from urllib.parse import urlparse
from typing import List, Dict
from loguru import logger
from validation.validators.base_validator import BaseValidator


class MongoDBValidator(BaseValidator):
    """MongoDB-specific validator using PyMongo."""

    def connect(self):
        """Create MongoDB connection."""
        try:
            from pymongo import MongoClient
            return MongoClient(self.db_url)
        except ImportError:
            logger.error("pymongo not installed. Run: pip install pymongo")
            raise

    def disconnect(self, conn):
        """Close MongoDB connection."""
        if conn:
            conn.close()

    def check_primary_keys(self, conn, schema_name: str, table_name: str) -> Dict:
        """MongoDB collections always have _id as primary key."""
        return {
            'has_pk': True,
            'pk_columns': '_id'
        }

    def check_null_values(self, conn, schema_name: str, table_name: str, column_name: str) -> Dict:
        """Count NULL or missing fields in MongoDB collection."""
        try:
            db = conn[schema_name]
            collection = db[table_name]

            # Count documents
            total_rows = collection.count_documents({})

            if total_rows == 0:
                return {
                    'total_rows': 0,
                    'null_count': 0,
                    'percentage': 0.0
                }

            # Count NULL or missing field
            null_count = collection.count_documents({
                '$or': [
                    {column_name: None},
                    {column_name: {'$exists': False}}
                ]
            })

            percentage = (null_count / total_rows * 100) if total_rows > 0 else 0

            return {
                'total_rows': total_rows,
                'null_count': null_count,
                'percentage': round(percentage, 2)
            }
        except Exception as e:
            logger.debug(f"NULL check failed for MongoDB: {e}")
            raise

    def check_duplicates(self, conn, schema_name: str, table_name: str, columns: List[str]) -> Dict:
        """Find duplicate documents based on specified fields."""
        try:
            db = conn[schema_name]
            collection = db[table_name]

            # Use first 5 columns for duplicate detection
            check_columns = [col for col in columns if col != '_id'][:5]

            if not check_columns:
                return {'count': 0}

            # Build aggregation pipeline to find duplicates
            group_by = {col: f'${col}' for col in check_columns}

            pipeline = [
                {
                    '$group': {
                        '_id': group_by,
                        'count': {'$sum': 1}
                    }
                },
                {
                    '$match': {
                        'count': {'$gt': 1}
                    }
                },
                {
                    '$count': 'duplicate_count'
                }
            ]

            result = list(collection.aggregate(pipeline))

            return {
                'count': result[0]['duplicate_count'] if result else 0
            }
        except Exception as e:
            logger.debug(f"Duplicate check failed for MongoDB: {e}")
            raise

    def check_table_size(self, conn, schema_name: str, table_name: str) -> Dict:
        """Get collection size and document count."""
        try:
            db = conn[schema_name]
            collection = db[table_name]

            # Get collection stats
            stats = db.command('collstats', table_name)

            total_size_mb = stats.get('size', 0) / 1024 / 1024
            row_count = stats.get('count', 0)

            return {
                'total_size': f"{total_size_mb:.2f} MB",
                'row_count': row_count
            }
        except Exception as e:
            logger.debug(f"Size check failed for MongoDB: {e}")
            raise

    def check_indexes(self, conn, schema_name: str, table_name: str) -> Dict:
        """List indexes on MongoDB collection."""
        try:
            db = conn[schema_name]
            collection = db[table_name]

            # Get indexes
            indexes = list(collection.list_indexes())

            # Exclude default _id index
            non_default_indexes = [
                idx for idx in indexes
                if idx.get('name') != '_id_'
            ]

            return {
                'count': len(non_default_indexes),
                'indexes': [
                    {
                        'name': idx.get('name'),
                        'keys': str(idx.get('key', {}))
                    }
                    for idx in non_default_indexes
                ]
            }
        except Exception as e:
            logger.debug(f"Index check failed for MongoDB: {e}")
            raise
