"""EmergencyState — active effect tracking with additive composition.

Design (Decision 2 — approved)
-------------------------------
``EmergencyState`` is the authoritative source of truth for which network
effects are currently active and what the composite edge state should be.

It never holds a reference to the ``DirectedGraph``. It only holds:
- A mapping from ``EdgeId`` to its original (baseline) ``MutableEdgeState``.
- A list of active ``NetworkEffect`` objects, each tagged with an ``EventId``.

The ``NetworkEffectSubscriber`` reads the composite state from ``EmergencyState``
and calls ``DirectedGraph.update_edge_state`` to apply it.  This keeps the
emergency module completely independent of the graph internals.

Effect composition rules (Decision 1 — approved)
-------------------------------------------------
When computing the composite state for an edge:
1. Start from the original baseline ``MutableEdgeState``.
2. Check if ANY active effect sets ``is_blocked = True`` → if so, the
   composite state is blocked regardless of everything else.
3. Sum all ``congestion_factor_delta`` values from active ``CongestionEffect``
   objects on this edge. Add to baseline ``congestion_factor``.
4. Sum all ``hazard_penalty_s`` values additively.
5. Sum all ``emergency_penalty_s`` values additively.
6. Sum all ``communication_penalty_s`` values additively.

Resolution cleanup (Decision 2 — approved)
-------------------------------------------
When an event is resolved, all its owned ``NetworkEffect`` objects are removed
from the active list. The composite state for each affected edge is then
recomputed from scratch from the remaining active effects. This prevents
floating-point accumulation drift.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Sequence

from e3hybrid.emergency.effects import NetworkEffect
from e3hybrid.emergency.types import EventId
from e3hybrid.network.edge import MutableEdgeState
from e3hybrid.network.types import EdgeId


@dataclass
class EmergencyState:
    """Tracks active network effects and computes composite edge states.

    The ``NetworkEffectSubscriber`` calls:
    1. ``apply_effects(event_id, effects)``  — when an event activates.
    2. ``remove_effects(event_id)``          — when an event resolves/expires.
    3. ``composite_state(edge_id)``          — to get current computed state.
    4. ``register_baseline(edge_id, state)`` — before any events activate.
    """

    _baselines: dict[EdgeId, MutableEdgeState] = field(default_factory=dict)
    _effects: list[NetworkEffect] = field(default_factory=list)

    def register_baseline(
        self, edge_id: EdgeId, state: MutableEdgeState
    ) -> None:
        """Record the original pre-emergency state of an edge.

        Must be called before any effect is applied to that edge.
        Called by ``NetworkEffectSubscriber`` the first time it sees an edge.
        """
        if edge_id not in self._baselines:
            self._baselines[edge_id] = state

    def apply_effects(
        self, event_id: EventId, effects: Sequence[NetworkEffect]
    ) -> None:
        """Register all effects owned by ``event_id`` as active."""

        for effect in effects:
            self._effects.append(effect)

    def remove_effects(self, event_id: EventId) -> frozenset[EdgeId]:
        """Remove all effects owned by ``event_id``.

        Returns the set of edge IDs whose composite state may have changed
        and must be reapplied to the graph.
        """
        owned = [e for e in self._effects if e.event_id == event_id]
        affected = frozenset(e.edge_id for e in owned)
        self._effects = [e for e in self._effects if e.event_id != event_id]
        return affected

    def composite_state(self, edge_id: EdgeId) -> MutableEdgeState | None:
        """Compute the current composite ``MutableEdgeState`` for an edge.

        Returns ``None`` if the edge has never been registered (no baseline).

        Composition rules
        -----------------
        1. Start from baseline.
        2. If any effect blocks the edge → ``is_blocked = True``, stop.
        3. Otherwise apply all non-blocking effects in insertion order.
        """
        if edge_id not in self._baselines:
            return None

        active = [e for e in self._effects if e.edge_id == edge_id]
        if not active:
            return self._baselines[edge_id]

        # Rule 1: start from baseline.
        state = self._baselines[edge_id]

        # Rule 2: blocked takes precedence over everything.
        from e3hybrid.emergency.effects import RoadClosureEffect
        if any(isinstance(e, RoadClosureEffect) for e in active):
            return MutableEdgeState(
                is_blocked=True,
                current_speed_mps=state.current_speed_mps,
                travel_time_override_s=state.travel_time_override_s,
                congestion_factor=state.congestion_factor,
                hazard_penalty_s=state.hazard_penalty_s,
                emergency_penalty_s=state.emergency_penalty_s,
                communication_penalty_s=state.communication_penalty_s,
                metadata=state.metadata,
            )

        # Rule 3: apply all remaining effects additively.
        for effect in active:
            state = effect.apply(state)
        return state

    def affected_edges(self) -> frozenset[EdgeId]:
        """Return all edges that have at least one active effect."""

        return frozenset(e.edge_id for e in self._effects)

    def active_effect_count(self) -> int:
        """Return the total number of active effects across all edges."""

        return len(self._effects)

    def clear_all(self) -> None:
        """Remove all active effects (used between experiment runs)."""

        self._effects.clear()
