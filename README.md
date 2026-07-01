# YQ Dev Assistant

> 个人开发工作台 | Personal Developer Workstation

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-59%20passed-brightgreen.svg)](tests/)
[![Status](https://img.shields.io/badge/Status-Alpha-orange.svg)](CHANGELOG.md)

一款模块化、可扩展的 Windows 桌面开发助手。帮助你管理开发环境、项目、GitHub、文档学习和浏览器自动化。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 开发模式安装
pip install -e .

# 运行 CLI
yqa --help
yqa status
```

## 项目结构

```
src/
├── core/         # 核心框架（BaseModule, EventBus, ConfigManager, ...）
├── modules/      # 功能模块（Health, Backup, Update, New, ...）
├── services/     # 外部服务封装（GitHub, Playwright, FileSystem, Network）
├── ui/           # GUI 层（PySide6 — Phase 3）
├── cli/          # 命令行入口
└── utils/        # 无状态工具函数
```

## 开发路线

| 阶段 | 内容 | 状态 |
|------|------|------|
| M1.1 | 架构框架 | ✅ 完成 |
| M1.2 | 核心模块 (Health, Backup, Update, New) | 🚧 开发中 |
| M1.3 | 扩展模块 (GitHub, Clean, Study, Browser) | 📋 计划中 |
| M1.4 | 质量保障 | 📋 计划中 |
| Phase 2 | 统一接口抽象 | 📋 计划中 |
| Phase 3 | GUI 开发 (PySide6) | 📋 计划中 |
| Phase 4 | UX 优化 | 📋 计划中 |
| Phase 5 | 打包 .exe | 📋 计划中 |

## 技术栈

- **语言**: Python 3.11+
- **GUI**: PySide6 (Phase 3)
- **CLI**: Click + Rich
- **配置**: JSON Schema
- **测试**: pytest
- **打包**: PyInstaller (Phase 5)

## 文档

- [项目分析报告](docs/00-项目分析报告.md)
- [架构设计](docs/01-架构设计.md)
- [开发指南](docs/02-开发指南.md)
- [模块开发模板](docs/03-模块开发模板.md)

## License

MIT
