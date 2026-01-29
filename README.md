# Engram

A personal AI assistant with memory and identity management capabilities.

## Features

- **User Authentication**: Secure phone-based authentication with JWT tokens
- **Chat Sessions**: Persistent chat conversations with AI
- **Person Identity Management**: Track and manage information about people you interact with
- **MCP Server**: Model Context Protocol server for LLM integration with person identities

## Tech Stack

### Backend
- **FastAPI**: Modern Python web framework
- **PostgreSQL**: Database for users, chats, and person identities
- **SQLAlchemy**: ORM for database operations
- **LangChain**: AI agent framework with Google Gemini
- **FastMCP**: MCP server implementation

### Frontend
- **Next.js 16**: React framework with App Router
- **TypeScript**: Type-safe development
- **Tailwind CSS**: Utility-first styling

## Getting Started

### Prerequisites
- Docker and Docker Compose
- Node.js 20+ (for frontend development)

### Running with Docker

1. **Start all services**:
   ```bash
   docker-compose up -d
   ```

2. **Check services are running**:
   ```bash
   docker-compose ps
   ```

3. **Access the application**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Creating Your First User

See [USER_CREATION.md](USER_CREATION.md) for detailed instructions on creating a user account.

Quick command (Windows CMD):
```cmd
curl -X POST http://localhost:8000/api/auth/register -H "Content-Type: application/json" -d "{\"phone\": \"1234567890\", \"password\": \"yourpassword123\"}"
```

## Project Structure

```
engram/
├── backend/           # FastAPI application
│   ├── app/
│   │   ├── main.py       # API endpoints
│   │   ├── database.py   # Database models
│   │   ├── crud.py       # Database operations
│   │   ├── schemas.py    # Pydantic schemas
│   │   ├── auth.py       # Authentication logic
│   │   └── agent.py      # LangChain AI agent
│   └── Dockerfile
├── frontend/          # Next.js application
│   ├── app/
│   │   ├── page.tsx      # Home page
│   │   ├── login/        # Login page
│   │   └── chat/         # Chat interface
│   └── package.json
├── mcp_server/        # MCP server for person identities
│   ├── server.py         # FastMCP server
│   └── tools.py          # MCP tools
└── docker-compose.yml # Docker orchestration
```

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get JWT token
- `GET /api/auth/me` - Get current user info

### Chat Sessions
- `POST /api/sessions` - Create new chat session
- `GET /api/sessions` - Get all user sessions
- `GET /api/sessions/{id}/messages` - Get session messages
- `DELETE /api/sessions/{id}` - Delete session
- `POST /api/chat` - Send message and get AI response

### Person Identities
- `POST /api/persons` - Create person identity
- `GET /api/persons` - List all persons
- `GET /api/persons/{id}` - Get specific person
- `PUT /api/persons/{id}` - Update person
- `DELETE /api/persons/{id}` - Delete person

## Development

### Backend Development
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend Development
```bash
cd frontend
npm install
npm run dev
```

### MCP Server
```bash
python -m mcp_server.server
```

## Environment Variables

Create a `.env` file in the root directory:
```env
GOOGLE_API_KEY=your_google_api_key_here
MCP_DEFAULT_USER_ID=your_default_user_id_here
```

## License

MIT
