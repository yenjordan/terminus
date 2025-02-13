# FastAPI React Starter Template

A modern, production-ready template featuring FastAPI backend, React frontend with Vite, SQLite database, and Docker support.

## Features

- **FastAPI Backend**
  - Health check endpoint
  - SQLite database integration
  - Environment configuration
  - CORS support

- **React Frontend**
  - Built with Vite for fast development
  - Tailwind CSS for styling
  - Environment configuration
  - API integration example

- **Development Tools**
  - Docker support
  - Docker Compose for local development
  - Hot-reloading for both frontend and backend

## Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- Node.js 20+ (for local development)

## Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/fastapi-react-starter.git
   cd fastapi-react-starter
   ```

2. Start the application using Docker Compose:
   ```bash
   docker-compose up --build
   ```

3. Access the applications:
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

## Local Development

### Backend

1. Create a virtual environment:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the FastAPI server:
   ```bash
   uvicorn app.main:app --reload
   ```

### Frontend

1. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```

2. Start the development server:
   ```bash
   npm run dev
   ```

## Project Structure

```
fastapi-react-starter/
│── backend/           # FastAPI backend
│   ├── app/
│   │   ├── main.py    # Entry point for FastAPI
│   │   ├── api/       # API routes
│   │   ├── db/        # Database setup (SQLite)
│   │   ├── core/      # Configuration settings
│   ├── Dockerfile     # Backend containerization
│   ├── requirements.txt  # Backend dependencies
│── frontend/          # React frontend
│   ├── src/
│   │   ├── components/
│   │   ├── pages/     # Landing page
│   ├── package.json   # Frontend dependencies
│── docker-compose.yml # Dev environment setup
│── README.md          # Project documentation
│── .env.example       # Example environment variables
```

## License

MIT
