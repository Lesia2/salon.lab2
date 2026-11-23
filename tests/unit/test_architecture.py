"""Перевірка правила залежностей між шарами:

    Presentation → Application → Domain ← Infrastructure

Тест читає import-и кожного файлу і падає, якщо шар імпортує те, що йому заборонено.
"""
import ast
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[2] / "app"

# Для кожного шару — що йому ЗАБОРОНЕНО імпортувати
FORBIDDEN = {
    "domain": [
        "app.application",
        "app.infrastructure",
        "app.presentation",
        "sqlalchemy",
        "fastapi",
        "pydantic",
        "starlette",
        "jwt",
        "bcrypt",
    ],
    "application": ["app.infrastructure", "app.presentation", "sqlalchemy", "fastapi", "pydantic"],
    "infrastructure": ["app.application", "app.presentation", "fastapi"],
}


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


@pytest.mark.parametrize("layer", FORBIDDEN)
def test_layer_does_not_import_forbidden_modules(layer):
    violations = []
    for path in (APP_DIR / layer).rglob("*.py"):
        for module in imported_modules(path):
            if any(module == bad or module.startswith(bad + ".") for bad in FORBIDDEN[layer]):
                violations.append(f"{path.relative_to(APP_DIR)} імпортує {module}")
    assert violations == []


def test_all_four_layers_exist():
    for layer in ["domain", "application", "infrastructure", "presentation"]:
        assert (APP_DIR / layer / "__init__.py").exists()
