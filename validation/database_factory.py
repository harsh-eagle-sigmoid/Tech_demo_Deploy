"""
Database Validator Factory

Creates appropriate validator based on database URL.
"""

from urllib.parse import urlparse
from loguru import logger


class DatabaseValidatorFactory:
    """Factory to create appropriate validator based on database type."""

    @staticmethod
    def create_validator(agent_id: int, db_url: str):
        """
        Detect database type from URL and return appropriate validator.

        Args:
            agent_id: Agent ID
            db_url: Database connection URL

        Returns:
            Appropriate validator instance (PostgreSQLValidator, MySQLValidator, etc.)

        Examples:
            postgresql://... → PostgreSQLValidator
            mysql://... → MySQLValidator
            mongodb://... → MongoDBValidator
        """
        parsed = urlparse(db_url)
        scheme = parsed.scheme.lower()

        logger.info(f"Creating validator for database type: {scheme}")

        if scheme in ['postgresql', 'postgres']:
            from validation.validators.postgresql_validator import PostgreSQLValidator
            return PostgreSQLValidator(agent_id, db_url)

        elif scheme == 'mysql':
            from validation.validators.mysql_validator import MySQLValidator
            return MySQLValidator(agent_id, db_url)

        elif scheme in ['mongodb', 'mongodb+srv']:
            from validation.validators.mongodb_validator import MongoDBValidator
            return MongoDBValidator(agent_id, db_url)

        elif scheme == 'sqlite':
            from validation.validators.sqlite_validator import SQLiteValidator
            return SQLiteValidator(agent_id, db_url)

        else:
            logger.error(f"Unsupported database type: {scheme}")
            raise ValueError(f"Unsupported database type: {scheme}")
