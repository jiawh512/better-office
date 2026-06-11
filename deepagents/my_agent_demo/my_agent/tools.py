"""Custom tools for the demo agent."""
from langchain.tools import tool


@tool
def calculator(expression: str) -> str:
    """Evaluate a simple math expression. Examples: '2+2', '10*5', '100/4'."""
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {e}"


@tool
def get_weather(city: str) -> str:
    """Get current weather for a city."""
    return f"Weather in {city}: sunny, 25C"


@tool
def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    with open(path, "w") as f:
        f.write(content)
    return f"File written to {path}"


@tool
def read_file(path: str) -> str:
    """Read content from a file."""
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return f"File not found: {path}"
