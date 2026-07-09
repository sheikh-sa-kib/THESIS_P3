# Literature Mapping

This document maps implementation choices to literature sources.

No literature-backed formulas or algorithm variants have been selected in Phase
1. Future entries must include:

- Bibliographic reference.
- Implemented module or class.
- Parameters derived from the source.
- Assumptions or deviations from the source.
- Reason for choosing the source over alternatives.

## Dependency Mapping

Runtime dependencies:

- PyYAML: parses YAML configuration files. YAML is required because experiment,
  scenario, and algorithm parameters must be externalized and reproducible.

Development dependencies:

- pytest: runs unit, integration, and regression tests.
- pytest-cov: records test coverage so coverage remains visible throughout the
  thesis implementation.
- mypy: enforces strict static typing.
- ruff: provides linting and formatting checks.
- types-PyYAML: supplies type stubs for strict checking of PyYAML usage.
- pre-commit: runs quality gates before commits.
