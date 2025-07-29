#!/bin/bash
set -e

echo "Starting Terminus Backend..."

# Wait for database to be ready (if using external database)
if [ -n "$DATABASE_URL" ]; then
  echo "Waiting for database to be ready..."
  # Extract host and port from DATABASE_URL
  if [[ "$DATABASE_URL" == postgresql* ]]; then
    # Extract host and port from PostgreSQL URL
    DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\).*/\1/p')
    DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    
    if [ -z "$DB_PORT" ]; then
      DB_PORT=5432  # Default PostgreSQL port
    fi
    
    echo "Checking PostgreSQL connection to $DB_HOST:$DB_PORT..."
    
    # Wait for the PostgreSQL database to be ready
    MAX_RETRIES=30
    RETRY_COUNT=0
    
    until nc -z $DB_HOST $DB_PORT; do
      RETRY_COUNT=$((RETRY_COUNT+1))
      if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        echo "Failed to connect to PostgreSQL database after $MAX_RETRIES attempts. Continuing anyway..."
        break
      fi
      echo "PostgreSQL database is not ready yet. Waiting... ($RETRY_COUNT/$MAX_RETRIES)"
      sleep 2
    done
    
    if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
      echo "PostgreSQL database is ready!"
    fi
  fi
fi

# Initialize database with multiple retries
echo "Running database initialization script..."
MAX_DB_INIT_RETRIES=5
DB_INIT_RETRY_COUNT=0

until python -m app.db.initialize_db; do
  DB_INIT_RETRY_COUNT=$((DB_INIT_RETRY_COUNT+1))
  if [ $DB_INIT_RETRY_COUNT -eq $MAX_DB_INIT_RETRIES ]; then
    echo "Failed to initialize database after $MAX_DB_INIT_RETRIES attempts."
    echo "Continuing startup, but the application may not work correctly."
    break
  fi
  echo "Database initialization failed. Retrying in 3 seconds... ($DB_INIT_RETRY_COUNT/$MAX_DB_INIT_RETRIES)"
  sleep 3
done

# Start the application
echo "Starting application..."
exec uvicorn root_app:app --host 0.0.0.0 --port 8000 