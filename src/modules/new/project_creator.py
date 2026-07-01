"""
Project Creator — create new projects from templates.

Design:
    - Templates are Python dicts (for now) — files -> content
    - Each template defines: name, description, files, init_git
    - Created projects get: README.md, .gitignore, language-specific files
    - Git repo is initialized automatically
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path


# ── Template Data Model ────────────────────────────────────


@dataclass
class ProjectTemplate:
    """A project template definition."""

    name: str
    description: str
    language: str
    files: dict[str, str]  # relative_path -> content
    init_git: bool = True
    subdir: str = ""  # e.g., "src" for Python projects


# ── Templates ──────────────────────────────────────────────


TEMPLATES = {
    "python-basic": ProjectTemplate(
        name="python-basic",
        description="Python 基础项目 — src/ 布局 + pyproject.toml",
        language="Python",
        subdir="src",
        files={
            "README.md": "# {project_name}\n\nPython project.\n",
            ".gitignore": "__pycache__/\n*.pyc\n.venv/\n.env\n",
            "src/__init__.py": '"""Package."""\n',
            "src/main.py": '"""Entry point."""\n\n\ndef main():\n    print("Hello, {project_name}!")\n\n\nif __name__ == "__main__":\n    main()\n',
            "pyproject.toml": (
                '[build-system]\nrequires = ["setuptools>=68.0", "wheel"]\n'
                'build-backend = "setuptools.build_meta"\n\n'
                "[project]\n"
                'name = "{project_name}"\n'
                'version = "0.1.0"\n'
                'description = "A Python project"\n'
                'requires-python = ">=3.11"\n'
            ),
            "tests/__init__.py": '"""Tests."""\n',
            "tests/test_main.py": (
                "from src.main import main\n\n\n"
                "def test_main():\n"
                "    # Basic smoke test\n"
                "    assert callable(main)\n"
            ),
        },
    ),
    "python-cli": ProjectTemplate(
        name="python-cli",
        description="Python CLI 项目 — Click 命令行工具",
        language="Python",
        subdir="src",
        files={
            "README.md": "# {project_name}\n\nCLI tool built with Click.\n",
            ".gitignore": "__pycache__/\n*.pyc\n.venv/\n.env\ndist/\n*.egg-info/\n",
            "src/__init__.py": '"""Package."""\n',
            "src/cli.py": (
                '"""CLI entry point."""\n\n'
                "import click\n\n\n"
                '@click.group()\n'
                "def cli():\n"
                '    """{project_name} CLI."""\n'
                "    pass\n\n\n"
                '@cli.command()\n'
                "def hello():\n"
                '    """Say hello."""\n'
                '    click.echo("Hello from {project_name}!")\n\n\n'
                'if __name__ == "__main__":\n'
                "    cli()\n"
            ),
            "pyproject.toml": (
                '[build-system]\nrequires = ["setuptools>=68.0", "wheel"]\n'
                'build-backend = "setuptools.build_meta"\n\n'
                "[project]\n"
                'name = "{project_name}"\n'
                'version = "0.1.0"\n'
                'description = "A Python CLI tool"\n'
                'requires-python = ">=3.11"\n'
                'dependencies = ["click>=8.0"]\n\n'
                "[project.scripts]\n"
                '{project_name} = "src.cli:cli"\n'
            ),
            "tests/__init__.py": '"""Tests."""\n',
            "tests/test_cli.py": (
                "from click.testing import CliRunner\n"
                "from src.cli import cli\n\n\n"
                "def test_hello():\n"
                "    runner = CliRunner()\n"
                "    result = runner.invoke(cli, ['hello'])\n"
                "    assert result.exit_code == 0\n"
            ),
        },
    ),
    "node-basic": ProjectTemplate(
        name="node-basic",
        description="Node.js 基础项目 — package.json + index.js",
        language="JavaScript",
        files={
            "README.md": "# {project_name}\n\nNode.js project.\n",
            ".gitignore": "node_modules/\n.env\ndist/\n",
            "index.js": (
                "// {project_name}\n\n"
                'console.log("Hello, {project_name}!");\n'
            ),
            "package.json": (
                "{\n"
                '  "name": "{project_name}",\n'
                '  "version": "0.1.0",\n'
                '  "description": "A Node.js project",\n'
                '  "main": "index.js",\n'
                '  "scripts": {\n'
                '    "start": "node index.js",\n'
                '    "test": "echo \\"No tests yet\\""\n'
                "  },\n"
                '  "keywords": [],\n'
                '  "author": "",\n'
                '  "license": "MIT"\n'
                "}\n"
            ),
        },
    ),
    "go-basic": ProjectTemplate(
        name="go-basic",
        description="Go 基础项目 — go.mod + main.go",
        language="Go",
        files={
            "README.md": "# {project_name}\n\nGo project.\n",
            ".gitignore": "*.exe\n*.test\n*.out\nvendor/\n",
            "main.go": (
                "package main\n\n"
                'import "fmt"\n\n'
                "func main() {\n"
                '    fmt.Println("Hello, {project_name}!")\n'
                "}\n"
            ),
            "go.mod": "module {project_name}\n\ngo 1.21\n",
        },
    ),
}


# ── Project Creator ────────────────────────────────────────


@dataclass
class CreateResult:
    """Result of creating a project."""

    project_name: str
    template: str
    path: Path
    files_created: int
    git_initialized: bool


def list_templates() -> list[dict]:
    """List all available templates."""
    return [
        {
            "name": t.name,
            "description": t.description,
            "language": t.language,
        }
        for t in TEMPLATES.values()
    ]


def create_project(
    project_name: str,
    template_name: str,
    parent_dir: str | Path = ".",
    init_git: bool = True,
    author: str = "",
) -> CreateResult:
    """
    Create a new project from a template.

    Args:
        project_name: Name of the new project (used as directory name).
        template_name: Template to use (must exist in TEMPLATES).
        parent_dir: Where to create the project directory.
        init_git: Whether to initialize a Git repository.
        author: Optional author name for files.

    Returns:
        CreateResult describing the created project.

    Raises:
        ValueError: If template not found or project already exists.
    """
    template = TEMPLATES.get(template_name)
    if template is None:
        available = ", ".join(TEMPLATES.keys())
        raise ValueError(
            f"Unknown template: {template_name}. Available: {available}"
        )

    project_dir = Path(parent_dir) / project_name
    if project_dir.exists():
        raise ValueError(
            f"Project directory already exists: {project_dir}"
        )

    # Create project directory
    project_dir.mkdir(parents=True)

    files_created = 0

    # Create all template files
    for rel_path, content in template.files.items():
        file_path = project_dir / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Replace placeholders
        rendered = content.replace("{project_name}", project_name)
        if author:
            rendered = rendered.replace('"author": ""', f'"author": "{author}"')
            rendered = rendered.replace("author = \"\"", f"author = \"{author}\"")

        file_path.write_text(rendered, encoding="utf-8")
        files_created += 1

    # Initialize Git repository if requested
    git_initialized = False
    if init_git:
        try:
            subprocess.run(
                ["git", "init"],
                cwd=str(project_dir),
                capture_output=True,
                timeout=10,
            )
            # Create initial commit
            subprocess.run(
                ["git", "add", "-A"],
                cwd=str(project_dir),
                capture_output=True,
                timeout=10,
            )
            subprocess.run(
                ["git", "commit", "-m", f"Initial commit from {template_name} template"],
                cwd=str(project_dir),
                capture_output=True,
                timeout=10,
            )
            git_initialized = True
        except Exception:
            # Git init failed — continue without it
            pass

    return CreateResult(
        project_name=project_name,
        template=template_name,
        path=project_dir.resolve(),
        files_created=files_created,
        git_initialized=git_initialized,
    )
