"""
YQA CLI — Entry point for the YQ Dev Assistant.

Usage:
    yqa --help              Show help
    yqa --version           Show version
    yqa list                List all modules
    yqa check <module>      Diagnose a module (read-only)
    yqa run <module>        Run a module (may have side effects)
    yqa status              Show system status
    yqa config get <key>    Read a config value
    yqa config set <key> <value>  Set a config value
    yqa logs                Show recent log entries

Architecture:
    The CLI is a thin layer that:
    1. Bootstraps the framework (Config → Log → EventBus → ModuleManager)
    2. Routes user commands to the appropriate component
    3. Formats and displays results

    All business logic lives in modules/ and services/.
    The CLI is just the "front door."
"""

import sys
from pathlib import Path
from typing import Any

import click

from src.core.config_manager import ConfigManager
from src.core.event_bus import EventBus
from src.core.log_manager import LogManager
from src.core.module_manager import ModuleManager
from src.utils.constants import (
    APP_NAME,
    APP_VERSION,
    EXIT_SUCCESS,
    EXIT_ERROR,
    EXIT_CONFIG_ERROR,
    EXIT_MODULE_ERROR,
)
from src.utils.formatters import format_module_result, format_table


# ── Bootstrap ──────────────────────────────────────────────


def bootstrap(config_dir: str, log_level: str, modules_dir: str) -> dict[str, Any]:
    """
    Initialize all framework components.

    Called at the start of every CLI command via click.pass_context.
    Returns a context dict with all initialized managers.

    Order matters:
        1. ConfigManager first (everything else needs config)
        2. LogManager second (everything else needs logging)
        3. EventBus third (standalone)
        4. ModuleManager last (needs ConfigManager + EventBus)
    """
    # 1. Config
    cm = ConfigManager(config_dir=config_dir)
    try:
        cm.load()
    except Exception as e:
        click.echo(f"Failed to load configuration: {e}", err=True)
        return {}

    # Override log level from config if not explicitly set
    if log_level == "INFO":
        log_level = cm.get("app.log_level", "INFO")

    # 2. Logging
    logs_dir = cm.get("paths.logs_dir", "logs")
    lm = LogManager(log_dir=logs_dir, log_level=log_level)
    logger = lm.get_logger("cli")

    # 3. EventBus
    eb = EventBus()

    # Subscribe to module events for automatic logging
    def log_module_event(event_name: str, data: dict) -> None:
        module_name = data.get("name", "?")
        logger.debug("[%s] %s", module_name, event_name)

    eb.subscribe("module:*", log_module_event)

    # 4. ModuleManager
    mm = ModuleManager(
        modules_dir=modules_dir,
        config_manager=cm,
        event_bus=eb,
    )

    # Discover modules
    try:
        mm.discover()
    except Exception as e:
        logger.warning("Module discovery failed: %s", e)

    logger.info(
        "%s v%s initialized | config=%s | modules=%s",
        APP_NAME,
        APP_VERSION,
        cm.config_path,
        mm.module_names,
    )

    return {
        "config": cm,
        "log": lm,
        "event_bus": eb,
        "modules": mm,
        "logger": logger,
    }


# ── CLI Group ──────────────────────────────────────────────


@click.group()
@click.option(
    "--config-dir",
    "-c",
    envvar="YQA_CONFIG_DIR",
    default="~/.yqa",
    help="Configuration directory",
)
@click.option(
    "--modules-dir",
    "-m",
    envvar="YQA_MODULES_DIR",
    default="src/modules",
    help="Modules directory",
)
@click.option(
    "--verbose",
    "-v",
    count=True,
    help="Increase verbosity (-v, -vv, -vvv)",
)
@click.version_option(
    version=APP_VERSION,
    prog_name=APP_NAME,
    message="%(prog)s v%(version)s",
)
@click.pass_context
def cli(ctx: click.Context, config_dir: str, modules_dir: str, verbose: int) -> None:
    """
    YQ Dev Assistant — Personal Developer Workstation.

    A modular, extensible assistant for managing your development
    environment, projects, GitHub, and more.
    """
    ctx.ensure_object(dict)

    # Map verbose count to log level
    log_levels = ["WARNING", "INFO", "DEBUG"]
    log_level = log_levels[min(verbose, 2)]

    # Bootstrap framework
    app_ctx = bootstrap(config_dir, log_level, modules_dir)
    if not app_ctx:
        click.echo("Failed to initialize application.", err=True)
        sys.exit(EXIT_CONFIG_ERROR)

    ctx.obj.update(app_ctx)


# ── list ───────────────────────────────────────────────────


@cli.command("list")
@click.pass_context
def list_modules(ctx: click.Context) -> None:
    """
    List all available modules.

    Shows module name, version, description, and status.
    """
    mm: ModuleManager = ctx.obj["modules"]

    if not mm.module_names:
        click.echo("No modules found.")
        click.echo(f"Modules directory: {mm._modules_dir}")
        return

    # Build table rows
    rows = []
    for name in mm.module_names:
        try:
            module = mm.get_module(name)
            status = "loaded" if name in mm.loaded_modules else "registered"
            rows.append(
                [
                    f"{module.info.icon} {name}",
                    module.info.version,
                    module.info.description,
                    status,
                ]
            )
        except Exception:
            rows.append([name, "?", "?", "error"])

    click.echo(format_table(["Module", "Version", "Description", "Status"], rows))


# ── check ──────────────────────────────────────────────────


@cli.command("check")
@click.argument("module_name", required=False)
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.pass_context
def check_module(ctx: click.Context, module_name: str | None, verbose: bool) -> None:
    """
    Run diagnostics on a module (read-only, safe).

    MODULE_NAME: Which module to check. If omitted, checks all modules.
    """
    mm: ModuleManager = ctx.obj["modules"]
    logger = ctx.obj.get("logger")

    if not mm.module_names:
        click.echo("No modules available. Run 'yqa list' to see what's installed.")
        return

    names_to_check = [module_name] if module_name else mm.module_names
    all_ok = True

    for name in names_to_check:
        try:
            result = mm.run_check(name)
            click.echo(format_module_result(result, verbose=verbose))
            if not result.is_ok:
                all_ok = False
        except Exception as e:
            click.echo(f"  [ERROR] {name}: {e}")
            all_ok = False

    if not all_ok:
        sys.exit(EXIT_ERROR)


# ── run ────────────────────────────────────────────────────


@cli.command("run")
@click.argument("module_name")
@click.argument("args", nargs=-1)
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.pass_context
def run_module(
    ctx: click.Context, module_name: str, args: tuple, verbose: bool
) -> None:
    """
    Run a module (may have side effects).

    MODULE_NAME: Which module to run.
    ARGS: Module-specific arguments (key=value format).
    """
    mm: ModuleManager = ctx.obj["modules"]
    logger = ctx.obj.get("logger")

    # Parse key=value arguments
    kwargs = {}
    for arg in args:
        if "=" in arg:
            key, value = arg.split("=", 1)
            kwargs[key] = value
        else:
            click.echo(f"Ignoring unrecognized argument: {arg}", err=True)

    try:
        result = mm.run_execute(module_name, **kwargs)
        click.echo(format_module_result(result, verbose=verbose))
        if not result.is_ok:
            sys.exit(EXIT_ERROR)
    except Exception as e:
        click.echo(f"[ERROR] {module_name}: {e}", err=True)
        sys.exit(EXIT_MODULE_ERROR)


# ── status ─────────────────────────────────────────────────


@cli.command("status")
@click.pass_context
def status(ctx: click.Context) -> None:
    """
    Show overall system status.

    Displays system info, configuration, and module statuses.
    """
    cm: ConfigManager = ctx.obj["config"]
    mm: ModuleManager = ctx.obj["modules"]

    # App info
    click.echo(f"{APP_NAME} v{APP_VERSION}")
    click.echo(f"Config: {cm.config_path}")

    # Module status
    if not mm.module_names:
        click.echo("Modules: (none)")
    else:
        statuses = mm.get_status_all()
        rows = [
            [name, s["version"], "✓" if s["enabled"] else "✗", s.get("category", "-")]
            for name, s in statuses.items()
        ]
        click.echo(format_table(["Module", "Version", "Enabled", "Category"], rows))

    click.echo(f"Total modules: {len(mm.module_names)} | Loaded: {len(mm.loaded_modules)}")


# ── config ─────────────────────────────────────────────────


@cli.group("config")
def config_group() -> None:
    """
    Manage configuration.

    Examples:
        yqa config get app.name
        yqa config set app.log_level DEBUG
    """
    pass


@config_group.command("get")
@click.argument("key")
@click.pass_context
def config_get(ctx: click.Context, key: str) -> None:
    """Read a config value using dot notation."""
    cm: ConfigManager = ctx.obj["config"]
    value = cm.get(key)
    if value is None:
        click.echo(f"(not set) {key}")
    else:
        click.echo(f"{key} = {value}")


@config_group.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def config_set(ctx: click.Context, key: str, value: str) -> None:
    """
    Set a config value.

    Values are parsed: "true"/"false" → bool, "123" → int,
    otherwise string.
    """
    cm: ConfigManager = ctx.obj["config"]

    # Parse the value
    parsed: Any = value
    if value.lower() == "true":
        parsed = True
    elif value.lower() == "false":
        parsed = False
    else:
        try:
            parsed = int(value)
        except ValueError:
            try:
                parsed = float(value)
            except ValueError:
                parsed = value

    try:
        cm.set(key, parsed)
        click.echo(f"{key} = {parsed}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(EXIT_CONFIG_ERROR)


@config_group.command("reset")
@click.pass_context
def config_reset(ctx: click.Context) -> None:
    """Reset configuration to defaults."""
    cm: ConfigManager = ctx.obj["config"]
    cm.reset()
    click.echo("Configuration reset to defaults.")


# ── logs ───────────────────────────────────────────────────


@cli.command("logs")
@click.option("--lines", "-n", default=20, help="Number of lines to show")
@click.option("--follow", "-f", is_flag=True, help="Follow log output (tail -f)")
@click.pass_context
def logs(ctx: click.Context, lines: int, follow: bool) -> None:
    """
    Show recent log entries.

    By default, shows the last 20 lines of the log file.
    Use --follow to continuously monitor (Ctrl+C to stop).
    """
    from pathlib import Path

    log_file = Path("logs/yqa.log")
    if not log_file.exists():
        click.echo(f"No log file found at {log_file}")
        return

    if follow:
        click.echo(f"Following {log_file} (Ctrl+C to stop)...")
        click.echo("-" * 60)
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                # Go to end of file
                f.seek(0, 2)
                while True:
                    line = f.readline()
                    if line:
                        click.echo(line.rstrip())
        except KeyboardInterrupt:
            click.echo("\nStopped.")
    else:
        # Show last N lines
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            for line in all_lines[-lines:]:
                click.echo(line.rstrip())


# ── Entry Point ────────────────────────────────────────────


def main() -> None:
    """
    Entry point for the 'yqa' console script.

    This is the function specified in pyproject.toml:
        [project.scripts]
        yqa = "src.cli.main:cli"
    """
    # Wrap in try/except to ensure clean error messages
    # even if Click itself crashes during parsing.
    try:
        cli(standalone_mode=False)
    except click.ClickException as e:
        e.show()
        sys.exit(EXIT_ERROR)
    except KeyboardInterrupt:
        click.echo("\nInterrupted.")
        sys.exit(0)


if __name__ == "__main__":
    main()
