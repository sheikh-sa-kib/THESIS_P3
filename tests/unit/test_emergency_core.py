"""Unit tests for the Phase 5 emergency framework.

No routing, SUMO, or communication simulation.
All tests are deterministic.
"""

from __future__ import annotations

import pytest

from e3hybrid.communication.enums import Priority
from e3hybrid.core.exceptions import EmergencyError
from e3hybrid.emergency import (
    CommunicationBlackoutEvent,
    CommunicationEffect,
    CongestionEffect,
    EmergencyEventBus,
    EmergencyEventType,
    EmergencyPriorityEffect,
    EmergencyRegistry,
    EmergencyState,
    EmergencyVehicleEvent,
    EventId,
    EventLocation,
    EventScheduler,
    EventStatus,
    HazardEffect,
    HazardZoneEvent,
    InfrastructureFailureEvent,
    NetworkEffectSubscriber,
    RoadBlockEvent,
    RoadClosureEffect,
    RoadClosureEvent,
    ScenarioLoader,
    TrafficAccidentEvent,
    validate_scenario_dict,
)
from e3hybrid.network.edge import Edge, MutableEdgeState
from e3hybrid.network.fixtures import create_synthetic_test_network
from e3hybrid.network.types import EdgeId, NodeId


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _location(edge_ids=("AB",)) -> EventLocation:
    return EventLocation(edge_ids=frozenset(EdgeId(e) for e in edge_ids))


def _make_closure(
    eid="evt_001",
    at=100.0,
    dur=200.0,
    edge="AB",
    severity=0.9,
    priority=Priority.HIGH,
) -> RoadClosureEvent:
    return RoadClosureEvent(
        event_id=EventId(eid),
        event_type=EmergencyEventType.ROAD_CLOSURE,
        activation_time_s=at,
        duration_s=dur,
        severity=severity,
        priority=priority,
        location=_location([edge]),
        broadcast_radius_m=300.0,
    )


# ---------------------------------------------------------------------------
# EventLocation
# ---------------------------------------------------------------------------


def test_event_location_requires_edge_or_node() -> None:
    with pytest.raises(EmergencyError, match="edge_ids or center_node"):
        EventLocation()


def test_event_location_with_edges() -> None:
    loc = EventLocation(edge_ids=frozenset([EdgeId("AB"), EdgeId("BC")]))
    assert EdgeId("AB") in loc.edge_ids


def test_event_location_with_center_node() -> None:
    loc = EventLocation(center_node=NodeId("A"), radius_m=150.0)
    assert loc.center_node == NodeId("A")
    assert loc.radius_m == 150.0


def test_event_location_rejects_negative_radius() -> None:
    with pytest.raises(EmergencyError, match="radius_m must be positive"):
        EventLocation(center_node=NodeId("A"), radius_m=-1.0)


def test_event_location_to_dict() -> None:
    loc = EventLocation(edge_ids=frozenset([EdgeId("AB")]))
    data = loc.to_dict()
    assert "AB" in data["edge_ids"]


# ---------------------------------------------------------------------------
# RoadClosureEvent
# ---------------------------------------------------------------------------


def test_road_closure_event_construction() -> None:
    event = _make_closure()
    assert event.event_id == EventId("evt_001")
    assert event.event_type == EmergencyEventType.ROAD_CLOSURE
    assert event.is_active(100.0) is True
    assert event.is_active(299.0) is True
    assert event.is_active(300.0) is False  # expired


def test_road_closure_event_affected_edges() -> None:
    event = _make_closure(edge="AB")
    assert EdgeId("AB") in event.affected_edge_ids


def test_road_closure_rejects_negative_severity() -> None:
    with pytest.raises(EmergencyError, match="severity"):
        _make_closure(severity=-0.1)


def test_road_closure_rejects_severity_above_one() -> None:
    with pytest.raises(EmergencyError, match="severity"):
        _make_closure(severity=1.1)


def test_road_closure_rejects_negative_duration() -> None:
    with pytest.raises(EmergencyError, match="duration"):
        RoadClosureEvent(
            event_id=EventId("x"),
            event_type=EmergencyEventType.ROAD_CLOSURE,
            activation_time_s=0.0,
            duration_s=-1.0,
            severity=0.5,
            priority=Priority.NORMAL,
            location=_location(),
            broadcast_radius_m=100.0,
        )


def test_road_closure_with_status_returns_copy() -> None:
    event = _make_closure()
    resolved = event.with_status(EventStatus.RESOLVED)
    assert resolved.status == EventStatus.RESOLVED
    assert event.status == EventStatus.CREATED


def test_road_closure_to_dict_keys() -> None:
    event = _make_closure()
    data = event.to_dict()
    for key in ("event_id", "event_type", "severity", "priority",
                "activation_time_s", "duration_s", "status", "location"):
        assert key in data


# ---------------------------------------------------------------------------
# All concrete event types construction
# ---------------------------------------------------------------------------


def test_all_event_types_construct() -> None:
    base = dict(
        event_type=EmergencyEventType.ROAD_BLOCK,
        activation_time_s=50.0, duration_s=100.0,
        severity=0.5, priority=Priority.NORMAL,
        location=_location(), broadcast_radius_m=200.0,
        status=EventStatus.CREATED,
    )
    RoadBlockEvent(event_id=EventId("rb1"), **base,
                   event_type=EmergencyEventType.ROAD_BLOCK)

    TrafficAccidentEvent(event_id=EventId("ta1"), **{**base,
        "event_type": EmergencyEventType.TRAFFIC_ACCIDENT})

    EmergencyVehicleEvent(event_id=EventId("ev1"), **{**base,
        "event_type": EmergencyEventType.EMERGENCY_VEHICLE})

    InfrastructureFailureEvent(event_id=EventId("if1"), **{**base,
        "event_type": EmergencyEventType.INFRASTRUCTURE_FAILURE})

    CommunicationBlackoutEvent(event_id=EventId("cb1"), **{**base,
        "event_type": EmergencyEventType.COMMUNICATION_BLACKOUT})

    HazardZoneEvent(event_id=EventId("hz1"), **{**base,
        "event_type": EmergencyEventType.HAZARD_ZONE})


# ---------------------------------------------------------------------------
# NetworkEffect composition
# ---------------------------------------------------------------------------


def test_road_closure_effect_sets_blocked() -> None:
    state = MutableEdgeState()
    effect = RoadClosureEffect(event_id=EventId("e1"), edge_id=EdgeId("AB"))
    new = effect.apply(state)
    assert new.is_blocked is True


def test_congestion_effect_adds_delta() -> None:
    state = MutableEdgeState(congestion_factor=1.0)
    effect = CongestionEffect(event_id=EventId("e1"), edge_id=EdgeId("AB"),
                              congestion_factor_delta=0.5)
    new = effect.apply(state)
    assert new.congestion_factor == pytest.approx(1.5)


def test_hazard_effect_adds_penalty() -> None:
    state = MutableEdgeState(hazard_penalty_s=0.0)
    effect = HazardEffect(event_id=EventId("e1"), edge_id=EdgeId("AB"),
                          hazard_penalty_s=30.0)
    new = effect.apply(state)
    assert new.hazard_penalty_s == pytest.approx(30.0)


def test_emergency_priority_effect_adds_penalty() -> None:
    state = MutableEdgeState(emergency_penalty_s=0.0)
    effect = EmergencyPriorityEffect(event_id=EventId("e1"), edge_id=EdgeId("AB"),
                                     emergency_penalty_s=120.0)
    new = effect.apply(state)
    assert new.emergency_penalty_s == pytest.approx(120.0)


def test_communication_effect_adds_penalty() -> None:
    state = MutableEdgeState(communication_penalty_s=0.0)
    effect = CommunicationEffect(event_id=EventId("e1"), edge_id=EdgeId("AB"),
                                 communication_penalty_s=60.0)
    new = effect.apply(state)
    assert new.communication_penalty_s == pytest.approx(60.0)


def test_effects_are_immutable() -> None:
    """Applying an effect returns a new state, original is unchanged."""
    original = MutableEdgeState(hazard_penalty_s=0.0)
    effect = HazardEffect(event_id=EventId("e1"), edge_id=EdgeId("AB"),
                          hazard_penalty_s=10.0)
    _ = effect.apply(original)
    assert original.hazard_penalty_s == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# EmergencyState — additive composition and resolution
# ---------------------------------------------------------------------------


def test_emergency_state_single_closure_blocks_edge() -> None:
    em_state = EmergencyState()
    baseline = MutableEdgeState()
    em_state.register_baseline(EdgeId("AB"), baseline)
    effect = RoadClosureEffect(event_id=EventId("e1"), edge_id=EdgeId("AB"))
    em_state.apply_effects(EventId("e1"), [effect])
    composite = em_state.composite_state(EdgeId("AB"))
    assert composite is not None
    assert composite.is_blocked is True


def test_emergency_state_two_hazards_stack_additively() -> None:
    em_state = EmergencyState()
    baseline = MutableEdgeState()
    em_state.register_baseline(EdgeId("AB"), baseline)
    em_state.apply_effects(EventId("e1"), [
        HazardEffect(event_id=EventId("e1"), edge_id=EdgeId("AB"), hazard_penalty_s=10.0)
    ])
    em_state.apply_effects(EventId("e2"), [
        HazardEffect(event_id=EventId("e2"), edge_id=EdgeId("AB"), hazard_penalty_s=20.0)
    ])
    composite = em_state.composite_state(EdgeId("AB"))
    assert composite is not None
    assert composite.hazard_penalty_s == pytest.approx(30.0)


def test_emergency_state_blocked_takes_precedence_over_hazard() -> None:
    em_state = EmergencyState()
    baseline = MutableEdgeState()
    em_state.register_baseline(EdgeId("AB"), baseline)
    em_state.apply_effects(EventId("e1"), [
        HazardEffect(event_id=EventId("e1"), edge_id=EdgeId("AB"), hazard_penalty_s=999.0)
    ])
    em_state.apply_effects(EventId("e2"), [
        RoadClosureEffect(event_id=EventId("e2"), edge_id=EdgeId("AB"))
    ])
    composite = em_state.composite_state(EdgeId("AB"))
    assert composite is not None
    assert composite.is_blocked is True


def test_emergency_state_resolution_restores_baseline() -> None:
    em_state = EmergencyState()
    baseline = MutableEdgeState()
    em_state.register_baseline(EdgeId("AB"), baseline)
    em_state.apply_effects(EventId("e1"), [
        HazardEffect(event_id=EventId("e1"), edge_id=EdgeId("AB"), hazard_penalty_s=30.0)
    ])
    assert em_state.composite_state(EdgeId("AB")).hazard_penalty_s == pytest.approx(30.0)

    em_state.remove_effects(EventId("e1"))
    restored = em_state.composite_state(EdgeId("AB"))
    assert restored is not None
    assert restored.hazard_penalty_s == pytest.approx(0.0)
    assert restored.is_blocked is False


def test_emergency_state_partial_resolution_preserves_other_effects() -> None:
    em_state = EmergencyState()
    baseline = MutableEdgeState()
    em_state.register_baseline(EdgeId("AB"), baseline)
    em_state.apply_effects(EventId("e1"), [
        HazardEffect(event_id=EventId("e1"), edge_id=EdgeId("AB"), hazard_penalty_s=10.0)
    ])
    em_state.apply_effects(EventId("e2"), [
        HazardEffect(event_id=EventId("e2"), edge_id=EdgeId("AB"), hazard_penalty_s=20.0)
    ])
    # Remove only e1; e2 remains
    em_state.remove_effects(EventId("e1"))
    composite = em_state.composite_state(EdgeId("AB"))
    assert composite.hazard_penalty_s == pytest.approx(20.0)


def test_emergency_state_unknown_edge_returns_none() -> None:
    em_state = EmergencyState()
    assert em_state.composite_state(EdgeId("XX")) is None


# ---------------------------------------------------------------------------
# NetworkEffectSubscriber + DirectedGraph integration
# ---------------------------------------------------------------------------


def test_network_effect_subscriber_applies_closure() -> None:
    graph = create_synthetic_test_network()
    em_state = EmergencyState()
    subscriber = NetworkEffectSubscriber(graph, em_state)

    event = _make_closure(at=0.0, dur=300.0, edge="AB")
    activated = event.with_status(EventStatus.ACTIVATED)
    subscriber.handle(activated)

    edge = graph.get_edge(EdgeId("AB"))
    assert edge.state.is_blocked is True


def test_network_effect_subscriber_restores_on_resolution() -> None:
    graph = create_synthetic_test_network()
    em_state = EmergencyState()
    subscriber = NetworkEffectSubscriber(graph, em_state)

    event = _make_closure(at=0.0, dur=300.0, edge="AB")
    subscriber.handle(event.with_status(EventStatus.ACTIVATED))
    assert graph.get_edge(EdgeId("AB")).state.is_blocked is True

    subscriber.handle(event.with_status(EventStatus.RESOLVED))
    assert graph.get_edge(EdgeId("AB")).state.is_blocked is False


def test_network_effect_subscriber_hazard_penalty() -> None:
    graph = create_synthetic_test_network()
    em_state = EmergencyState()
    subscriber = NetworkEffectSubscriber(graph, em_state)

    event = HazardZoneEvent(
        event_id=EventId("hz1"),
        event_type=EmergencyEventType.HAZARD_ZONE,
        activation_time_s=0.0, duration_s=100.0,
        severity=0.5, priority=Priority.NORMAL,
        location=_location(["BC"]), broadcast_radius_m=200.0,
        hazard_penalty_s=45.0,
    )
    subscriber.handle(event.with_status(EventStatus.ACTIVATED))
    assert graph.get_edge(EdgeId("BC")).state.hazard_penalty_s == pytest.approx(45.0)


# ---------------------------------------------------------------------------
# EmergencyEventBus
# ---------------------------------------------------------------------------


def test_bus_delivers_to_typed_subscriber() -> None:
    bus = EmergencyEventBus()
    received = []
    bus.subscribe(EmergencyEventType.ROAD_CLOSURE, received.append)

    bus.publish(_make_closure())
    assert len(received) == 1


def test_bus_delivers_to_all_subscriber() -> None:
    bus = EmergencyEventBus()
    received = []
    bus.subscribe_all(received.append)

    bus.publish(_make_closure())
    assert len(received) == 1


def test_bus_does_not_deliver_wrong_type() -> None:
    bus = EmergencyEventBus()
    received = []
    bus.subscribe(EmergencyEventType.HAZARD_ZONE, received.append)

    bus.publish(_make_closure())  # road_closure, not hazard_zone
    assert len(received) == 0


def test_bus_priority_ordering() -> None:
    bus = EmergencyEventBus()
    order = []
    bus.subscribe(EmergencyEventType.ROAD_CLOSURE,
                  lambda e: order.append("low"), priority=0)
    bus.subscribe(EmergencyEventType.ROAD_CLOSURE,
                  lambda e: order.append("high"), priority=10)

    bus.publish(_make_closure())
    assert order == ["high", "low"]


def test_bus_exception_isolation() -> None:
    bus = EmergencyEventBus()
    received = []

    def bad_handler(e): raise RuntimeError("subscriber failure")
    def good_handler(e): received.append(e)

    bus.subscribe(EmergencyEventType.ROAD_CLOSURE, bad_handler, priority=10)
    bus.subscribe(EmergencyEventType.ROAD_CLOSURE, good_handler, priority=0)

    bus.publish(_make_closure())  # bad_handler raises, good_handler still runs
    assert len(received) == 1


def test_bus_unsubscribe() -> None:
    bus = EmergencyEventBus()
    received = []
    bus.subscribe(EmergencyEventType.ROAD_CLOSURE, received.append)
    bus.unsubscribe(EmergencyEventType.ROAD_CLOSURE, received.append)

    bus.publish(_make_closure())
    assert len(received) == 0


def test_bus_statistics() -> None:
    bus = EmergencyEventBus()
    bus.subscribe_all(lambda e: None)
    bus.publish(_make_closure())
    bus.publish(_make_closure(eid="e2"))

    stats = bus.statistics
    assert stats.events_published == 2
    assert stats.total_deliveries == 2
    assert stats.total_failures == 0


def test_bus_clear_removes_subscribers_and_stats() -> None:
    bus = EmergencyEventBus()
    received = []
    bus.subscribe_all(received.append)
    bus.publish(_make_closure())
    bus.clear()
    bus.publish(_make_closure())  # no subscribers now
    assert len(received) == 1  # only first publish


# ---------------------------------------------------------------------------
# EmergencyRegistry
# ---------------------------------------------------------------------------


def test_registry_register_and_get() -> None:
    reg = EmergencyRegistry()
    event = _make_closure()
    reg.register(event)
    assert reg.get(EventId("evt_001")).event_id == EventId("evt_001")


def test_registry_rejects_duplicate_id() -> None:
    reg = EmergencyRegistry()
    reg.register(_make_closure())
    with pytest.raises(EmergencyError, match="duplicate event_id"):
        reg.register(_make_closure())


def test_registry_unknown_id_raises() -> None:
    reg = EmergencyRegistry()
    with pytest.raises(EmergencyError, match="unknown event_id"):
        reg.get(EventId("missing"))


def test_registry_status_transition() -> None:
    reg = EmergencyRegistry()
    reg.register(_make_closure())
    reg.update_status(EventId("evt_001"), EventStatus.SCHEDULED)
    assert reg.get(EventId("evt_001")).status == EventStatus.SCHEDULED


def test_registry_rejects_backward_transition() -> None:
    reg = EmergencyRegistry()
    reg.register(_make_closure())
    reg.update_status(EventId("evt_001"), EventStatus.SCHEDULED)
    with pytest.raises(EmergencyError, match="invalid status transition"):
        reg.update_status(EventId("evt_001"), EventStatus.CREATED)


def test_registry_terminal_state_cannot_be_updated() -> None:
    reg = EmergencyRegistry()
    event = _make_closure()
    reg.register(event)
    reg.update_status(EventId("evt_001"), EventStatus.SCHEDULED)
    reg.update_status(EventId("evt_001"), EventStatus.ACTIVATED)
    reg.update_status(EventId("evt_001"), EventStatus.RESOLVED)
    with pytest.raises(EmergencyError, match="terminal state"):
        reg.update_status(EventId("evt_001"), EventStatus.BROADCAST)


def test_registry_active_events_filter() -> None:
    reg = EmergencyRegistry()
    e1 = _make_closure(eid="e1", at=0.0, dur=100.0)
    e2 = _make_closure(eid="e2", at=200.0, dur=100.0)
    reg.register(e1)
    reg.register(e2)
    active = reg.active_events(sim_time_s=50.0)
    ids = {e.event_id for e in active}
    assert EventId("e1") in ids
    assert EventId("e2") not in ids


# ---------------------------------------------------------------------------
# EventScheduler
# ---------------------------------------------------------------------------


def test_scheduler_fixed_event_activates_at_correct_time() -> None:
    sched = EventScheduler(seed=0)
    sched.schedule(_make_closure(at=100.0))

    assert sched.tick(50.0) == []
    events = sched.tick(100.0)
    assert len(events) == 1
    assert events[0].event_id == EventId("evt_001")
    assert events[0].status == EventStatus.ACTIVATED


def test_scheduler_deterministic_replay() -> None:
    """Same seed and same events must produce identical activation order."""
    def run(seed):
        sched = EventScheduler(seed=seed)
        event = _make_closure(at=50.0)
        sched.schedule_random(event, earliest_s=10.0, latest_s=100.0, count=3)
        activated = sched.tick(200.0)
        return [e.event_id for e in activated]

    assert run(42) == run(42)


def test_scheduler_different_seeds_differ() -> None:
    """Different seeds should (almost always) produce different schedules."""
    def run(seed):
        sched = EventScheduler(seed=seed)
        event = _make_closure(at=50.0)
        sched.schedule_random(event, earliest_s=0.0, latest_s=1000.0, count=5)
        return [e.event_id for e in sched.tick(2000.0)]

    # With 5 random events in [0, 1000], different seeds should differ
    assert run(1) != run(999)


def test_scheduler_recurring_fires_multiple_times() -> None:
    sched = EventScheduler(seed=0)
    template = _make_closure(at=0.0, dur=10.0)
    sched.schedule_recurring(template, first_activation_s=0.0, interval_s=50.0,
                              max_occurrences=3)

    all_events = sched.tick(200.0)
    assert len(all_events) == 3


def test_scheduler_random_count() -> None:
    sched = EventScheduler(seed=7)
    template = _make_closure(at=0.0)
    sched.schedule_random(template, earliest_s=0.0, latest_s=500.0, count=4)
    events = sched.tick(600.0)
    assert len(events) == 4


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _minimal_scenario(override: dict | None = None) -> dict:
    base: dict = {
        "scenario": {
            "name": "test",
            "seed": 0,
            "simulation_duration_s": 3600.0,
            "events": [
                {
                    "id": "evt_001",
                    "type": "road_closure",
                    "activation_time": 100.0,
                    "duration": 300.0,
                    "severity": 0.8,
                    "priority": "high",
                    "broadcast_radius_m": 500.0,
                    "location": {"edge_ids": ["AB"]},
                }
            ],
        }
    }
    if override:
        base["scenario"]["events"][0].update(override)
    return base


def test_validation_accepts_valid_scenario() -> None:
    validate_scenario_dict(_minimal_scenario())  # must not raise


def test_validation_rejects_missing_scenario_key() -> None:
    with pytest.raises(EmergencyError, match="'scenario' key"):
        validate_scenario_dict({})


def test_validation_rejects_duplicate_event_id() -> None:
    data = _minimal_scenario()
    data["scenario"]["events"].append(dict(data["scenario"]["events"][0]))
    with pytest.raises(EmergencyError, match="duplicate event id"):
        validate_scenario_dict(data)


def test_validation_rejects_negative_activation_time() -> None:
    with pytest.raises(EmergencyError, match="activation_time must be non-negative"):
        validate_scenario_dict(_minimal_scenario({"activation_time": -1.0}))


def test_validation_rejects_negative_duration() -> None:
    with pytest.raises(EmergencyError, match="duration must be positive"):
        validate_scenario_dict(_minimal_scenario({"duration": -10.0}))


def test_validation_rejects_invalid_severity() -> None:
    with pytest.raises(EmergencyError, match="severity must be in"):
        validate_scenario_dict(_minimal_scenario({"severity": 1.5}))


def test_validation_rejects_unknown_event_type() -> None:
    with pytest.raises(EmergencyError, match="not a valid EmergencyEventType"):
        validate_scenario_dict(_minimal_scenario({"type": "volcano_eruption"}))


def test_validation_rejects_missing_location() -> None:
    data = _minimal_scenario()
    del data["scenario"]["events"][0]["location"]
    with pytest.raises(EmergencyError, match="location is required"):
        validate_scenario_dict(data)


def test_validation_rejects_empty_location() -> None:
    with pytest.raises(EmergencyError, match="edge_ids or center_node"):
        validate_scenario_dict(_minimal_scenario({"location": {}}))


def test_validation_rejects_activation_exceeds_simulation_duration() -> None:
    with pytest.raises(EmergencyError, match="exceeds simulation_duration_s"):
        validate_scenario_dict(_minimal_scenario({"activation_time": 9999.0}))


def test_validation_rejects_invalid_priority() -> None:
    with pytest.raises(EmergencyError, match="priority must be one of"):
        validate_scenario_dict(_minimal_scenario({"priority": "extreme"}))


# ---------------------------------------------------------------------------
# ScenarioLoader
# ---------------------------------------------------------------------------


def test_scenario_loader_dict_round_trip() -> None:
    loader = ScenarioLoader()
    scenario = loader.load_dict(_minimal_scenario())
    assert scenario.metadata.name == "test"
    assert scenario.metadata.seed == 0
    assert scenario.metadata.event_count == 1


def test_scenario_loader_produces_scheduled_events() -> None:
    loader = ScenarioLoader()
    scenario = loader.load_dict(_minimal_scenario())
    assert scenario.scheduler.pending_count() == 1
    events = scenario.scheduler.tick(200.0)
    assert len(events) == 1
    assert events[0].event_type == EmergencyEventType.ROAD_CLOSURE


def test_scenario_loader_all_event_types() -> None:
    """ScenarioLoader must construct all Phase 5 event types without error."""
    types_and_extras = [
        ("road_closure", {}),
        ("road_block", {"congestion_factor_delta": 0.5}),
        ("traffic_accident", {"vehicle_count": 2}),
        ("emergency_vehicle", {"emergency_penalty_s": 120.0}),
        ("infrastructure_failure", {}),
        ("communication_blackout", {"communication_penalty_s": 60.0}),
        ("hazard_zone", {"hazard_penalty_s": 30.0}),
    ]
    for i, (event_type, extras) in enumerate(types_and_extras):
        data = _minimal_scenario({
            "id": f"evt_{i:03d}",
            "type": event_type,
            **extras,
        })
        data["scenario"]["events"][0].update({"id": f"evt_{i:03d}", "type": event_type})
        loader = ScenarioLoader()
        scenario = loader.load_dict(data)
        events = scenario.scheduler.tick(200.0)
        assert len(events) == 1
        assert str(events[0].event_type) == event_type


# ---------------------------------------------------------------------------
# End-to-end: scheduler → bus → subscriber → graph
# ---------------------------------------------------------------------------


def test_end_to_end_activation_and_resolution() -> None:
    """Full pipeline: scenario load → tick → publish → graph effect → resolve."""
    graph = create_synthetic_test_network()
    em_state = EmergencyState()
    subscriber = NetworkEffectSubscriber(graph, em_state)

    bus = EmergencyEventBus()
    bus.subscribe_all(subscriber.handle, priority=100)

    loader = ScenarioLoader()
    scenario = loader.load_dict(_minimal_scenario())

    # Tick 100 — event activates
    events = scenario.scheduler.tick(100.0)
    assert len(events) == 1
    activated = events[0]
    bus.publish(activated)

    assert graph.get_edge(EdgeId("AB")).state.is_blocked is True

    # Resolve the event
    resolved = activated.with_status(EventStatus.RESOLVED)
    bus.publish(resolved)

    assert graph.get_edge(EdgeId("AB")).state.is_blocked is False
