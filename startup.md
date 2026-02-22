# Startup Guide - Engram

This guide provides instructions on how to start the Engram application using various methods.

## Prerequisites

- **Docker & Docker Compose**: Recommended for the easiest setup.
- **Node.js 20+**: Required for manual frontend development.
- **Python 3.10+**: Required for manual backend/MCP development.
- **Google API Key**: Required for the AI agent (Gemini).

## 1. Quick Start (Docker - Recommended)

The simplest way to run the entire stack (Database, Backend, and Frontend) is using Docker Compose.

1.  **Configure Environment**:
    Ensure you have a `.env` file in the root directory with your `GOOGLE_API_KEY`.
    ```env
    GOOGLE_API_KEY=your_gemini_api_key_here
    ```

2.  **Start Services**:
    ```bash
    docker-compose up -d
    ```

3.  **Access the App**:
    - **Frontend**: [http://localhost:3000](http://localhost:3000)
    - **Backend API**: [http://localhost:8000](http://localhost:8000)
    - **API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 2. Manual Setup (Development Mode)

If you want to run components individually for development, follow these steps:

### A. Database (PostgreSQL)
The application expects a PostgreSQL database. You can run one via Docker:
```bash
docker run --name engram-db -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=engram -p 5432:5432 -d postgres:15-alpine
```

### B. Backend (FastAPI)
1.  Navigate to the backend directory:
    ```bash
    cd backend
    ```
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Run the server:
    ```bash
    uvicorn app.main:app --reload
    ```

### C. Frontend (Next.js)
1.  Navigate to the frontend directory:
    ```bash
    cd frontend
    ```
2.  Install dependencies:
    ```bash
    npm install
    ```
3.  Start the development server:
    ```bash
    npm run dev
    ```

### D. MCP Server
If you need to run the Model Context Protocol server separately:
```bash
python -m mcp_server.server
```

---

## 3. Creating a User
Once the application is running, you need to create a user to log in.

**Using Curl:**
```bash
curl -X POST http://localhost:8000/api/auth/register \
     -H "Content-Type: application/json" \
     -d "{\"phone\": \"1234567890\", \"password\": \"yourpassword123\"}"
```
*Note: See [USER_CREATION.md](USER_CREATION.md) for more details.*

## Troubleshooting

- **Database Connection**: Ensure `DATABASE_URL` in your environment matches your PostgreSQL setup.
- **Port Conflicts**: If port 3000 or 8000 is taken, the services might fail to start.
- **Docker Issues**: Try `docker-compose down -v` to clear volumes if you encounter persistent database issues.
