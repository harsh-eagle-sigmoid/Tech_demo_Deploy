
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from loguru import logger

from config.settings import settings


def create_database():
    
    try:
       
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database="postgres"  
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        
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
   
    try:
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD
        )
        cursor = conn.cursor()

        
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
    
    schemas = [
        "spend_data",
        "demand_data",
        "monitoring",
        "platform"
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
    

    monitoring_tables = """
    -- Drop tables if they exist to apply schema changes
    DROP TABLE IF EXISTS monitoring.drift_monitoring CASCADE;
    DROP TABLE IF EXISTS monitoring.errors CASCADE;
    DROP TABLE IF EXISTS monitoring.evaluations CASCADE;
    DROP TABLE IF EXISTS monitoring.queries CASCADE;
    DROP TABLE IF EXISTS monitoring.baseline CASCADE;

    -- 1. queries table
    CREATE TABLE IF NOT EXISTS monitoring.queries (
        query_id VARCHAR(50) PRIMARY KEY,
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
        query_id VARCHAR(50) NOT NULL UNIQUE REFERENCES monitoring.queries(query_id),
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
        query_id VARCHAR(50) REFERENCES monitoring.queries(query_id),
        error_category VARCHAR(50),
        error_subcategory VARCHAR(50),
        error_message TEXT,
        stack_trace TEXT,
        severity VARCHAR(20),
        frequency_count INTEGER DEFAULT 1,
        confidence FLOAT,
        suggested_fix TEXT,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 4. drift_monitoring table
    CREATE TABLE IF NOT EXISTS monitoring.drift_monitoring (
        drift_id SERIAL PRIMARY KEY,
        query_id VARCHAR(50) UNIQUE REFERENCES monitoring.queries(query_id),
        query_embedding VECTOR(1024),
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
        centroid_embedding VECTOR(1024),
        num_queries INTEGER,
        avg_query_length FLOAT,
        common_keywords JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        version INTEGER DEFAULT 1
    );

    -- Create indexes for performance
    CREATE INDEX IF NOT EXISTS idx_query_agent ON monitoring.queries(agent_type);
    CREATE INDEX IF NOT EXISTS idx_query_created ON monitoring.queries(created_at);
    CREATE INDEX IF NOT EXISTS idx_eval_result ON monitoring.evaluations(result);
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


def create_platform_tables():
    """Create platform schema tables for dynamic agent registry."""

    platform_tables = """
    -- Agent registry
    CREATE TABLE IF NOT EXISTS platform.agents (
        agent_id        SERIAL PRIMARY KEY,
        agent_name      VARCHAR(100) UNIQUE NOT NULL,
        display_name    VARCHAR(200),
        description     TEXT,
        db_url          TEXT NOT NULL,
        agent_url       VARCHAR(500),
        status          VARCHAR(20) DEFAULT 'pending',
        poll_interval_s INTEGER DEFAULT 30,
        last_polled_at  TIMESTAMP,
        last_error      TEXT,
        api_key_hash    VARCHAR(128),
        api_key_prefix  VARCHAR(20),
        gt_status       VARCHAR(20) DEFAULT 'pending',
        gt_error        TEXT,
        gt_generated_at TIMESTAMP,
        gt_query_count  INTEGER,
        gt_retry_count  INTEGER DEFAULT 0,
        gt_last_retry_at TIMESTAMP,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Discovered schema columns from agent's DB
    CREATE TABLE IF NOT EXISTS platform.discovered_schemas (
        schema_id     SERIAL PRIMARY KEY,
        agent_id      INTEGER NOT NULL REFERENCES platform.agents(agent_id) ON DELETE CASCADE,
        schema_name   VARCHAR(100) NOT NULL,
        table_name    VARCHAR(200) NOT NULL,
        column_name   VARCHAR(200) NOT NULL,
        data_type     VARCHAR(100),
        is_nullable   BOOLEAN DEFAULT TRUE,
        discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(agent_id, schema_name, table_name, column_name)
    );

    -- Detected query log table config + watermark per agent
    CREATE TABLE IF NOT EXISTS platform.query_log_config (
        config_id           SERIAL PRIMARY KEY,
        agent_id            INTEGER UNIQUE NOT NULL REFERENCES platform.agents(agent_id) ON DELETE CASCADE,
        schema_name         VARCHAR(100) NOT NULL,
        table_name          VARCHAR(200) NOT NULL,
        query_text_column   VARCHAR(200) NOT NULL,
        sql_column          VARCHAR(200) NOT NULL,
        timestamp_column    VARCHAR(200) NOT NULL,
        status_column       VARCHAR(200),
        error_column        VARCHAR(200),
        id_column           VARCHAR(200),
        last_seen_timestamp TIMESTAMP,
        last_seen_id        BIGINT,
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_platform_agents_name    ON platform.agents(agent_name);
    CREATE INDEX IF NOT EXISTS idx_platform_agents_status  ON platform.agents(status);
    CREATE INDEX IF NOT EXISTS idx_platform_agents_keyhash ON platform.agents(api_key_hash);
    CREATE INDEX IF NOT EXISTS idx_discovered_agent        ON platform.discovered_schemas(agent_id);
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
        cursor.execute(platform_tables)
        conn.commit()
        logger.info("Platform tables created successfully")
        cursor.close()
        conn.close()
        return True

    except Exception as e:
        logger.error(f"Error creating platform tables: {e}")
        return False


def migrate_health_columns():
    """Add health check columns to platform.agents if they don't exist."""
    try:
        conn = psycopg2.connect(
            host=settings.DB_HOST, port=settings.DB_PORT,
            database=settings.DB_NAME, user=settings.DB_USER,
            password=settings.DB_PASSWORD
        )
        cursor = conn.cursor()
        for col, dtype, default in [
            ("health_status", "VARCHAR(20)", "'unknown'"),
            ("health_detail", "TEXT", "NULL"),
            ("last_health_check_at", "TIMESTAMP", "NULL"),
        ]:
            cursor.execute(f"""
                ALTER TABLE platform.agents
                ADD COLUMN IF NOT EXISTS {col} {dtype} DEFAULT {default}
            """)
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("Health columns migrated successfully")
        return True
    except Exception as e:
        logger.error(f"migrate_health_columns failed: {e}")
        return False


def initialize_database():

    logger.info("Starting database initialization...")


    if not create_database():
        return False


    if not install_extensions():
        return False


    if not create_schemas():
        return False


    if not create_monitoring_tables():
        return False

    if not create_platform_tables():
        return False

    migrate_health_columns()

    logger.info("Database initialization completed successfully!")
    return True


if __name__ == "__main__":
    
    logger.add("logs/database_init.log", rotation="10 MB")

    
    success = initialize_database()

    if success:
        print("✅ Database initialized successfully!")
    else:
        print("❌ Database initialization failed. Check logs for details.")
