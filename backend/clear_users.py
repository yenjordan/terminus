import asyncio
import typer
from sqlalchemy import delete
from app.db.models import User
from app.db.database import AsyncSessionLocal, init_db
from app.utils.logger import setup_logger

app = typer.Typer()
logger = setup_logger(__name__)

async def clear_users_async():
    """Delete all users from the database."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            # Delete all users
            stmt = delete(User)
            result = await session.execute(stmt)
            count = result.rowcount
            logger.info(f"Deleted {count} users from the database")
            return count

@app.command()
def clear_users():
    """Clear all users from the database."""
    typer.echo("Clearing all users from the database...")
    try:
        count = asyncio.run(clear_users_async())
        typer.secho(f"Successfully deleted {count} users from the database.", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"An error occurred: {e}", fg=typer.colors.RED, err=True)

if __name__ == "__main__":
    app() 