"""
YQ Dev Assistant — Shared Constants.

This is the single source of truth for magic values used across the project.
If a value appears in more than one file, it belongs here.
"""

# ── App Identity ──────────────────────────────────────────
APP_NAME = "YQDevAssistant"
APP_VERSION = "0.1.0"
APP_AUTHOR = "lt3045502989-dev"
APP_DESCRIPTION = "Personal Developer Workstation Assistant"

# ── Paths ─────────────────────────────────────────────────
DEFAULT_CONFIG_DIR = "~/.yqa"
ALLOWED_FS_ROOT = "C:/Users/L1372"
DEFAULT_LOGS_DIR = "logs"
DEFAULT_BACKUPS_DIR = "backups"

# ── Network ───────────────────────────────────────────────
DEFAULT_PROXY_HTTP = "http://127.0.0.1:7897"
DEFAULT_PROXY_HTTPS = "http://127.0.0.1:7897"
DEFAULT_REQUEST_TIMEOUT = 5  # seconds
DEFAULT_CONNECT_TIMEOUT = 5  # seconds

# ── Exit Codes ────────────────────────────────────────────
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_MODULE_ERROR = 3
EXIT_SERVICE_ERROR = 4
EXIT_VALIDATION_ERROR = 5

# ── Logging ───────────────────────────────────────────────
DEFAULT_LOG_LEVEL = "INFO"
MAX_LOG_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5

# ── Modules ───────────────────────────────────────────────
MODULES_DIR = "src/modules"
MODULE_FILE = "module.py"  # Each module's entry point file
MODULE_CLASS_SUFFIX = "Module"  # e.g., HealthModule, BackupModule

# ── Event Names ───────────────────────────────────────────
# Standardized event names for inter-module communication.
# Format: <domain>:<action>
EVENT_MODULE_STARTED = "module:started"
EVENT_MODULE_COMPLETED = "module:completed"
EVENT_MODULE_FAILED = "module:failed"
EVENT_CONFIG_CHANGED = "config:changed"
EVENT_CONFIG_RELOADED = "config:reloaded"
