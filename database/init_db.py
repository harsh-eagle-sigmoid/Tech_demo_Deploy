"""
Database initialization script
Creates database, extensions, schemas, and tables
"""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from loguru import logger

from config.settings import settings


def create_database():
    """Create database if it doesn't exist"""
    try:
        # Connect to PostgreSQL server
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database="postgres"  # Connect to default database
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Check if database exists
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (settings.DB_NAME,)
        )
        exists = cursor.fetchone()

        if not exists:
            cursor.execute(f"CREATE DATABASE {settings.DB_NAME}")
            logger.info(f"Database '{settings.DB_NAME}' created successfully")
        else:
            logger.info(f"Database '{settings.DB_NAME}' already exists")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        logger.error(f"Error creating database: {e}")
        return False


def install_extensions():
    """Install required PostgreSQL extensions"""
    try:
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD
        )
        cursor = conn.cursor()

        # Install pgvector extension
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.commit()
        logger.info("pgvector extension installed")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        logger.error(f"Error installing extensions: {e}")
        return False


def create_schemas():
    """Create database schemas"""
    schemas = [
        "spend_data",
        "demand_data",
        "monitoring"
    ]

    try:
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD
        )
        cursor = conn.cursor()

        for schema in schemas:
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema};")
            logger.info(f"Schema '{schema}' created")

        conn.commit()
        cursor.close()
        conn.close()
        return True

    except Exception as e:
        logger.error(f"Error creating schemas: {e}")
        return False


def create_monitoring_tables():
    """Create monitoring framework tables"""

    monitoring_tables = """
    -- 1. queries table
    CREATE TABLE IF NOT EXISTS monitoring.queries (
        query_id SERIAL PRIMARY KEY,
        query_text TEXT NOT NULL,
        agent_type VARCHAR(20) NOT NULL,
        agent_response TEXT,
        generated_sql TEXT,
        execution_time_ms INTEGER,
        status VARCHAR(20),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        user_id VARCHAR(100),
        session_id VARCHAR(100)
    );

    -- 2. evaluations table
    CREATE TABLE IF NOT EXISTS monitoring.evaluations (
        evaluation_id SERIAL PRIMARY KEY,
        query_id VARCHAR(20) NOT NULL,
        query_text TEXT NOT NULL,
        agent_type VARCHAR(20) NOT NULL,
        complexity VARCHAR(20),
        generated_sql TEXT,
        ground_truth_sql TEXT,
        structural_score FLOAT,
        semantic_score FLOAT,
        llm_score FLOAT,
        final_score FLOAT,
        result VARCHAR(10),
        confidence FLOAT,
        reasoning TEXT,
        evaluation_data JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 3. errors table
    CREATE TABLE IF NOT EXISTS monitoring.errors (
        error_id SERIAL PRIMARY KEY,
        evaluation_id INTEGER REFERENCES monitoring.evaluations(evaluation_id),
        query_id INTEGER REFERENCES monitoring.queries(query_id),
        error_category VARCHAR(50),
        error_subcategory VARCHAR(50),
        error_message TEXT,
        stack_trace TEXT,
        severity VARCHAR(20),
        frequency_count INTEGER DEFAULT 1,
        confidence FLOAT,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 4. drift_monitoring table
    CREATE TABLE IF NOT EXISTS monitoring.drift_monitoring (
        drift_id SERIAL PRIMARY KEY,
        query_id INTEGER REFERENCES monitoring.queries(query_id),
        query_embedding VECTOR(384),
        drift_score FLOAT,
        drift_classification VARCHAR(20),
        similarity_to_baseline FLOAT,
        is_anomaly BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 5. baseline table
    CREATE TABLE IF NOT EXISTS monitoring.baseline (
        baseline_id SERIAL PRIMARY KEY,
        agent_type VARCHAR(20) NOT NULL,
        centroid_embedding VECTOR(384),
        num_queries INTEGER,
        avg_query_length FLOAT,
        common_keywords JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        version INTEGER DEFAULT 1
    );

    -- Create indexes for performance
    CREATE INDEX IF NOT EXISTS idx_query_agent ON monitoring.queries(agent_type);
    CREATE INDEX IF NOT EXISTS idx_query_created ON monitoring.queries(created_at);
    CREATE INDEX IF NOT EXISTS idx_eval_result ON monitoring.evaluations(evaluation_result);
    CREATE INDEX IF NOT EXISTS idx_error_category ON monitoring.errors(error_category);
    CREATE INDEX IF NOT EXISTS idx_drift_score ON monitoring.drift_monitoring(drift_score);
    """

    try:
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD
        )
        cursor = conn.cursor()

        cursor.execute(monitoring_tables)
        conn.commit()
        logger.info("Monitoring tables created successfully")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        logger.error(f"Error creating monitoring tables: {e}")
        return False


def initialize_database():
    """Complete database initialization"""
    logger.info("Starting database initialization...")

    # Step 1: Create database
    if not create_database():
        return False

    # Step 2: Install extensions
    if not install_extensions():
        return False

    # Step 3: Create schemas
    if not create_schemas():
        return False

    # Step 4: Create monitoring tables
    if not create_monitoring_tables():
        return False

    logger.info("Database initialization completed successfully!")
    return True


if __name__ == "__main__":
    # Configure logger
    logger.add("logs/database_init.log", rotation="10 MB")

    # Initialize database
    success = initialize_database()

    if success:
        print("✅ Database initialized successfully!")
    else:
        print("❌ Database initialization failed. Check logs for details.")
