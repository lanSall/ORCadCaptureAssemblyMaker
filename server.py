"""MCP server that executes TCL commands over a TCP socket."""

import socket

from mcp.server.fastmcp import FastMCP

HOST = "localhost"
PORT = 9020
RECV_BUFSIZE = 65536
TIMEOUT_SECONDS = 30.0

mcp = FastMCP("tcl-mcp-server")


@mcp.tool()
def execute_tcl(command: str) -> str:
    """Send a TCL command to localhost:9020 and return the response."""
    with socket.create_connection((HOST, PORT), timeout=TIMEOUT_SECONDS) as sock:
        sock.settimeout(TIMEOUT_SECONDS)
        sock.sendall(command.encode("utf-8"))
        response = sock.recv(RECV_BUFSIZE)
    return response.decode("utf-8", errors="replace")


if __name__ == "__main__":
    mcp.run()
