
import psycopg2
from psycopg2 import pool
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from loguru import logger

from config.settings import settings



Base = declarative_base()


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False
)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class DatabaseManager:
    

    def __init__(self):
        self.connection_pool = None
        self._initialize_pool()

    def _initialize_pool(self):
        
        try:
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                database=settings.DB_NAME,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD
            )
            logger.info("Database connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise

    def get_connection(self):
        
        if self.connection_pool:
            return self.connection_pool.getconn()
        raise Exception("Connection pool not initialized")

    def return_connection(self, conn):
        
        if self.connection_pool:
            self.connection_pool.putconn(conn)

    def close_all_connections(self):
        
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("All database connections closed")

    @contextmanager
    def get_cursor(self):
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            cursor.close()
            self.return_connection(conn)



db_manager = DatabaseManager()


@contextmanager
def get_db_session():
    
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Session error: {e}")
        raise
    finally:
        session.close()


def test_connection():
    
    try:
        with db_manager.get_cursor() as cursor:
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            logger.info(f"PostgreSQL version: {version[0]}")
            return True
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return False
