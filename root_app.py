from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.main import app as api_app
import os
import sys
import traceback
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

app = FastAPI()

# Mount the API at /api
app.mount("/api", api_app)

# Define a list of known static file paths that should be served directly
STATIC_FILE_EXTENSIONS = ['.js', '.css', '.svg', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.woff', '.woff2', '.ttf', '.eot']

# Mount static files from the frontend build
try:
    # Try to mount the assets directory
    if os.path.isdir("static/assets"):
        app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")
        print(f"Mounted static assets from: {os.path.abspath('static/assets')}")
    else:
        print(f"Warning: static/assets directory not found at: {os.path.abspath('static/assets')}")
    
    # Mount other specific static directories, but not the root
    for dir_name in ['images', 'fonts', 'media']:
        dir_path = f"static/{dir_name}"
        if os.path.isdir(dir_path):
            app.mount(f"/{dir_name}", StaticFiles(directory=dir_path), name=dir_name)
            print(f"Mounted static directory: {os.path.abspath(dir_path)}")
except Exception as e:
    print(f"Error mounting static files: {str(e)}")
    traceback.print_exc()


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_redirect():
    return RedirectResponse(url="/api/docs")


# Special debugging routes
@app.get("/api-debug")
async def api_debug():
    """Debug endpoint to check API routing"""
    return JSONResponse(
        {
            "status": "API debug endpoint working",
            "routes": {
                "api": "/api/*",
                "auth": "/api/auth/*",
                "register": "/api/auth/register",
                "login": "/api/auth/login",
            },
        }
    )

# Add static file debugging endpoint
@app.get("/static-debug")
async def static_debug():
    """Debug endpoint to check static files"""
    static_dir = os.path.abspath("static")
    assets_dir = os.path.abspath("static/assets")
    
    static_files = []
    if os.path.exists(static_dir):
        static_files = os.listdir(static_dir)
    
    assets_files = []
    if os.path.exists(assets_dir):
        assets_files = os.listdir(assets_dir)
    
    index_content = None
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, 'r') as f:
            try:
                content = f.read()
                index_content = content[:500] + "..." if len(content) > 500 else content
            except Exception as e:
                index_content = f"Error reading file: {str(e)}"
    
    return JSONResponse({
        "static_dir_exists": os.path.exists(static_dir),
        "static_dir_path": static_dir,
        "static_files": static_files,
        "assets_dir_exists": os.path.exists(assets_dir),
        "assets_dir_path": assets_dir,
        "assets_files": assets_files,
        "index_html_exists": os.path.exists(index_path),
        "index_html_preview": index_content
    })


@app.get("/db-check")
async def db_check():
    """Direct database check endpoint"""
    try:
        # Get database URL from environment or use SQLite
        database_url = os.environ.get("DATABASE_URL", "")
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)

        if not database_url:
            database_url = "sqlite+aiosqlite:///./terminus.db"

        # Create engine and test connection
        connect_args = {}
        if database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False

        engine = create_async_engine(database_url, connect_args=connect_args)

        tables = []
        try:
            async with AsyncSession(engine) as session:
                # Check if tables exist
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

                # Check users table specifically
                try:
                    result = await session.execute(text("SELECT COUNT(*) FROM users"))
                    user_count = result.scalar()
                except Exception as e:
                    user_count = f"Error: {str(e)}"
        finally:
            await engine.dispose()

        return {
            "status": "Database check completed",
            "database_url_type": database_url.split("://")[0],
            "tables": tables,
            "users_table_exists": "users" in [t.lower() for t in tables],
            "user_count": user_count if "user_count" in locals() else None,
        }
    except Exception as e:
        error_detail = f"Database check error: {str(e)}\n{traceback.format_exc()}"
        return JSONResponse(status_code=500, content={"error": error_detail})


@app.post("/auth/register")
async def catch_wrong_register(request: Request):
    """Catch requests to the wrong register endpoint"""
    body = await request.json()
    return JSONResponse(
        {
            "error": "Wrong endpoint! You're hitting /auth/register instead of /api/auth/register",
            "received_data": body,
            "correct_endpoint": "/api/auth/register",
        },
        status_code=404,
    )


@app.post("/auth/login")
async def catch_wrong_login(request: Request):
    """Catch requests to the wrong login endpoint"""
    body = await request.json()
    return JSONResponse(
        {
            "error": "Wrong endpoint! You're hitting /auth/login instead of /api/auth/login",
            "received_data": body,
            "correct_endpoint": "/api/auth/login",
        },
        status_code=404,
    )


# Helper function to check if a path is a static file
def is_static_file(path: str) -> bool:
    """Check if a path points to a static file based on extension"""
    return any(path.endswith(ext) for ext in STATIC_FILE_EXTENSIONS)


# Serve frontend index.html for all other routes
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str, request: Request):
    # Log the requested path for debugging
    print(f"Request path: {full_path}")
    
    # Check if the path is for a static file
    if is_static_file(full_path):
        static_file_path = f"static/{full_path}"
        if os.path.isfile(static_file_path):
            return FileResponse(static_file_path)
    
    # For direct access to static files in root directory
    static_file_path = f"static/{full_path}"
    if os.path.isfile(static_file_path) and not full_path.startswith("api/"):
        return FileResponse(static_file_path)
    
    # For all other paths, serve the index.html for client-side routing
    if os.path.isfile("static/index.html"):
        return FileResponse("static/index.html")
    else:
        # Check if we have the fallback HTML file
        fallback_path = "static/fallback.html"
        if os.path.isfile(fallback_path):
            return FileResponse(fallback_path)
            
        # Final fallback if no HTML files exist
        return HTMLResponse(
            """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Terminus IDE</title>
  <style>
    body {
      font-family: system-ui, sans-serif;
      max-width: 800px;
      margin: 0 auto;
      padding: 2rem;
      line-height: 1.6;
      color: #333;
    }
    h1 { margin-bottom: 1rem; }
    a { color: #0066cc; }
    .debug { margin-top: 2rem; padding: 1rem; background: #f5f5f5; border-radius: 4px; }
    @media (prefers-color-scheme: dark) {
      body { background: #222; color: #eee; }
      .debug { background: #333; }
      a { color: #4da6ff; }
    }
  </style>
</head>
<body>
  <h1>Terminus IDE</h1>
  <p>The API is running but the frontend could not be loaded.</p>
  <p>API is available at <a href='/api/docs'>/api/docs</a></p>
  <div class="debug">
    <p><strong>Debug Information:</strong></p>
    <p>Check static files status at <a href='/static-debug'>/static-debug</a></p>
    <p>Check API status at <a href='/api-debug'>/api-debug</a></p>
    <p>Check database status at <a href='/db-check'>/db-check</a></p>
  </div>
</body>
</html>"""
        )
