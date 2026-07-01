"""
Tests for the New (project creator) module.
"""

import pytest
from src.modules.new.module import NewModule
from src.modules.new.project_creator import (
    list_templates,
    create_project,
    TEMPLATES,
    CreateResult,
)


class TestProjectCreator:
    """Tests for project_creator functions."""

    def test_list_templates(self):
        templates = list_templates()
        assert len(templates) >= 4
        names = [t["name"] for t in templates]
        assert "python-basic" in names
        assert "python-cli" in names
        assert "node-basic" in names
        assert "go-basic" in names

    def test_create_python_basic(self, tmp_path):
        result = create_project(
            project_name="test-project",
            template_name="python-basic",
            parent_dir=str(tmp_path),
            init_git=False,
        )
        assert result.project_name == "test-project"
        assert result.files_created >= 3
        assert (tmp_path / "test-project").exists()
        assert (tmp_path / "test-project" / "README.md").exists()
        assert (tmp_path / "test-project" / "pyproject.toml").exists()
        assert (tmp_path / "test-project" / "src" / "main.py").exists()

    def test_create_python_cli(self, tmp_path):
        result = create_project(
            project_name="my-cli",
            template_name="python-cli",
            parent_dir=str(tmp_path),
            init_git=False,
        )
        assert result.project_name == "my-cli"
        assert (tmp_path / "my-cli" / "src" / "cli.py").exists()

    def test_create_node_basic(self, tmp_path):
        result = create_project(
            project_name="my-node-app",
            template_name="node-basic",
            parent_dir=str(tmp_path),
            init_git=False,
        )
        assert result.project_name == "my-node-app"
        assert (tmp_path / "my-node-app" / "package.json").exists()
        assert (tmp_path / "my-node-app" / "index.js").exists()

    def test_create_go_basic(self, tmp_path):
        result = create_project(
            project_name="my-go-app",
            template_name="go-basic",
            parent_dir=str(tmp_path),
            init_git=False,
        )
        assert result.project_name == "my-go-app"
        assert (tmp_path / "my-go-app" / "go.mod").exists()
        assert (tmp_path / "my-go-app" / "main.go").exists()

    def test_create_with_git(self, tmp_path):
        """Creating with init_git=True should create a Git repo."""
        result = create_project(
            project_name="git-project",
            template_name="python-basic",
            parent_dir=str(tmp_path),
            init_git=True,
        )
        assert result.git_initialized
        assert (tmp_path / "git-project" / ".git").exists()

    def test_create_unknown_template_raises(self, tmp_path):
        with pytest.raises(ValueError) as exc_info:
            create_project(
                project_name="test",
                template_name="nonexistent",
                parent_dir=str(tmp_path),
            )
        assert "Unknown template" in str(exc_info.value)

    def test_create_existing_dir_raises(self, tmp_path):
        (tmp_path / "existing").mkdir()
        with pytest.raises(ValueError) as exc_info:
            create_project(
                project_name="existing",
                template_name="python-basic",
                parent_dir=str(tmp_path),
            )
        assert "already exists" in str(exc_info.value)

    def test_placeholder_replacement(self, tmp_path):
        """Template placeholder {project_name} should be replaced."""
        create_project(
            project_name="my-awesome-app",
            template_name="python-basic",
            parent_dir=str(tmp_path),
            init_git=False,
        )
        readme = (tmp_path / "my-awesome-app" / "README.md").read_text()
        assert "my-awesome-app" in readme

        main_py = (tmp_path / "my-awesome-app" / "src" / "main.py").read_text()
        assert "my-awesome-app" in main_py

    def test_templates_have_required_files(self):
        """Every template should have README and .gitignore."""
        for name, template in TEMPLATES.items():
            assert "README.md" in template.files, f"{name} missing README.md"
            assert ".gitignore" in template.files, f"{name} missing .gitignore"


class TestNewModule:
    """Tests for NewModule."""

    def test_info(self):
        mod = NewModule()
        assert mod.info.name == "new"
        assert mod.info.category == "tools"

    def test_check_returns_templates(self):
        mod = NewModule()
        result = mod.check()
        assert result.is_ok
        assert result.data["count"] >= 4

    def test_execute_list(self):
        mod = NewModule()
        result = mod.execute(action="list")
        assert result.is_ok
        assert result.data["count"] >= 4

    def test_execute_create(self, tmp_path):
        mod = NewModule()
        result = mod.execute(
            action="create",
            project="test-from-module",
            template="python-basic",
            dir=str(tmp_path),
        )
        assert result.is_ok
        assert result.data["project_name"] == "test-from-module"

    def test_execute_create_missing_project(self):
        mod = NewModule()
        result = mod.execute(action="create", template="python-basic")
        assert not result.is_ok
        assert "project" in result.errors[0]

    def test_execute_create_missing_template(self):
        mod = NewModule()
        result = mod.execute(action="create", name="test")
        assert not result.is_ok
        assert "template" in result.errors[0]

    def test_get_status(self):
        mod = NewModule()
        status = mod.get_status()
        assert status["templates"] >= 4
