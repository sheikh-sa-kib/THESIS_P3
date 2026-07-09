"""SUMO/TraCI integration package.

This package is strictly an integration layer between the E3-Hybrid routing
framework and SUMO (Simulation of Urban Mobility). It contains:

- SumoConfig              — SUMO simulation configuration
- SumoTraciConnection     — Low-level TraCI wrapper (sole TraCI user)
- SumoNetworkImporter     — SUMO .net.xml → DirectedGraph converter
- SumoSimulation          — Step loop with graph state sync
- SumoReroutingManager    — Reroute scheduling and application
- SumoRoutingAdapter      — RoutingAlgorithm wrapper for SUMO
- SumoExperimentRunner    — Full experiment lifecycle orchestration

No routing logic lives here. All routing decisions are delegated to
the existing RoutingAlgorithm protocol.
"""

from __future__ import annotations

from e3hybrid.sumo.adapters import SumoRoutingAdapter
from e3hybrid.sumo.config import SumoConfig
from e3hybrid.sumo.connection import SumoTraciConnection
from e3hybrid.sumo.emergency_manager import SumoEmergencyManager
from e3hybrid.sumo.experiment_runner import SumoExperimentResult, SumoExperimentRunner
from e3hybrid.sumo.network_importer import SumoNetworkImporter
from e3hybrid.sumo.rerouting_manager import SumoReroutingManager
from e3hybrid.sumo.simulation import SumoSimulation

__all__ = [
    "SumoConfig",
    "SumoTraciConnection",
    "SumoNetworkImporter",
    "SumoSimulation",
    "SumoReroutingManager",
    "SumoRoutingAdapter",
    "SumoEmergencyManager",
    "SumoExperimentRunner",
    "SumoExperimentResult",
]