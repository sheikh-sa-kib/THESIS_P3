"""Shared strongly typed identifiers.

The aliases in this module make public interfaces explicit without coupling
Phase 1 infrastructure to future simulation, routing, or SUMO implementations.
"""

from typing import NewType

AlgorithmName = NewType("AlgorithmName", str)
ExperimentName = NewType("ExperimentName", str)
Seed = NewType("Seed", int)
