from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="Repository Server", stateless_http=True)


@mcp.tool(description="Database Server that Gives the details about the user.")
def get_user_info(user_id: str) -> str:
    # Here you would implement the logic to retrieve user information from the database
    return f"User information for {user_id}"