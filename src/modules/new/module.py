"""
New Module — project creator from templates.

Templates:
    - python-basic: Python src/ layout + pyproject.toml
    - python-cli: Python CLI with Click
    - node-basic: Node.js + package.json
    - go-basic: Go + go.mod

Usage:
    yqa check new                          # List available templates
    yqa run new action=create name=my-project template=python-basic
    yqa run new action=list                # List templates
"""

from src.core.module_base import BaseModule, ModuleResult, ModuleInfo
from src.modules.new.project_creator import (
    list_templates,
    create_project,
    TEMPLATES,
)


class NewModule(BaseModule):
    """
    Project creator from templates.

    check() — list available templates
    execute() — create new projects
    """

    info = ModuleInfo(
        name="new",
        version="0.1.0",
        description="项目创建器 — 从模板快速创建 Python/Node/Go 项目",
        category="tools",
        icon="🆕",
    )

    def check(self) -> ModuleResult:
        """
        List available project templates.

        Returns:
            ModuleResult with template information.
        """
        try:
            templates = list_templates()
            return ModuleResult.ok(
                self.info.name,
                {
                    "templates": templates,
                    "count": len(templates),
                },
            )
        except Exception as e:
            return ModuleResult.fail(self.info.name, [str(e)])

    def execute(self, **kwargs) -> ModuleResult:
        """
        Create a new project or list templates.

        Actions:
            create  — create a new project
            list    — list available templates

        Required for create:
            project: Project name (e.g., "my-awesome-app")
            template: Template name (e.g., "python-basic")

        Optional for create:
            dir: Parent directory (default: current directory)
            author: Author name

        Examples:
            yqa run new action=create project=my-app template=python-basic
            yqa run new action=list
        """
        action = kwargs.get("action", "list")

        try:
            if action == "list":
                templates = list_templates()
                return ModuleResult.ok(
                    self.info.name,
                    {"templates": templates, "count": len(templates)},
                )

            elif action == "create":
                project_name = kwargs.get("project")
                template_name = kwargs.get("template")

                if not project_name:
                    return ModuleResult.fail(
                        self.info.name,
                        ["'project' is required. Example: yqa run new action=create project=my-app template=python-basic"],
                    )
                if not template_name:
                    return ModuleResult.fail(
                        self.info.name,
                        ["'template' is required. Use 'yqa check new' to see available templates."],
                    )

                parent_dir = kwargs.get("dir", ".")
                author = kwargs.get("author", "")
                init_git = kwargs.get("git", "true").lower() == "true"

                result = create_project(
                    project_name=project_name,
                    template_name=template_name,
                    parent_dir=parent_dir,
                    init_git=init_git,
                    author=author,
                )

                return ModuleResult.ok(
                    self.info.name,
                    {
                        "action": "create",
                        "project_name": result.project_name,
                        "template": result.template,
                        "path": str(result.path),
                        "files_created": result.files_created,
                        "git_initialized": result.git_initialized,
                    },
                )

            else:
                return ModuleResult.fail(
                    self.info.name,
                    [f"Unknown action: {action}. Valid: create, list"],
                )

        except ValueError as e:
            return ModuleResult.fail(self.info.name, [str(e)])
        except Exception as e:
            return ModuleResult.fail(self.info.name, [str(e)])

    def get_status(self) -> dict:
        status = super().get_status()
        status["templates"] = len(TEMPLATES)
        return status
