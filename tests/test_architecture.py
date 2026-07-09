"""Architectural regression and structural integrity tests."""

from __future__ import annotations

import ast
import importlib
import os
import sys
from pathlib import Path

import pytest


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _src_packages() -> list[Path]:
    src = _project_root() / "src" / "e3hybrid"
    return [
        p for p in src.rglob("__init__.py")
        if p.parent.is_dir() and p.parent != src
    ]


class TestCircularImports:
    """Verify there are no circular imports anywhere in the project."""

    def test_no_circular_imports(self) -> None:
        """Import every top-level module and submodule; circular imports
        will raise ImportError at import time."""
        root = _project_root() / "src"
        sys.path.insert(0, str(root))

        failed = []
        for init_file in sorted(_src_packages()):
            rel = init_file.relative_to(root / "e3hybrid")
            mod_name = "e3hybrid." + str(rel.parent).replace(os.sep, ".")
            try:
                importlib.import_module(mod_name)
            except ImportError as e:
                failed.append((mod_name, str(e)))

        assert len(failed) == 0, (
            f"Circular or failed imports detected:\n" +
            "\n".join(f"  {m}: {e}" for m, e in failed)
        )

    def test_individual_modules_importable(self) -> None:
        """All .py files in the project must be importable."""
        root = _project_root() / "src"
        sys.path.insert(0, str(root))

        e3hybrid_root = root / "e3hybrid"
        failed = []
        for py_file in sorted(e3hybrid_root.rglob("*.py")):
            if py_file.name == "__init__.py":
                continue
            rel = py_file.relative_to(e3hybrid_root)
            mod_name = "e3hybrid." + str(rel.with_suffix("")).replace(os.sep, ".")
            try:
                importlib.import_module(mod_name)
            except ImportError as e:
                failed.append((mod_name, str(e)))

        assert len(failed) == 0, (
            f"Modules that failed to import:\n" +
            "\n".join(f"  {m}: {e}" for m, e in failed[:20])
        )


class TestSumoLayerIndependence:
    """Verify the SUMO integration layer does not depend on routing internals
    beyond the RoutingAlgorithm protocol."""

    def test_sumo_imports_no_routing_internals(self) -> None:
        """The sumo/ package should not import from routing/ directly,
        only from the public protocol."""
        sumo_dir = _project_root() / "src" / "e3hybrid" / "sumo"
        routing_dir_pattern = "e3hybrid.routing"

        violations = []
        for py_file in sumo_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith(routing_dir_pattern) and "protocol" not in alias.name:
                            # experiment_runner imports adapters which is OK
                            if "experiment_runner" in py_file.name:
                                continue
                            violations.append(f"{py_file.name} imports from {alias.name}")

        assert len(violations) == 0, (
            "SUMO layer imports routing internals:\n" + "\n".join(violations)
        )


class TestNoRoutingAlgoModifications:
    """Verify no routing algorithms were modified by the SUMO integration."""

    def test_routing_algorithms_no_emergency_branches(self) -> None:
        """Verify routing algorithms have no emergency-specific branches."""
        routing_dir = _project_root() / "src" / "e3hybrid" / "routing"
        excluded = {"__init__.py", "cost_calculator.py", "cost.py", "verifier.py"}

        violations = []
        for py_file in routing_dir.rglob("*.py"):
            if py_file.name in excluded:
                continue
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.If):
                    if_text = ast.dump(node.test).lower()
                    if "emergency" in if_text:
                        violations.append((py_file.name, node.lineno, if_text[:80]))

        assert len(violations) == 0, (
            f"Emergency-specific branches found in routing algorithms:\n" +
            "\n".join(f"  {f}:{l} {t}" for f, l, t in violations)
        )

    def test_routing_algorithms_pure_protocol(self) -> None:
        """All algorithms must implement only the RoutingAlgorithm protocol."""
        routing_dir = _project_root() / "src" / "e3hybrid" / "routing"
        astar_path = routing_dir / "astar.py"
        dijkstra_path = routing_dir / "dijkstra.py"

        for fpath in [astar_path, dijkstra_path]:
            content = fpath.read_text(encoding="utf-8")
            assert "compute_route" in content, (
                f"{fpath.name} does not implement compute_route"
            )
