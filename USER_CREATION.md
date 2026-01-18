# User Creation Guide

## Create a User via curl (Windows CMD)

To create a new user, run this command in **CMD** (not PowerShell):

```cmd
curl -X POST http://localhost:8000/api/auth/register -H "Content-Type: application/json" -d "{\"phone\": \"1234567890\", \"password\": \"yourpassword123\"}"
```

**Important:** Use double quotes and escape inner quotes with backslash `\"`

### Response
```json
{
  "id": 1,
  "phone": "1234567890",
  "created_at": "2026-01-18T..."
}
```


## Test Login

```cmd
curl -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" -d "{\"phone\": \"1234567890\", \"password\": \"yourpassword123\"}"
```

### Response
```json
{
  "access_token": "eyJ0eXAiOiJ...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "phone": "1234567890",
    "created_at": "..."
  }
}
```

Now you can login at **http://localhost:3000/login** with your phone and password!
