# ============================================================
#  test_tools.py — Diagnostic Tool Execution Script
# ============================================================
import asyncio
from tools import registry
# Import agents to make sure tools are registered
from agents.hand_agent import HandAgent

async def run_diagnostics():
    print("=" * 60)
    print("  RUMAIN Diagnostic — Tool Registry Verification")
    print("=" * 60)
    
    print(f"\nRegistered tools ({len(registry.schemas)}):")
    for schema in registry.schemas:
        print(f" - {schema['name']}: {schema['description']}")
        
    print("\nRunning test execution for 'get_system_status'...")
    res = await registry.execute("get_system_status", {})
    print(f"Result:\n{res}")
    
    print("\nRunning test execution for 'read_clipboard'...")
    res = await registry.execute("read_clipboard", {})
    print(f"Result:\n{res}")
    
    print("\nDiagnostics complete!")

if __name__ == "__main__":
    asyncio.run(run_diagnostics())
