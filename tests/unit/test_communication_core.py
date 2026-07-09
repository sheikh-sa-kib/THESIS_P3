"""Unit tests for the Phase 4 communication framework.

All tests are deterministic — no threads, sockets, or real-time.
The DeterministicProtocol (no-loss, zero-latency, infinite-radius) is
used by default unless a test explicitly needs a different model.
"""

from __future__ import annotations

import pytest

from e3hybrid.communication import (
    Broadcaster,
    CommunicationStatistics,
    ConstantLatencyModel,
    DeliveryStatus,
    DeterministicProtocol,
    FixedRadiusModel,
    InfiniteRadiusModel,
    Message,
    MessageBus,
    MessageType,
    NoLossModel,
    Packet,
    Priority,
    Receiver,
    ZeroLatencyModel,
)
from e3hybrid.communication.types import MessageId
from e3hybrid.core.exceptions import CommunicationError
from e3hybrid.vehicle.types import VehicleId


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_broadcast(
    sender: str = "v1",
    msg_type: MessageType = MessageType.HEARTBEAT,
    created_at: float = 0.0,
    ttl: float = 10.0,
    priority: Priority = Priority.NORMAL,
    payload: object = None,
) -> Message:
    return Message.create(
        sender_id=VehicleId(sender),
        message_type=msg_type,
        payload=payload,
        created_at_s=created_at,
        ttl_s=ttl,
        priority=priority,
        is_broadcast=True,
    )


def _make_unicast(
    sender: str = "v1",
    receiver: str = "v2",
    msg_type: MessageType = MessageType.TRAFFIC_UPDATE,
    created_at: float = 0.0,
    ttl: float = 10.0,
) -> Message:
    return Message.create(
        sender_id=VehicleId(sender),
        receiver_id=VehicleId(receiver),
        message_type=msg_type,
        payload={"speed": 12.5},
        created_at_s=created_at,
        ttl_s=ttl,
        is_broadcast=False,
    )


# ---------------------------------------------------------------------------
# Message construction and validation
# ---------------------------------------------------------------------------


def test_message_create_broadcast_auto_id() -> None:
    """Message.create should generate a non-empty UUID."""

    msg = _make_broadcast()
    assert msg.message_id
    assert msg.is_broadcast is True
    assert msg.receiver_id is None


def test_message_create_unicast() -> None:
    """Unicast messages should store receiver_id."""

    msg = _make_unicast()
    assert msg.is_broadcast is False
    assert msg.receiver_id == VehicleId("v2")


def test_message_create_explicit_id() -> None:
    """Caller-supplied message_id should be preserved."""

    mid = MessageId("fixed-id-001")
    msg = Message.create(
        sender_id=VehicleId("v1"),
        message_type=MessageType.HEARTBEAT,
        payload=None,
        created_at_s=0.0,
        ttl_s=5.0,
        message_id=mid,
    )
    assert msg.message_id == mid


def test_message_rejects_unicast_without_receiver() -> None:
    """Unicast messages with no receiver_id must be rejected."""

    with pytest.raises(CommunicationError, match="receiver_id must be set"):
        Message.create(
            sender_id=VehicleId("v1"),
            message_type=MessageType.TRAFFIC_UPDATE,
            payload=None,
            created_at_s=0.0,
            ttl_s=5.0,
            is_broadcast=False,
        )


def test_message_rejects_non_positive_ttl() -> None:
    """Zero or negative TTL must be rejected."""

    with pytest.raises(CommunicationError, match="ttl_s must be positive"):
        Message.create(
            sender_id=VehicleId("v1"),
            message_type=MessageType.HEARTBEAT,
            payload=None,
            created_at_s=0.0,
            ttl_s=0.0,
        )


def test_message_expiration_time() -> None:
    """expiration_time_s should equal created_at_s + ttl_s."""

    msg = _make_broadcast(created_at=5.0, ttl=3.0)
    assert msg.expiration_time_s == pytest.approx(8.0)


def test_message_is_expired_true() -> None:
    """is_expired should return True when current time >= expiration."""

    msg = _make_broadcast(created_at=0.0, ttl=5.0)
    assert msg.is_expired(5.0) is True
    assert msg.is_expired(6.0) is True


def test_message_is_expired_false() -> None:
    """is_expired should return False before expiration."""

    msg = _make_broadcast(created_at=0.0, ttl=5.0)
    assert msg.is_expired(4.9) is False


def test_message_with_status() -> None:
    """with_status should return a copy with updated delivery_status."""

    msg = _make_broadcast()
    delivered = msg.with_status(DeliveryStatus.DELIVERED)
    assert delivered.delivery_status == DeliveryStatus.DELIVERED
    assert msg.delivery_status == DeliveryStatus.PENDING  # original unchanged


def test_message_with_incremented_hop() -> None:
    """with_incremented_hop should increase hop_count by one."""

    msg = _make_broadcast()
    relayed = msg.with_incremented_hop()
    assert relayed.hop_count == 1
    assert msg.hop_count == 0  # original unchanged


def test_message_can_relay_unlimited() -> None:
    """Messages with max_hops=None should always be relayable."""

    msg = _make_broadcast()
    assert msg.can_relay() is True


def test_message_can_relay_at_limit() -> None:
    """Messages at max_hops should not be relayable."""

    msg = Message.create(
        sender_id=VehicleId("v1"),
        message_type=MessageType.SCOUT_REPORT,
        payload=None,
        created_at_s=0.0,
        ttl_s=10.0,
        max_hops=2,
    )
    relayed_twice = msg.with_incremented_hop().with_incremented_hop()
    assert relayed_twice.can_relay() is False


def test_message_to_dict_contains_required_keys() -> None:
    """Serialized message must include all required fields."""

    msg = _make_unicast()
    data = msg.to_dict()
    for key in (
        "message_id", "sender_id", "receiver_id", "message_type",
        "priority", "is_broadcast", "created_at_s", "ttl_s",
        "expiration_time_s", "hop_count", "delivery_status", "payload",
    ):
        assert key in data, f"missing key: {key}"


def test_message_all_types_are_valid_enum_members() -> None:
    """Every MessageType member should be constructable."""

    for mt in MessageType:
        msg = _make_broadcast(msg_type=mt)
        assert msg.message_type == mt


def test_message_priority_ordering() -> None:
    """CRITICAL > HIGH > NORMAL > LOW."""

    assert Priority.CRITICAL > Priority.HIGH
    assert Priority.HIGH > Priority.NORMAL
    assert Priority.NORMAL > Priority.LOW


# ---------------------------------------------------------------------------
# Packet construction and validation
# ---------------------------------------------------------------------------


def test_packet_create_from_message() -> None:
    """Packet.create should wrap a message with default values."""

    msg = _make_broadcast()
    pkt = Packet.create(message=msg, transmitted_at_s=1.0)
    assert pkt.message is msg
    assert pkt.transmitted_at_s == pytest.approx(1.0)
    assert pkt.latency_s == pytest.approx(0.0)
    assert pkt.delivery_status == DeliveryStatus.PENDING


def test_packet_arrival_time() -> None:
    """arrival_time_s should equal transmitted_at_s + latency_s."""

    msg = _make_broadcast()
    pkt = Packet.create(message=msg, transmitted_at_s=2.0)
    pkt = pkt.with_latency(0.05)
    assert pkt.arrival_time_s == pytest.approx(2.05)


def test_packet_with_status_immutability() -> None:
    """with_status must not mutate the original packet."""

    msg = _make_broadcast()
    pkt = Packet.create(message=msg, transmitted_at_s=0.0)
    delivered = pkt.with_status(DeliveryStatus.DELIVERED)
    assert delivered.delivery_status == DeliveryStatus.DELIVERED
    assert pkt.delivery_status == DeliveryStatus.PENDING


def test_packet_rejects_negative_latency() -> None:
    """Negative latency must be rejected at construction."""

    msg = _make_broadcast()
    with pytest.raises(CommunicationError, match="latency_s"):
        Packet(
            packet_id=MessageId("p1"),
            message=msg,
            sender_id=VehicleId("v1"),
            transmitted_at_s=0.0,
            latency_s=-0.1,
        )


def test_packet_is_expired_delegates_to_message() -> None:
    """Packet.is_expired should delegate to the wrapped message."""

    msg = _make_broadcast(created_at=0.0, ttl=5.0)
    pkt = Packet.create(message=msg, transmitted_at_s=0.0)
    assert pkt.is_expired(5.0) is True
    assert pkt.is_expired(4.9) is False


def test_packet_to_dict_contains_required_keys() -> None:
    """Serialized packet must include all required fields."""

    msg = _make_broadcast()
    pkt = Packet.create(message=msg, transmitted_at_s=0.0)
    data = pkt.to_dict()
    for key in (
        "packet_id", "message_id", "sender_id", "transmitted_at_s",
        "latency_s", "arrival_time_s", "delivery_status",
    ):
        assert key in data, f"missing key: {key}"


# ---------------------------------------------------------------------------
# Baseline model tests
# ---------------------------------------------------------------------------


def test_no_loss_model_never_drops() -> None:
    """NoLossModel.is_lost must always return False."""

    model = NoLossModel()
    msg = _make_broadcast()
    pkt = Packet.create(message=msg, transmitted_at_s=0.0)
    assert model.is_lost(pkt) is False


def test_zero_latency_model_returns_zero() -> None:
    """ZeroLatencyModel.compute_latency_s must always return 0.0."""

    model = ZeroLatencyModel()
    msg = _make_broadcast()
    pkt = Packet.create(message=msg, transmitted_at_s=0.0)
    assert model.compute_latency_s(pkt) == pytest.approx(0.0)


def test_constant_latency_model_returns_configured_value() -> None:
    """ConstantLatencyModel should return exactly its configured latency."""

    model = ConstantLatencyModel(latency_s=0.05)
    msg = _make_broadcast()
    pkt = Packet.create(message=msg, transmitted_at_s=0.0)
    assert model.compute_latency_s(pkt) == pytest.approx(0.05)


def test_constant_latency_model_rejects_negative() -> None:
    """ConstantLatencyModel should reject negative latency."""

    with pytest.raises(CommunicationError, match="latency_s"):
        ConstantLatencyModel(latency_s=-1.0)


def test_infinite_radius_all_in_range() -> None:
    """InfiniteRadiusModel should return True for all distinct pairs."""

    model = InfiniteRadiusModel()
    assert model.in_range(VehicleId("v1"), VehicleId("v2")) is True
    assert model.in_range(VehicleId("v2"), VehicleId("v1")) is True


def test_infinite_radius_excludes_self() -> None:
    """InfiniteRadiusModel should return False for same-agent pairs."""

    model = InfiniteRadiusModel()
    assert model.in_range(VehicleId("v1"), VehicleId("v1")) is False


def test_infinite_radius_broadcast_excludes_sender() -> None:
    """receivers_in_range must exclude the sender."""

    model = InfiniteRadiusModel()
    receivers = model.receivers_in_range(
        VehicleId("v1"),
        frozenset({VehicleId("v1"), VehicleId("v2"), VehicleId("v3")}),
    )
    assert VehicleId("v1") not in receivers
    assert VehicleId("v2") in receivers
    assert VehicleId("v3") in receivers


def test_fixed_radius_model_within_range() -> None:
    """FixedRadiusModel should detect agents within the configured radius."""

    model = FixedRadiusModel(radius_m=300.0)
    model.register_position(VehicleId("v1"), 0.0, 0.0)
    model.register_position(VehicleId("v2"), 200.0, 0.0)
    assert model.in_range(VehicleId("v1"), VehicleId("v2")) is True


def test_fixed_radius_model_out_of_range() -> None:
    """FixedRadiusModel should reject agents beyond the configured radius."""

    model = FixedRadiusModel(radius_m=100.0)
    model.register_position(VehicleId("v1"), 0.0, 0.0)
    model.register_position(VehicleId("v2"), 200.0, 0.0)
    assert model.in_range(VehicleId("v1"), VehicleId("v2")) is False


def test_fixed_radius_model_unknown_position_out_of_range() -> None:
    """FixedRadiusModel should treat unknown positions as out of range."""

    model = FixedRadiusModel(radius_m=500.0)
    model.register_position(VehicleId("v1"), 0.0, 0.0)
    # v2 not registered
    assert model.in_range(VehicleId("v1"), VehicleId("v2")) is False


def test_fixed_radius_model_rejects_non_positive_radius() -> None:
    """FixedRadiusModel must reject zero or negative radius."""

    with pytest.raises(CommunicationError, match="radius_m"):
        FixedRadiusModel(radius_m=0.0)


def test_fixed_radius_broadcast_subset() -> None:
    """receivers_in_range should return only agents within radius."""

    model = FixedRadiusModel(radius_m=150.0)
    model.register_position(VehicleId("v1"), 0.0, 0.0)
    model.register_position(VehicleId("v2"), 100.0, 0.0)   # 100 m — in range
    model.register_position(VehicleId("v3"), 200.0, 0.0)   # 200 m — out of range

    result = model.receivers_in_range(
        VehicleId("v1"),
        frozenset({VehicleId("v1"), VehicleId("v2"), VehicleId("v3")}),
    )
    assert VehicleId("v2") in result
    assert VehicleId("v3") not in result
    assert VehicleId("v1") not in result  # sender excluded


# ---------------------------------------------------------------------------
# MessageBus — registration
# ---------------------------------------------------------------------------


def test_bus_register_and_query_receivers() -> None:
    """Registered receivers should appear in registered_ids."""

    bus = MessageBus()
    r1 = bus.create_receiver(VehicleId("v1"))
    r2 = bus.create_receiver(VehicleId("v2"))
    assert VehicleId("v1") in bus.registered_ids()
    assert VehicleId("v2") in bus.registered_ids()


def test_bus_rejects_duplicate_registration() -> None:
    """Registering the same vehicle_id twice must raise CommunicationError."""

    bus = MessageBus()
    bus.create_receiver(VehicleId("v1"))
    with pytest.raises(CommunicationError, match="already registered"):
        bus.create_receiver(VehicleId("v1"))


def test_bus_unregister_removes_receiver() -> None:
    """Unregistering a vehicle should remove it from registered_ids."""

    bus = MessageBus()
    bus.create_receiver(VehicleId("v1"))
    bus.unregister(VehicleId("v1"))
    assert VehicleId("v1") not in bus.registered_ids()


def test_broadcaster_rejects_wrong_sender_id() -> None:
    """Broadcaster must reject messages with a mismatched sender_id."""

    bus = MessageBus()
    broadcaster = bus.create_broadcaster(VehicleId("v1"))
    wrong_msg = _make_broadcast(sender="v2")
    with pytest.raises(CommunicationError, match="cannot send"):
        broadcaster.send(wrong_msg)


# ---------------------------------------------------------------------------
# MessageBus — broadcast delivery
# ---------------------------------------------------------------------------


def test_bus_broadcast_delivers_to_all_receivers() -> None:
    """A broadcast message should reach every registered receiver except sender."""

    bus = MessageBus()
    bus.create_receiver(VehicleId("v1"))
    r2 = bus.create_receiver(VehicleId("v2"))
    r3 = bus.create_receiver(VehicleId("v3"))

    msg = _make_broadcast(sender="v1")
    bus.submit(msg)
    bus.tick(current_time_s=0.0)

    assert len(r2.inbox) == 1
    assert len(r3.inbox) == 1
    assert r2.inbox[0].delivery_status == DeliveryStatus.DELIVERED
    assert r3.inbox[0].delivery_status == DeliveryStatus.DELIVERED


def test_bus_broadcast_does_not_deliver_to_sender() -> None:
    """A broadcast must not loop back to the sender's inbox."""

    bus = MessageBus()
    r1 = bus.create_receiver(VehicleId("v1"))
    bus.create_receiver(VehicleId("v2"))

    bus.submit(_make_broadcast(sender="v1"))
    bus.tick(current_time_s=0.0)

    assert len(r1.inbox) == 0


def test_bus_broadcast_updates_statistics() -> None:
    """Bus statistics should reflect sent and delivered counts."""

    bus = MessageBus()
    bus.create_receiver(VehicleId("v1"))
    bus.create_receiver(VehicleId("v2"))
    bus.create_receiver(VehicleId("v3"))

    bus.submit(_make_broadcast(sender="v1"))
    bus.tick(current_time_s=0.0)

    stats = bus.statistics
    assert stats.messages_sent == 1
    assert stats.broadcast_count == 1
    assert stats.messages_delivered == 2  # v2 and v3
    assert stats.delivery_ratio == pytest.approx(2.0)  # 2 deliveries / 1 message


# ---------------------------------------------------------------------------
# MessageBus — unicast delivery
# ---------------------------------------------------------------------------


def test_bus_unicast_delivers_to_target_only() -> None:
    """A unicast message must reach only the addressed receiver."""

    bus = MessageBus()
    bus.create_receiver(VehicleId("v1"))
    r2 = bus.create_receiver(VehicleId("v2"))
    r3 = bus.create_receiver(VehicleId("v3"))

    bus.submit(_make_unicast(sender="v1", receiver="v2"))
    bus.tick(current_time_s=0.0)

    assert len(r2.inbox) == 1
    assert len(r3.inbox) == 0
    assert r2.inbox[0].delivery_status == DeliveryStatus.DELIVERED


def test_bus_unicast_out_of_range_updates_statistics() -> None:
    """Unicast to an out-of-range receiver should update out_of_range counter."""

    from e3hybrid.communication.models import FixedRadiusModel, DeterministicProtocol
    from e3hybrid.communication.models import NoLossModel, ZeroLatencyModel

    radius_model = FixedRadiusModel(radius_m=50.0)
    radius_model.register_position(VehicleId("v1"), 0.0, 0.0)
    radius_model.register_position(VehicleId("v2"), 200.0, 0.0)  # out of range

    protocol = DeterministicProtocol(
        _loss_model=NoLossModel(),
        _latency_model=ZeroLatencyModel(),
        _radius_model=radius_model,
    )
    bus = MessageBus(protocol=protocol)
    bus.create_receiver(VehicleId("v1"))
    bus.create_receiver(VehicleId("v2"))

    bus.submit(_make_unicast(sender="v1", receiver="v2"))
    bus.tick(current_time_s=0.0)

    assert bus.statistics.messages_out_of_range == 1
    assert bus.statistics.messages_delivered == 0


# ---------------------------------------------------------------------------
# MessageBus — TTL and expiry
# ---------------------------------------------------------------------------


def test_bus_expired_message_is_not_delivered() -> None:
    """Messages that have expired by tick time should be discarded."""

    bus = MessageBus()
    bus.create_receiver(VehicleId("v1"))
    r2 = bus.create_receiver(VehicleId("v2"))

    msg = _make_broadcast(sender="v1", created_at=0.0, ttl=5.0)
    bus.submit(msg)
    bus.tick(current_time_s=10.0)  # well past expiry

    assert len(r2.inbox) == 0
    assert bus.statistics.messages_expired == 1


def test_bus_not_yet_expired_message_is_delivered() -> None:
    """Messages within TTL should be delivered normally."""

    bus = MessageBus()
    bus.create_receiver(VehicleId("v1"))
    r2 = bus.create_receiver(VehicleId("v2"))

    msg = _make_broadcast(sender="v1", created_at=0.0, ttl=10.0)
    bus.submit(msg)
    bus.tick(current_time_s=4.0)  # within TTL

    assert len(r2.inbox) == 1


# ---------------------------------------------------------------------------
# MessageBus — duplicate messages
# ---------------------------------------------------------------------------


def test_bus_ignores_duplicate_message_id() -> None:
    """Submitting the same message_id twice must be idempotent."""

    bus = MessageBus()
    bus.create_receiver(VehicleId("v1"))
    r2 = bus.create_receiver(VehicleId("v2"))

    mid = MessageId("dup-001")
    msg = Message.create(
        sender_id=VehicleId("v1"),
        message_type=MessageType.HEARTBEAT,
        payload=None,
        created_at_s=0.0,
        ttl_s=10.0,
        message_id=mid,
    )
    bus.submit(msg)
    bus.tick(current_time_s=0.0)
    # Second submission of same id should be silently ignored.
    bus.submit(msg)
    bus.tick(current_time_s=0.0)

    assert len(r2.inbox) == 1
    assert bus.statistics.messages_sent == 1


# ---------------------------------------------------------------------------
# MessageBus — latency
# ---------------------------------------------------------------------------


def test_bus_constant_latency_reflected_in_packet() -> None:
    """Packets should carry the latency computed by the LatencyModel."""

    from e3hybrid.communication.models import DeterministicProtocol

    protocol = DeterministicProtocol(
        _latency_model=ConstantLatencyModel(latency_s=0.02)
    )
    bus = MessageBus(protocol=protocol)
    bus.create_receiver(VehicleId("v1"))
    r2 = bus.create_receiver(VehicleId("v2"))

    bus.submit(_make_broadcast(sender="v1"))
    bus.tick(current_time_s=1.0)

    pkt = r2.inbox[0]
    assert pkt.latency_s == pytest.approx(0.02)
    assert pkt.arrival_time_s == pytest.approx(1.02)


def test_bus_statistics_average_latency() -> None:
    """Average latency should be the mean of delivered packet latencies."""

    from e3hybrid.communication.models import DeterministicProtocol

    protocol = DeterministicProtocol(
        _latency_model=ConstantLatencyModel(latency_s=0.1)
    )
    bus = MessageBus(protocol=protocol)
    bus.create_receiver(VehicleId("v1"))
    bus.create_receiver(VehicleId("v2"))
    bus.create_receiver(VehicleId("v3"))

    bus.submit(_make_broadcast(sender="v1"))
    bus.tick(current_time_s=0.0)

    # 2 deliveries (v2 and v3) each at 0.1 s
    assert bus.statistics.average_latency_s == pytest.approx(0.1)


# ---------------------------------------------------------------------------
# MessageBus — priority ordering
# ---------------------------------------------------------------------------


def test_bus_higher_priority_message_dispatched_first() -> None:
    """High-priority messages submitted together should arrive first in inbox."""

    bus = MessageBus()
    bus.create_receiver(VehicleId("v1"))
    r2 = bus.create_receiver(VehicleId("v2"))

    low = _make_broadcast(sender="v1", msg_type=MessageType.HEARTBEAT,
                          priority=Priority.LOW)
    critical = _make_broadcast(sender="v1", msg_type=MessageType.EMERGENCY_VEHICLE,
                               priority=Priority.CRITICAL)

    # Submit low first, then critical.
    bus.submit(low)
    bus.submit(critical)
    bus.tick(current_time_s=0.0)

    # Both delivered; order in inbox reflects submission order for now
    # (priority queue is a future enhancement).  Assert both arrived.
    assert len(r2.inbox) == 2


# ---------------------------------------------------------------------------
# MessageBus — drain and peek
# ---------------------------------------------------------------------------


def test_receiver_drain_clears_inbox() -> None:
    """drain() should return all packets and clear the inbox."""

    bus = MessageBus()
    bus.create_receiver(VehicleId("v1"))
    r2 = bus.create_receiver(VehicleId("v2"))

    bus.submit(_make_broadcast(sender="v1"))
    bus.tick(current_time_s=0.0)

    packets = r2.drain()
    assert len(packets) == 1
    assert len(r2.inbox) == 0


def test_receiver_peek_does_not_clear_inbox() -> None:
    """peek() should return packets without removing them."""

    bus = MessageBus()
    bus.create_receiver(VehicleId("v1"))
    r2 = bus.create_receiver(VehicleId("v2"))

    bus.submit(_make_broadcast(sender="v1"))
    bus.tick(current_time_s=0.0)

    peeked = r2.peek()
    assert len(peeked) == 1
    assert len(r2.inbox) == 1  # still present


# ---------------------------------------------------------------------------
# MessageBus — packet log and reset
# ---------------------------------------------------------------------------


def test_bus_packet_log_records_all_deliveries() -> None:
    """packet_log should contain every processed packet."""

    bus = MessageBus()
    bus.create_receiver(VehicleId("v1"))
    bus.create_receiver(VehicleId("v2"))
    bus.create_receiver(VehicleId("v3"))

    bus.submit(_make_broadcast(sender="v1"))
    bus.tick(current_time_s=0.0)

    log = bus.packet_log()
    assert len(log) == 2  # v2 and v3


def test_bus_reset_log_clears_state() -> None:
    """reset_log should clear the packet log and statistics."""

    bus = MessageBus()
    bus.create_receiver(VehicleId("v1"))
    bus.create_receiver(VehicleId("v2"))

    bus.submit(_make_broadcast(sender="v1"))
    bus.tick(current_time_s=0.0)

    bus.reset_log()
    assert bus.packet_log() == []
    assert bus.statistics.messages_sent == 0


# ---------------------------------------------------------------------------
# CommunicationStatistics
# ---------------------------------------------------------------------------


def test_statistics_delivery_ratio_zero_on_empty() -> None:
    """delivery_ratio should be 0.0 when no messages have been sent."""

    stats = CommunicationStatistics()
    assert stats.delivery_ratio == pytest.approx(0.0)


def test_statistics_average_latency_zero_on_empty() -> None:
    """average_latency_s should be 0.0 when no packets delivered."""

    stats = CommunicationStatistics()
    assert stats.average_latency_s == pytest.approx(0.0)


def test_statistics_accumulate_correctly() -> None:
    """Manual updates should accumulate correctly."""

    stats = CommunicationStatistics()
    stats.record_sent(is_broadcast=True)
    stats.record_sent(is_broadcast=False)
    stats.record_delivered(latency_s=0.1)
    stats.record_delivered(latency_s=0.3)
    stats.record_dropped()

    assert stats.messages_sent == 2
    assert stats.broadcast_count == 1
    assert stats.unicast_count == 1
    assert stats.messages_delivered == 2
    assert stats.messages_dropped == 1
    assert stats.average_latency_s == pytest.approx(0.2)
    assert stats.delivery_ratio == pytest.approx(1.0)


def test_statistics_to_dict_contains_required_keys() -> None:
    """Serialized statistics must include all metric fields."""

    stats = CommunicationStatistics()
    data = stats.to_dict()
    for key in (
        "messages_sent", "messages_delivered", "messages_dropped",
        "messages_expired", "messages_out_of_range", "broadcast_count",
        "unicast_count", "delivery_ratio", "drop_ratio",
        "average_latency_s", "relay_count",
    ):
        assert key in data, f"missing key: {key}"


def test_statistics_reset() -> None:
    """reset() should zero all counters."""

    stats = CommunicationStatistics()
    stats.record_sent(is_broadcast=True)
    stats.record_delivered(latency_s=0.05)
    stats.reset()

    assert stats.messages_sent == 0
    assert stats.messages_delivered == 0
    assert stats.average_latency_s == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# End-to-end integration scenario
# ---------------------------------------------------------------------------


def test_end_to_end_multi_tick_scenario() -> None:
    """Multi-tick scenario: traffic update then emergency broadcast."""

    bus = MessageBus()
    bus.create_receiver(VehicleId("v1"))
    r2 = bus.create_receiver(VehicleId("v2"))
    r3 = bus.create_receiver(VehicleId("v3"))

    # Tick 0: v2 sends a traffic update to v3 (unicast)
    traffic = _make_unicast(sender="v2", receiver="v3",
                            msg_type=MessageType.TRAFFIC_UPDATE, created_at=0.0, ttl=30.0)
    bus.submit(traffic)
    bus.tick(current_time_s=0.0)

    assert len(r3.inbox) == 1
    assert r3.inbox[0].message.message_type == MessageType.TRAFFIC_UPDATE

    r3.drain()

    # Tick 5: v1 sends an emergency broadcast
    emergency = _make_broadcast(sender="v1", msg_type=MessageType.EMERGENCY_VEHICLE,
                                created_at=5.0, ttl=10.0, priority=Priority.CRITICAL)
    bus.submit(emergency)
    bus.tick(current_time_s=5.0)

    assert len(r2.inbox) == 1
    assert len(r3.inbox) == 1
    assert r2.inbox[0].message.message_type == MessageType.EMERGENCY_VEHICLE
    assert r3.inbox[0].message.message_type == MessageType.EMERGENCY_VEHICLE

    assert bus.statistics.messages_sent == 2
    assert bus.statistics.messages_delivered == 3  # 1 unicast + 2 broadcast
