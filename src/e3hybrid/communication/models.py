"""Deterministic baseline communication model implementations.

These are the simplest possible implementations of each Protocol interface.
They are used:

- In all Phase 4 unit tests (deterministic, no randomness).
- As the default channel model until a realistic model is approved.
- As a sanity-check baseline in experiments (an ideal channel that never
  drops packets and has zero latency sets an upper-bound on performance).

Implementations provided
------------------------
``NoLossModel``          – PacketLossModel:          never drops a packet.
``ZeroLatencyModel``     – LatencyModel:             always returns 0.0 s.
``ConstantLatencyModel`` – LatencyModel:             returns a fixed delay.
``InfiniteRadiusModel``  – CommunicationRadiusModel: all agents always in range.
``FixedRadiusModel``     – CommunicationRadiusModel: disk model with a
                           configurable radius; requires position injection.
``DeterministicProtocol``– CommunicationProtocol:   bundles NoLoss + Zero
                           Latency + InfiniteRadius.

Future models (not in Phase 4)
-------------------------------
``DistanceLossModel``    – probability of loss increases with distance.
``DSRCLatencyModel``     – IEEE 802.11p delay distribution.
``ObstacleRadiusModel``  – SUMO-integrated line-of-sight radius.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from e3hybrid.communication.packet import Packet
from e3hybrid.communication.protocols import (
    CommunicationRadiusModel,
    LatencyModel,
    PacketLossModel,
)
from e3hybrid.core.exceptions import CommunicationError
from e3hybrid.vehicle.types import VehicleId


# ---------------------------------------------------------------------------
# Packet loss models
# ---------------------------------------------------------------------------


class NoLossModel:
    """Always returns False — no packet is ever lost.

    Use as the baseline for unit tests and ideal-channel experiments.
    """

    def is_lost(self, packet: Packet) -> bool:
        """Return False unconditionally."""

        return False


# ---------------------------------------------------------------------------
# Latency models
# ---------------------------------------------------------------------------


class ZeroLatencyModel:
    """Always returns 0.0 seconds.

    Use as the baseline for unit tests and synchronous delivery scenarios.
    """

    def compute_latency_s(self, packet: Packet) -> float:
        """Return 0.0 unconditionally."""

        return 0.0


@dataclass(frozen=True, slots=True)
class ConstantLatencyModel:
    """Returns a fixed latency for all packets.

    Parameters
    ----------
    latency_s:
        Fixed delay in simulation seconds. Must be non-negative.

    Use this model when a flat per-hop delay is needed (e.g., 0.01 s for
    DSRC in free-flow conditions, or 0.1 s for a congested channel).
    """

    latency_s: float

    def __post_init__(self) -> None:
        if self.latency_s < 0:
            raise CommunicationError("ConstantLatencyModel.latency_s must be non-negative")

    def compute_latency_s(self, packet: Packet) -> float:
        """Return the configured constant latency."""

        return self.latency_s


# ---------------------------------------------------------------------------
# Communication radius models
# ---------------------------------------------------------------------------


class InfiniteRadiusModel:
    """All agents are always within range of each other.

    Use as the baseline for unit tests and ideal-connectivity experiments.
    The sender is excluded from its own broadcasts.
    """

    def in_range(self, sender_id: VehicleId, receiver_id: VehicleId) -> bool:
        """Return True for all distinct sender/receiver pairs."""

        return sender_id != receiver_id

    def receivers_in_range(
        self,
        sender_id: VehicleId,
        all_receiver_ids: frozenset[VehicleId],
    ) -> frozenset[VehicleId]:
        """Return all receivers except the sender."""

        return frozenset(r for r in all_receiver_ids if r != sender_id)


@dataclass(frozen=True, slots=True)
class FixedRadiusModel:
    """Disk-model radius check based on pre-registered positions.

    Positions are injected via ``register_position`` before each tick.
    When a position is unknown, the agent is treated as out of range
    (fail-safe: unknown agents cannot receive messages).

    Parameters
    ----------
    radius_m:
        Communication radius in metres. Must be positive.

    This model is sufficient for Phase 4 testing without SUMO. In Phase 8,
    positions will be supplied by TraCI and registered each simulation tick.
    """

    radius_m: float
    _positions: dict[VehicleId, tuple[float, float]] = field(
        default_factory=dict, init=False, compare=False, repr=False
    )

    def __post_init__(self) -> None:
        if self.radius_m <= 0:
            raise CommunicationError("FixedRadiusModel.radius_m must be positive")
        # Bypass frozen=True to initialise the mutable positions dict.
        object.__setattr__(self, "_positions", {})

    def register_position(self, vehicle_id: VehicleId, x: float, y: float) -> None:
        """Register or update the position of a vehicle."""

        self._positions[vehicle_id] = (x, y)

    def in_range(self, sender_id: VehicleId, receiver_id: VehicleId) -> bool:
        """Return True when receiver is within ``radius_m`` of sender."""

        if sender_id == receiver_id:
            return False
        if sender_id not in self._positions or receiver_id not in self._positions:
            return False
        sx, sy = self._positions[sender_id]
        rx, ry = self._positions[receiver_id]
        dist_sq = (sx - rx) ** 2 + (sy - ry) ** 2
        return dist_sq <= self.radius_m ** 2

    def receivers_in_range(
        self,
        sender_id: VehicleId,
        all_receiver_ids: frozenset[VehicleId],
    ) -> frozenset[VehicleId]:
        """Return receivers within the disk radius."""

        return frozenset(
            r for r in all_receiver_ids if self.in_range(sender_id, r)
        )


# ---------------------------------------------------------------------------
# Bundled deterministic protocol
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DeterministicProtocol:
    """No-loss, zero-latency, infinite-radius protocol.

    The default channel model for Phase 4 unit tests and early experiments.
    Replace with a realistic protocol once the simulation core is ready.

    All three sub-models satisfy their respective Protocols and can be
    substituted independently without changing this class.
    """

    _loss_model: PacketLossModel = field(default_factory=NoLossModel)
    _latency_model: LatencyModel = field(default_factory=ZeroLatencyModel)
    _radius_model: CommunicationRadiusModel = field(
        default_factory=InfiniteRadiusModel
    )

    @property
    def loss_model(self) -> PacketLossModel:
        """Return the packet loss model."""

        return self._loss_model

    @property
    def latency_model(self) -> LatencyModel:
        """Return the latency model."""

        return self._latency_model

    @property
    def radius_model(self) -> CommunicationRadiusModel:
        """Return the communication radius model."""

        return self._radius_model
