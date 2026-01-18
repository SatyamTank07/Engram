"""
FastMCP server for PersonIdentity CRUD operations.
Allows LLMs to interact with the PersonIdentity database table.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import backend modules
sys.path.append(str(Path(__file__).parent.parent))

from fastmcp import FastMCP
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import tools
from mcp_server.tools import (
    create_person_tool,
    get_person_tool,
    list_persons_tool,
    update_person_tool,
    delete_person_tool,
    search_person_tool
)

# Initialize FastMCP server
mcp = FastMCP("PersonIdentity CRUD Server")

# Register all tools
mcp.tool()(create_person_tool)
mcp.tool()(get_person_tool)
mcp.tool()(list_persons_tool)
mcp.tool()(update_person_tool)
mcp.tool()(delete_person_tool)
mcp.tool()(search_person_tool)


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()