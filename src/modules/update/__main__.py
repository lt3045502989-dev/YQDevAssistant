"""
Standalone entry point for the Update module.

Usage:
    python -m src.modules.update
"""

from src.modules.update.module import UpdateModule

if __name__ == "__main__":
    module = UpdateModule()
    result = module.check()

    if result.data:
        print("=" * 60)
        print("  Development Tool Update Check")
        print("=" * 60)
        for item in result.data["items"]:
            icon = "UPDATE" if item["update_available"] else "OK"
            method = f"[{item['method']}]"
            print(f"  [{icon}] {item['name']}: {item['current']}", end="")
            if item["latest"] and item["latest"] != "?":
                print(f" → latest: {item['latest']}", end="")
            if item["update_command"]:
                print(f"\n    Update: {item['update_command']}", end="")
            print()
        print("=" * 60)
        print(f"  {result.data['updates_available']} update(s) available")
        print("=" * 60)
