from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="Repository Server", stateless_http=True)


@mcp.tool(description="Repository Server that Gives the details about the github of the user.")
def get_github_info(username: str) -> str:
    # Here you would implement the logic to retrieve GitHub information for the user
    return f"GitHub information for {username}"