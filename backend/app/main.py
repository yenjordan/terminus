from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.utils.logger import setup_logger
from app.routes.health import router as health_router
from app.routes.auth import router as auth_router
from app.routes.terminal import router as terminal_router
from app.routes.sessions import router as sessions_router
from app.routes.files import router as files_router
from app.routes.code_review import router as code_review_router
from app.db.database import init_db, engine
from app.config import get_settings

settings = get_settings()
logger = setup_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for the FastAPI application.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting application")
    try:
        await init_db()
        logger.info("Application started successfully")
        yield
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise
    finally:
        # Cleanup
        logger.info("Shutting down application")
        await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    lifespan=lifespan,
)

# cors
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# debug route
@app.get("/debug")
async def debug_api(request: Request):
    """Debug endpoint to check API routing in the backend app"""
    return JSONResponse(
        {
            "status": "Backend API debug endpoint working",
            "base_url": str(request.base_url),
            "url": str(request.url),
            "cors_origins": settings.CORS_ORIGINS,
            "routes": {"auth": "/auth/*", "register": "/auth/register", "login": "/auth/login"},
        }
    )


# include core routers firstfor basic functionality
app.include_router(health_router)
app.include_router(auth_router)

# include feature-specific routers, can be loaded conditionally if needed
try:
    # terminal and related features are loaded separately to prevent their dependencies from affecting core functionality like authentication
    app.include_router(terminal_router)
    app.include_router(sessions_router)
    app.include_router(files_router)
    app.include_router(code_review_router)
    logger.info("All application routes configured successfully")
except Exception as e:
    logger.error(f"Error loading feature-specific routes: {str(e)}")
    logger.info("Application will continue with core functionality only")

logger.info("Application startup complete")
