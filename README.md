# Terminus

Terminus is a web-based Python code execution platform featuring an integrated terminal environment that's built with React, TypeScript, Tailwind CSS, and FastAPI to provide a complete IDE-like experience for Python development in the browser. It includes a code review system with dedicated attempter and reviewer roles to enable a structured workflow where users can write, submit, review, and improve code through an iterative feedback process.

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Node.js 22+ (for local development)
- Python 3.11+ (for local development)

### Running with Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/yenjordan/terminus.git
   cd terminus
   ```

2. **Start the application**
   ```bash
   docker compose up --build
   ```

3. **Access the application**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000

## Technical Architecture

### System Overview