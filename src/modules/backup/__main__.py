"""
Standalone entry point for the Backup module.

Usage:
    python -m src.modules.backup              # Check status
    python -m src.modules.backup backup       # Create backup
    python -m src.modules.backup list         # List backups
"""

import sys
from src.modules.backup.module import BackupModule

if __name__ == "__main__":
    module = BackupModule()
    action = sys.argv[1] if len(sys.argv) > 1 else "check"

    if action == "check":
        result = module.check()
    else:
        result = module.execute(action=action)

    print(f"Module: {result.module_name}")
    print(f"Success: {result.success}")
    if result.data:
        for key, value in result.data.items():
            print(f"  {key}: {value}")
    if result.errors:
        print(f"Errors: {result.errors}")
    if result.warnings:
        print(f"Warnings: {result.warnings}")
