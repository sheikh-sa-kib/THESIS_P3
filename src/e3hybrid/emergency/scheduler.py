"""EventScheduler — deterministic, reproducible event scheduling.

Every scheduling mode (fixed, random/seeded, progressive, recurring) passes
through ``tick(sim_time_s)`` which returns a list of newly activated events.
The caller publishes these to the ``EmergencyEventBus``.

Reproducibility guarantee
--------------------------
Random event generation uses a named ``random.Random`` instance seeded from
the scenario's seed value.  Given the same seed and scenario file, every run
produces exactly the same event activation sequence.  The seed is recorded in
``environment.json`` by the reproducibility module.

Scheduling modes
----------------
FIXED       — event activates at a specified ``activation_time_s``.
RANDOM      — events drawn from a Poisson process within [earliest, latest].
RECURRING   — event repeats every ``interval_s`` starting at ``first_activation_s``.
PROGRESSIVE — event automatically escalates to a new type after a threshold.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Sequence

from e3hybrid.core.exceptions import EmergencyError
from e3hybrid.emergency.event import EmergencyEvent
from e3hybrid.emergency.types import EventId, EventStatus


@dataclass
class ScheduledEntry:
    """Internal scheduler record for one event instance."""

    event: EmergencyEvent
    scheduled_time: float


@dataclass
class RecurringConfig:
    """Configuration for a recurring event template."""

    template: EmergencyEvent
    first_activation_s: float
    interval_s: float
    max_occurrences: int | None
    _occurrences_fired: int = 0

    def next_activation(self, after_s: float) -> float | None:
        """Return the next activation time after ``after_s``, or None if done."""
        if self.max_occurrences is not None:
            if self._occurrences_fired >= self.max_occurrences:
                return None
        count = 0
        t = self.first_activation_s
        while t <= after_s:
            t += self.interval_s
            count += 1
        return t


@dataclass
class EventScheduler:
    """Deterministic event scheduler supporting all scheduling modes.

    Parameters
    ----------
    seed:
        Random seed for Poisson event generation.  Stored in environment
        metadata for reproducibility.
    """

    seed: int = 0
    _queue: list[ScheduledEntry] = field(default_factory=list)
    _recurring: list[RecurringConfig] = field(default_factory=list)
    _activated_ids: set[EventId] = field(default_factory=set)
    _rng: random.Random = field(init=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def schedule(self, event: EmergencyEvent) -> None:
        """Add a fixed-time event to the queue."""

        if event.event_id in self._activated_ids:
            raise EmergencyError(
                f"cannot schedule already-activated event '{event.event_id}'"
            )
        self._queue.append(
            ScheduledEntry(event=event, scheduled_time=event.activation_time_s)
        )
        # Stable sort: earlier activation first; equal times preserve insertion order
        self._queue.sort(key=lambda e: e.scheduled_time)

    def schedule_recurring(
        self,
        template: EmergencyEvent,
        first_activation_s: float,
        interval_s: float,
        max_occurrences: int | None = None,
    ) -> None:
        """Register a recurring event template.

        Each occurrence is a copy of ``template`` with a unique ID and
        adjusted ``activation_time_s``.  IDs are generated as
        ``{template.event_id}_r{n}`` where n is the occurrence index.
        """
        if interval_s <= 0:
            raise EmergencyError("recurring interval_s must be positive")
        self._recurring.append(
            RecurringConfig(
                template=template,
                first_activation_s=first_activation_s,
                interval_s=interval_s,
                max_occurrences=max_occurrences,
            )
        )

    def schedule_random(
        self,
        template: EmergencyEvent,
        earliest_s: float,
        latest_s: float,
        count: int,
    ) -> None:
        """Generate ``count`` random events between ``earliest_s`` and ``latest_s``.

        Activation times are drawn uniformly from the interval using the
        seeded RNG.  IDs are generated as ``{template.event_id}_rand{n}``.
        All activations are reproducible for a given seed.
        """
        if earliest_s >= latest_s:
            raise EmergencyError(
                "schedule_random: earliest_s must be less than latest_s"
            )
        if count <= 0:
            raise EmergencyError("schedule_random: count must be positive")

        times = sorted(
            self._rng.uniform(earliest_s, latest_s) for _ in range(count)
        )
        from e3hybrid.emergency.types import EventId

        for n, t in enumerate(times):
            new_id = EventId(f"{template.event_id}_rand{n}")
            # Build a new event with adjusted id and activation time.
            updated = template.with_status(template.status)
            # Re-create with new activation_time_s via dataclass replace pattern.
            import dataclasses
            overrides: dict = {
                "event_id": new_id,
                "activation_time_s": t,
                "status": EventStatus.CREATED,
            }
            new_event = dataclasses.replace(updated, **overrides)  # type: ignore[arg-type]
            self.schedule(new_event)

    # ------------------------------------------------------------------
    # Tick
    # ------------------------------------------------------------------

    def tick(self, sim_time_s: float) -> list[EmergencyEvent]:
        """Advance the scheduler and return events that activate at this time.

        Recurring events are expanded lazily.  All activations at
        ``sim_time_s <= activation_time`` are returned in order.
        """
        # Expand recurring events that should have fired by now
        self._expand_recurring(sim_time_s)

        activated = []
        remaining = []
        for entry in self._queue:
            if entry.scheduled_time <= sim_time_s:
                if entry.event.event_id not in self._activated_ids:
                    self._activated_ids.add(entry.event.event_id)
                    activated_event = entry.event.with_status(EventStatus.ACTIVATED)
                    activated.append(activated_event)
            else:
                remaining.append(entry)

        self._queue = remaining
        return activated

    def _expand_recurring(self, up_to_s: float) -> None:
        """Materialise recurring event instances up to ``up_to_s``."""

        from e3hybrid.emergency.types import EventId
        import dataclasses

        for cfg in self._recurring:
            while True:
                next_t = cfg.next_activation(
                    cfg.first_activation_s
                    + cfg._occurrences_fired * cfg.interval_s
                    - cfg.interval_s
                )
                if next_t is None or next_t > up_to_s:
                    break
                n = cfg._occurrences_fired
                new_id = EventId(f"{cfg.template.event_id}_r{n}")
                if new_id not in self._activated_ids:
                    new_event = dataclasses.replace(  # type: ignore[arg-type]
                        cfg.template,
                        event_id=new_id,
                        activation_time_s=next_t,
                        status=EventStatus.CREATED,
                    )
                    self._queue.append(
                        ScheduledEntry(event=new_event, scheduled_time=next_t)
                    )
                cfg._occurrences_fired += 1
                if (
                    cfg.max_occurrences is not None
                    and cfg._occurrences_fired >= cfg.max_occurrences
                ):
                    break

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def pending_count(self) -> int:
        """Return the number of events waiting to be activated."""
        return len(self._queue)

    def is_empty(self) -> bool:
        return not self._queue and not any(
            (cfg.max_occurrences is None or cfg._occurrences_fired < cfg.max_occurrences)
            for cfg in self._recurring
        )

    def clear(self) -> None:
        """Remove all scheduled events and recurring configs."""
        self._queue.clear()
        self._recurring.clear()
        self._activated_ids.clear()
