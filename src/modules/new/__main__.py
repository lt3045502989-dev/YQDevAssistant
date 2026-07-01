"""
Standalone entry point for the New module.

Usage:
    python -m src.modules.new                          # List templates
    python -m src.modules.new create my-project python-basic  # Create project
"""

import sys
from src.modules.new.module import NewModule

if __name__ == "__main__":
    module = NewModule()

    if len(sys.argv) >= 4 and sys.argv[1] == "create":
        name = sys.argv[2]
        template = sys.argv[3]
        result = module.execute(action="create", name=name, template=template)
    else:
        result = module.check()

    print(f"Success: {result.success}")
    if result.data:
        for key, value in result.data.items():
            print(f"  {key}: {value}")
    if result.errors:
        print(f"Errors: {result.errors}")
