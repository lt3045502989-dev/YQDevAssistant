# Changelog

All notable changes to YQ Dev Assistant.

## [0.1.0] — 2026-07-01

### Added

**M1.1: Architecture Framework**

- **Core Framework**
  - `BaseModule` abstract class with `check()` / `execute()` / `configure()` / `get_status()`
  - `ModuleResult[T]` generic dataclass with factory methods `ok()` and `fail()`
  - `ModuleInfo` dataclass for module metadata
  - Exception hierarchy: `YQAError` → `ConfigError` / `ModuleError` / `ServiceError` / `ValidationError`

- **Core Systems**
  - `EventBus`: pub/sub with fnmatch wildcards and error isolation
  - `ConfigManager`: JSON config with Schema validation, dot-notation access, auto-save
  - `LogManager`: dual output (Rich console + rotating file), hierarchical loggers

- **Module Management**
  - `ModuleManager`: directory scanning, lazy loading, lifecycle management, auto-timing

- **Services Layer**
  - `NetworkService`: HTTP client with proxy support and retry logic
  - `FileSystemService`: safe filesystem ops constrained to allowed root
  - `GitHubService`: interface stubs (M1.3 implementation)
  - `PlaywrightService`: installation detection (M1.3 implementation)

- **CLI**
  - `yqa` command: list, check, run, status, config, logs
  - Click-based with --verbose, --config-dir, --modules-dir options

- **Tests**
  - 59 unit tests across core components
  - Core coverage: >89% on framework classes

- **Documentation**
  - Project analysis report
  - Module development template
  - Architecture and development guides

### Project Structure
- Initialized with Python `src/` layout
- `pyproject.toml` with PEP 621 metadata
- `.gitignore`, `.editorconfig`, `requirements.txt`
- Test infrastructure with pytest fixtures
