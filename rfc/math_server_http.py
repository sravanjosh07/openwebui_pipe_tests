"""
HTTP version of the Math MCP Server

This creates an HTTP endpoint that serves the same math tools as math_server.py
but over HTTP instead of stdio.

Run with: python math_server_http.py
Serves at: http://localhost:8001/mcp
"""

import asyncio
import json
from aiohttp import web
from mcp.server.fastmcp import FastMCP

# Create the FastMCP instance
mcp = FastMCP("Math")

@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers (ints or floats)"""
    return a + b

@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract b from a (ints or floats)"""
    return a - b

@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers (ints or floats)"""
    return a * b

@mcp.tool()
def divide(numerator: float, denominator: float) -> float:
    """Divide numerator by denominator (floats ok)"""
    if denominator == 0:
        raise ValueError("Cannot divide by zero")
    return numerator / denominator

@mcp.tool()
def power(base: float, exponent: float) -> float:
    """Raise base to the power of exponent (floats ok)"""
    return base ** exponent

@mcp.tool()
def sqrt(number: float) -> float:
    """Calculate the square root of a number"""
    if number < 0:
        raise ValueError("Cannot calculate square root of a negative number")
    return number ** 0.5

if __name__ == "__main__":
    print("🧮 Starting Math MCP Server on HTTP...")
    print("📡 Server will be available at: http://localhost:8001/mcp")
    
    # Run the HTTP server
    mcp.run(transport="http", port=8001)