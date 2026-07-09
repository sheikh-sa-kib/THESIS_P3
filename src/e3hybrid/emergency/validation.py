"""Scenario YAML validation — all hard errors before any event is constructed."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from e3hybrid.core.exceptions import EmergencyError
from e3hybrid.emergency.enums import EmergencyEventType

_VALID_PRIORITIES = {"low", "normal", "high", "critical"}
_PHASE5_TYPES = {str(t) for t in EmergencyEventType}


def validate_scenario_dict(data: Mapping[str, Any]) -> None:
    """Validate a raw scenario dictionary loaded from YAML.

    Raises
    ------
    EmergencyError:
        On the first validation failure, with a descriptive message.
        All field-level errors are collected into one compound message.
    """
    errors: list[str] = []

    if "scenario" not in data:
        raise EmergencyError("scenario YAML must contain a top-level 'scenario' key")

    scenario = data["scenario"]
    if not isinstance(scenario, Mapping):
        raise EmergencyError("'scenario' must be a mapping")

    # Top-level required fields
    if not scenario.get("name", "").strip():
        errors.append("scenario.name must be a non-empty string")

    sim_duration = scenario.get("simulation_duration_s")
    if sim_duration is not None:
        if not isinstance(sim_duration, int | float) or sim_duration <= 0:
            errors.append("scenario.simulation_duration_s must be positive when provided")

    events = scenario.get("events", [])
    if not isinstance(events, list):
        errors.append("scenario.events must be a list")
        _raise_if_errors(errors)

    # Per-event validation
    seen_ids: set[str] = set()
    for i, event in enumerate(events):
        if not isinstance(event, Mapping):
            errors.append(f"events[{i}] must be a mapping")
            continue
        prefix = f"events[{i}]"
        _validate_event_dict(event, prefix, seen_ids, sim_duration, errors)

    _raise_if_errors(errors)


def _validate_event_dict(
    event: Mapping[str, Any],
    prefix: str,
    seen_ids: set[str],
    sim_duration: float | None,
    errors: list[str],
) -> None:
    # id
    event_id = event.get("id", "")
    if not str(event_id).strip():
        errors.append(f"{prefix}.id must be a non-empty string")
    elif str(event_id) in seen_ids:
        errors.append(f"{prefix}: duplicate event id '{event_id}'")
    else:
        seen_ids.add(str(event_id))

    # type
    event_type = event.get("type", "")
    if str(event_type) not in _PHASE5_TYPES:
        errors.append(
            f"{prefix}.type '{event_type}' is not a valid EmergencyEventType"
        )

    # activation_time
    act_time = event.get("activation_time")
    if act_time is None:
        errors.append(f"{prefix}.activation_time is required")
    elif isinstance(act_time, bool) or not isinstance(act_time, int | float):
        errors.append(f"{prefix}.activation_time must be a number")
    elif act_time < 0:
        errors.append(f"{prefix}.activation_time must be non-negative")
    elif sim_duration is not None and act_time > sim_duration:
        errors.append(
            f"{prefix}.activation_time ({act_time}) exceeds"
            f" simulation_duration_s ({sim_duration})"
        )

    # duration (optional)
    duration = event.get("duration")
    if duration is not None:
        if isinstance(duration, bool) or not isinstance(duration, int | float):
            errors.append(f"{prefix}.duration must be a number when provided")
        elif duration <= 0:
            errors.append(f"{prefix}.duration must be positive when provided")

    # severity
    severity = event.get("severity")
    if severity is None:
        errors.append(f"{prefix}.severity is required")
    elif isinstance(severity, bool) or not isinstance(severity, int | float):
        errors.append(f"{prefix}.severity must be a number")
    elif not (0.0 <= float(severity) <= 1.0):
        errors.append(f"{prefix}.severity must be in [0.0, 1.0]")

    # priority
    priority = str(event.get("priority", "")).lower()
    if priority not in _VALID_PRIORITIES:
        errors.append(
            f"{prefix}.priority must be one of: "
            f"{', '.join(sorted(_VALID_PRIORITIES))}"
        )

    # location
    location = event.get("location")
    if location is None:
        errors.append(f"{prefix}.location is required")
    elif not isinstance(location, Mapping):
        errors.append(f"{prefix}.location must be a mapping")
    else:
        edge_ids = location.get("edge_ids", [])
        center_node = location.get("center_node")
        if not edge_ids and center_node is None:
            errors.append(
                f"{prefix}.location must specify edge_ids or center_node"
            )
        radius = location.get("radius_m")
        if radius is not None:
            if isinstance(radius, bool) or not isinstance(radius, int | float):
                errors.append(f"{prefix}.location.radius_m must be a number")
            elif radius <= 0:
                errors.append(f"{prefix}.location.radius_m must be positive")

    # broadcast_radius_m
    br = event.get("broadcast_radius_m")
    if br is None:
        errors.append(f"{prefix}.broadcast_radius_m is required")
    elif isinstance(br, bool) or not isinstance(br, int | float) or br <= 0:
        errors.append(f"{prefix}.broadcast_radius_m must be positive")


def _raise_if_errors(errors: list[str]) -> None:
    if errors:
        joined = "; ".join(errors)
        raise EmergencyError(f"Scenario validation failed: {joined}")
