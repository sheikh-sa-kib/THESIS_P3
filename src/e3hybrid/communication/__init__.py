"""Simulator-independent communication framework.

This module provides the infrastructure for message passing between
simulation agents (vehicles, infrastructure, emergency coordinator).

Design philosophy
-----------------
The communication layer follows the same Protocol-based design as
``CostProvider`` and ``EnergyModel``:

- ``CommunicationProtocol`` is a Protocol — the MessageBus never imports a
  concrete channel model.
- ``PacketLossModel`` is a Protocol — pluggable loss models.
- ``LatencyModel`` is a Protocol — pluggable delay models.
- ``CommunicationRadiusModel`` is a Protocol — pluggable range models.

The layer never knows about:
- routing algorithms (ACO, BCO, PSO)
- vehicle physics or energy consumption
- SUMO or TraCI
- emergency corridor logic

It only transports packets.

Public interfaces
-----------------
Entities
  Message, Packet

Enumerations
  MessageType, Priority, DeliveryStatus

Protocols (interfaces)
  CommunicationProtocol, PacketLossModel, LatencyModel,
  CommunicationRadiusModel

Baseline models
  NoLossModel, ZeroLatencyModel, ConstantLatencyModel,
  InfiniteRadiusModel, FixedRadiusModel, DeterministicProtocol

Bus
  MessageBus, Broadcaster, Receiver

Statistics
  CommunicationStatistics

Types
  MessageId, VehicleId (re-exported)
"""

from e3hybrid.communication.bus import Broadcaster, MessageBus, Receiver
from e3hybrid.communication.enums import MessageType, Priority
from e3hybrid.communication.message import Message
from e3hybrid.communication.models import (
    ConstantLatencyModel,
    DeterministicProtocol,
    FixedRadiusModel,
    InfiniteRadiusModel,
    NoLossModel,
    ZeroLatencyModel,
)
from e3hybrid.communication.packet import Packet
from e3hybrid.communication.protocols import (
    CommunicationProtocol,
    CommunicationRadiusModel,
    LatencyModel,
    PacketLossModel,
)
from e3hybrid.communication.statistics import CommunicationStatistics
from e3hybrid.communication.types import DeliveryStatus, MessageId

__all__ = [
    "Broadcaster",
    "CommunicationProtocol",
    "CommunicationRadiusModel",
    "CommunicationStatistics",
    "ConstantLatencyModel",
    "DeliveryStatus",
    "DeterministicProtocol",
    "FixedRadiusModel",
    "InfiniteRadiusModel",
    "LatencyModel",
    "Message",
    "MessageBus",
    "MessageId",
    "MessageType",
    "NoLossModel",
    "Packet",
    "PacketLossModel",
    "Priority",
    "Receiver",
    "ZeroLatencyModel",
]
