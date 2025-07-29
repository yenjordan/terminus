from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import AsyncAdaptedQueuePool
from app.utils.logger import setup_logger
from app.config import get_settings
from urllib.parse import quote_plus
import time
import os

settings = get_settings()
logger = setup_logger(__name__)


def get_database_url() -> str:
    """
    Constructs the database URL based on configuration.
    Prioritizes DATABASE_URL if set directly (for Render.com compatibility).
    Then prioritizes TEST_DATABASE_URL if set in 'testing' environment.
    Returns PostgreSQL URL if credentials are provided, otherwise falls back to SQLite.
    """
    # first check for a complete DATABASE_URL (Render.com provides this)
    if os.environ.get("DATABASE_URL"):
        db_url = os.environ.get("DATABASE_URL")
        logger.info(f"Using DATABASE_URL from environment: {db_url[:10]}...")
        # convert postgres:// to postgresql:// if needed (SQLAlchemy requirement)
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return db_url

    if settings.DATABASE_URL:
        logger.info(f"Using DATABASE_URL from settings: {settings.DATABASE_URL[:10]}...")
        # convert postgres:// to postgresql:// if needed
        if settings.DATABASE_URL.startswith("postgres://"):
            return settings.DATABASE_URL.replace("postgres://", "postgresql://", 1)
        return settings.DATABASE_URL

    if settings.ENVIRONMENT == "testing" and settings.TEST_DATABASE_URL:
        return settings.TEST_DATABASE_URL

    # checking for complete database configuration
    if settings.DB_NAME and settings.DB_USER and settings.DB_HOST and settings.DB_PORT:
        password = quote_plus(settings.DB_PASSWORD) if settings.DB_PASSWORD else ""
        return f"postgresql+asyncpg://{settings.DB_USER}:{password}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"

    logger.warning("No complete database configuration found, falling back to SQLite")
    return "sqlite+aiosqlite:///./terminus.db"


def create_engine_with_retry(database_url: str):
    """
    Creates an async engine with retry logic and appropriate configuration
    based on the database type.
    """
    connect_args = {}
    pooling_args = {
        "pool_pre_ping": True,
        "pool_recycle": 3600,
        "echo": False,
    }

    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    else:
        pooling_args.update(
            {
                "poolclass": AsyncAdaptedQueuePool,
                "pool_size": 20,
                "max_overflow": 10,
                "pool_timeout": 30,
            }
        )

    return create_async_engine(database_url, connect_args=connect_args, **pooling_args)


# get the db URL and log it
db_url = get_database_url()
masked_url = db_url[:10] + "..." if db_url else "None"
logger.info(f"Database URL: {masked_url}")

engine = create_engine_with_retry(db_url)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autocommit=False, autoflush=False
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """
    Dependency that provides a database session.
    Ensures proper handling of connections and error cases.
    """
    session = AsyncSessionLocal()
    logger.debug("Creating new database session")
    try:
        yield session
    except Exception as e:
        logger.error(f"Database session error: {str(e)}")
        await session.rollback()
        raise
    finally:
        logger.debug("Closing database session")
        await session.close()


async def init_db() -> None:
    """
    Initialize database tables and perform any startup database operations.
    Includes retry logic for initial connection.
    """
    logger.info("Initializing database")
    max_retries = 5
    retry_delay = 2  # seconds

    for attempt in range(1, max_retries + 1):
        try:
            # import models here to ensure they're registered with Base, avoids circular imports
            from app.db.models import (
                User,
                CodeSession,
                CodeFile,
                CodeExecution,
                CodeSubmission,
                CodeReview,
            )

            logger.info(f"Creating tables (attempt {attempt}/{max_retries})")
            async with engine.begin() as conn:
                # drop and recreate all tables in development mode for testing
                if (
                    settings.ENVIRONMENT == "development"
                    and os.environ.get("DROP_TABLES") == "true"
                ):
                    logger.warning("Development mode: Dropping all tables before creation")
                    await conn.run_sync(Base.metadata.drop_all)

                # create tables
                await conn.run_sync(Base.metadata.create_all)

            logger.info("Database tables created successfully")

            # verify tables exist by checking the users table
            async with AsyncSessionLocal() as session:
                from sqlalchemy import text

                result = await session.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
                )
                tables = result.fetchall()
                logger.info(f"Tables verified: {tables}")

                if not tables:
                    logger.warning("Users table not found after creation, will retry...")
                    if attempt < max_retries:
                        time.sleep(retry_delay)
                        continue
                    else:
                        logger.error("Failed to create tables after maximum retries")
                        raise Exception("Failed to create database tables")

            return
        except Exception as e:
            logger.error(f"Error initializing database (attempt {attempt}/{max_retries}): {str(e)}")
            if attempt < max_retries:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # exponential backoff
            else:
                logger.error("Failed to initialize database after maximum retries")
                raise
