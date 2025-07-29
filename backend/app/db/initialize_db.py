import asyncio
import os
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase
import traceback

# Add parent directory to path so we can import from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.db.models import (
    Base,
    User,
    CodeSession,
    CodeFile,
    CodeExecution,
    CodeSubmission,
    CodeReview,
)
from app.config.config import get_settings

settings = get_settings()


async def initialize_database():
    print("Starting database initialization script...")

    # Get database URL
    database_url = os.environ.get("DATABASE_URL", "")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    if not database_url:
        # Fall back to settings or SQLite
        if settings.DATABASE_URL:
            database_url = settings.DATABASE_URL
        else:
            database_url = "sqlite+aiosqlite:///./terminus.db"
            print(f"No DATABASE_URL found, using SQLite: {database_url}")

    print(f"Using database URL: {database_url[:10]}...")

    # Create engine
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_async_engine(
        database_url, connect_args=connect_args, echo=True  # Show SQL for debugging
    )

    try:
        # Create all tables
        print("Creating database tables...")
        async with engine.begin() as conn:
            # Check if tables already exist
            if database_url.startswith("sqlite"):
                result = await conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                )
            else:
                result = await conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
                    )
                )

            existing_tables = [row[0] for row in result.fetchall()]
            print(f"Existing tables: {existing_tables}")

            # Always create tables that don't exist
            await conn.run_sync(Base.metadata.create_all)
            print("Tables created or verified")

        # Verify tables exist and are properly structured
        async with AsyncSession(engine) as session:
            print("Verifying tables...")
            if database_url.startswith("sqlite"):
                result = await session.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                )
            else:
                result = await session.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
                    )
                )

            tables = [row[0] for row in result.fetchall()]
            print(f"Tables in database: {tables}")

            if "users" not in [t.lower() for t in tables]:
                print("ERROR: Users table not found after creation!")
                return False

            # Verify users table structure
            try:
                if database_url.startswith("sqlite"):
                    result = await session.execute(text("PRAGMA table_info(users)"))
                    columns = [row[1] for row in result.fetchall()]  # Column name is at index 1
                else:
                    result = await session.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns WHERE table_name='users'"
                        )
                    )
                    columns = [row[0] for row in result.fetchall()]

                print(f"Users table columns: {columns}")

                # Check for required columns
                required_columns = ["id", "email", "username", "hashed_password", "role"]
                missing_columns = [
                    col
                    for col in required_columns
                    if col.lower() not in [c.lower() for c in columns]
                ]

                if missing_columns:
                    print(f"WARNING: Users table is missing columns: {missing_columns}")
                    # Don't recreate the table here, as it might contain data
            except Exception as e:
                print(f"Error verifying users table structure: {str(e)}")
                traceback.print_exc()

            # Create a test user if none exists
            try:
                result = await session.execute(text("SELECT COUNT(*) FROM users"))
                user_count = result.scalar()
                print(f"User count: {user_count}")

                if user_count == 0:
                    print("Creating test admin user...")
                    test_user = User(
                        email="admin@example.com", username="admin", role="admin", is_superuser=True
                    )
                    test_user.set_password("admin123")
                    session.add(test_user)
                    await session.commit()
                    print("Test admin user created successfully")
            except Exception as e:
                print(f"Error checking/creating test user: {str(e)}")
                traceback.print_exc()
                await session.rollback()

        print("Database initialization completed successfully!")
        return True

    except Exception as e:
        print(f"Error initializing database: {str(e)}")
        traceback.print_exc()
        return False
    finally:
        await engine.dispose()


if __name__ == "__main__":
    success = asyncio.run(initialize_database())
    sys.exit(0 if success else 1)
