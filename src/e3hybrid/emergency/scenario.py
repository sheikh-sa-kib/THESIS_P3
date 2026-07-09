"""Scenario loading from YAML files.

``ScenarioLoader`` reads a YAML file, validates the schema via
``validate_scenario_dict()``, and constructs concrete ``EmergencyEvent``
objects ready to be handed to the ``EventScheduler``.

Nothing is hardcoded.  Every event parameter comes from the YAML file.

Supported scheduling modes in YAML
-----------------------------------
(none / omit)    — fixed-time event (default)
``recurring``    — repeat on interval
``random``       — seeded random activations within a time window

Supported event types in Phase 5
---------------------------------
road_closure, road_block, traffic_accident, emergency_vehicle,
infrastructure_failure, communication_blackout, hazard_zone
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from e3hybrid.communication.enums import Priority
from e3hybrid.core.exceptions import EmergencyError
from e3hybrid.emergency.enums import EmergencyEventType
from e3hybrid.emergency.events import (
    CommunicationBlackoutEvent,
    EmergencyVehicleEvent,
    HazardZoneEvent,
    InfrastructureFailureEvent,
    RoadBlockEvent,
    RoadClosureEvent,
    TrafficAccidentEvent,
)
from e3hybrid.emergency.scheduler import EventScheduler
from e3hybrid.emergency.types import EventId, EventLocation, EventStatus
from e3hybrid.emergency.validation import validate_scenario_dict
from e3hybrid.network.types import EdgeId, NodeId

_logger = logging.getLogger(__name__)

_PRIORITY_MAP: dict[str, Priority] = {
    "low": Priority.LOW,
    "normal": Priority.NORMAL,
    "high": Priority.HIGH,
    "critical": Priority.CRITICAL,
}


@dataclass(frozen=True)
class ScenarioMetadata:
    """High-level metadata about a loaded scenario."""

    name: str
    seed: int
    description: str
    simulation_duration_s: float | None
    event_count: int


@dataclass
class LoadedScenario:
    """Result of loading and parsing a scenario YAML file."""

    metadata: ScenarioMetadata
    scheduler: EventScheduler
    raw: dict[str, Any]


class ScenarioLoader:
    """Load and parse emergency scenario YAML files.

    Usage
    -----
    ::

        loader = ScenarioLoader()
        scenario = loader.load(Path("scenarios/rush_hour.yaml"))
        # scenario.scheduler is pre-populated and ready to be ticked
    """

    def load(self, path: Path) -> LoadedScenario:
        """Load, validate, and parse a scenario from a YAML file."""

        if not path.exists():
            raise EmergencyError(f"scenario file not found: {path}")

        _logger.info("ScenarioLoader: loading %s", path)
        try:
            with path.open("r", encoding="utf-8") as fh:
                raw = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            raise EmergencyError(f"YAML parse error in {path}: {exc}") from exc

        return self.load_dict(raw)

    def load_dict(self, raw: dict[str, Any]) -> LoadedScenario:
        """Validate and parse a scenario from a pre-loaded dictionary."""

        validate_scenario_dict(raw)
        scenario_data = raw["scenario"]

        seed = int(scenario_data.get("seed", 0))
        sim_duration = scenario_data.get("simulation_duration_s")

        scheduler = EventScheduler(seed=seed)
        events_data = scenario_data.get("events", [])

        for event_data in events_data:
            self._load_event(event_data, scheduler)

        metadata = ScenarioMetadata(
            name=scenario_data["name"],
            seed=seed,
            description=scenario_data.get("description", ""),
            simulation_duration_s=float(sim_duration) if sim_duration else None,
            event_count=len(events_data),
        )
        return LoadedScenario(metadata=metadata, scheduler=scheduler, raw=raw)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_event(
        self, data: Mapping[str, Any], scheduler: EventScheduler
    ) -> None:
        scheduling = data.get("scheduling")
        event = self._build_event(data)

        if scheduling == "recurring":
            scheduler.schedule_recurring(
                template=event,
                first_activation_s=float(data.get("first_activation", event.activation_time_s)),
                interval_s=float(data["interval_s"]),
                max_occurrences=data.get("max_occurrences"),
            )
        elif scheduling == "random":
            scheduler.schedule_random(
                template=event,
                earliest_s=float(data["earliest_s"]),
                latest_s=float(data["latest_s"]),
                count=int(data.get("count", 1)),
            )
        else:
            scheduler.schedule(event)

    def _build_event(self, data: Mapping[str, Any]) -> Any:
        event_id = EventId(str(data["id"]))
        event_type = EmergencyEventType(str(data["type"]))
        activation_time_s = float(data["activation_time"])
        duration_s = float(data["duration"]) if data.get("duration") is not None else None
        severity = float(data["severity"])
        priority = _PRIORITY_MAP[str(data.get("priority", "normal")).lower()]
        broadcast_radius_m = float(data["broadcast_radius_m"])
        metadata = dict(data.get("metadata", {}))
        location = self._build_location(data["location"])

        kwargs: dict[str, Any] = dict(
            event_id=event_id,
            event_type=event_type,
            activation_time_s=activation_time_s,
            duration_s=duration_s,
            severity=severity,
            priority=priority,
            broadcast_radius_m=broadcast_radius_m,
            metadata=metadata,
            location=location,
            status=EventStatus.CREATED,
        )

        if event_type == EmergencyEventType.ROAD_CLOSURE:
            return RoadClosureEvent(
                **kwargs, blocking_cause=str(data.get("blocking_cause", ""))
            )
        elif event_type == EmergencyEventType.ROAD_BLOCK:
            return RoadBlockEvent(
                **kwargs,
                speed_reduction_factor=float(data.get("speed_reduction_factor", 0.5)),
                congestion_factor_delta=float(data.get("congestion_factor_delta", 1.0)),
            )
        elif event_type == EmergencyEventType.TRAFFIC_ACCIDENT:
            return TrafficAccidentEvent(
                **kwargs,
                vehicle_count=int(data.get("vehicle_count", 1)),
                blocks_all_lanes=bool(data.get("blocks_all_lanes", True)),
                spawns_emergency_vehicle=bool(data.get("spawns_emergency_vehicle", False)),
                secondary_congestion_delta=float(data.get("secondary_congestion_delta", 0.5)),
            )
        elif event_type == EmergencyEventType.EMERGENCY_VEHICLE:
            origin = NodeId(str(data["origin_node"])) if data.get("origin_node") else None
            dest = NodeId(str(data["destination_node"])) if data.get("destination_node") else None
            return EmergencyVehicleEvent(
                **kwargs,
                origin_node=origin,
                destination_node=dest,
                vehicle_type=str(data.get("vehicle_type", "ambulance")),
                emergency_penalty_s=float(data.get("emergency_penalty_s", 120.0)),
            )
        elif event_type == EmergencyEventType.INFRASTRUCTURE_FAILURE:
            return InfrastructureFailureEvent(
                **kwargs,
                failed_sensor_ids=frozenset(data.get("failed_sensor_ids", [])),
                fallback_to_static=bool(data.get("fallback_to_static", True)),
            )
        elif event_type == EmergencyEventType.COMMUNICATION_BLACKOUT:
            return CommunicationBlackoutEvent(
                **kwargs,
                communication_penalty_s=float(data.get("communication_penalty_s", 60.0)),
                blackout_cause=str(data.get("blackout_cause", "unspecified")),
            )
        elif event_type == EmergencyEventType.HAZARD_ZONE:
            return HazardZoneEvent(
                **kwargs,
                hazard_type=str(data.get("hazard_type", "unspecified")),
                hazard_penalty_s=float(data.get("hazard_penalty_s", 30.0)),
            )
        else:
            raise EmergencyError(f"unsupported event type for construction: {event_type}")

    @staticmethod
    def _build_location(loc_data: Mapping[str, Any]) -> EventLocation:
        edge_ids = frozenset(EdgeId(str(e)) for e in loc_data.get("edge_ids", []))
        center_node = NodeId(str(loc_data["center_node"])) if loc_data.get("center_node") else None
        radius_m = float(loc_data["radius_m"]) if loc_data.get("radius_m") is not None else None
        return EventLocation(
            edge_ids=edge_ids,
            center_node=center_node,
            radius_m=radius_m,
            metadata=dict(loc_data.get("metadata", {})),
        )
