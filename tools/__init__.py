# ============================================================
#  tools/__init__.py — Tool Registration Framework
# ============================================================
import inspect
from typing import Any, Callable, Dict, List

class ToolRegistry:
    """
    Registry for tools that the LLM brain can call.
    Maintains schemas and maps tool execution calls.
    """
    def __init__(self) -> None:
        self.tools: Dict[str, Callable] = {}
        self.schemas: List[Dict[str, Any]] = []

    def register(self, name: str, description: str, parameters: Dict[str, Any]) -> Callable:
        """Decorator to register a tool with a specific schema."""
        def decorator(func: Callable) -> Callable:
            self.tools[name] = func
            self.schemas.append({
                "name": name,
                "description": description,
                "input_schema": parameters
            })
            return func
        return decorator

    async def execute(self, name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool by name with arguments (supports both async and sync tools)."""
        if name not in self.tools:
            return f"Error: Tool '{name}' is not registered."
        
        func = self.tools[name]
        try:
            if inspect.iscoroutinefunction(func):
                result = await func(**arguments)
            else:
                result = func(**arguments)
            return str(result)
        except Exception as e:
            return f"Error executing tool '{name}': {e}"

# Global registry instance
registry = ToolRegistry()

def tool(name: str, description: str, parameters: Dict[str, Any]):
    """Decorator shortcut to register a tool."""
    return registry.register(name, description, parameters)
