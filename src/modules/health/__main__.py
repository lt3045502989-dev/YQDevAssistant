"""
Standalone entry point for the Health module.

Usage:
    python -m src.modules.health
"""

from src.modules.health.module import HealthModule
from src.modules.health.reporter import format_report_cli

if __name__ == "__main__":
    module = HealthModule()
    result = module.check()

    if result.is_ok and result.data:
        print(format_report_cli(result.data))
    else:
        print(f"Health check failed:")
        for error in result.errors:
            print(f"  [ERROR] {error}")
        for warning in result.warnings:
            print(f"  [WARN] {warning}")
