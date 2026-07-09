"""Unit tests for DecisionEngine."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock

from e3hybrid.decision.aggregation import DecisionAggregationPolicy
from e3hybrid.decision.config import DecisionConfig
from e3hybrid.decision.decision import Decision
from e3hybrid.decision.decision_log import DecisionLog
from e3hybrid.decision.engine import DecisionEngine, DecisionEngineConfig
from e3hybrid.decision.observation import VehicleObservation
from e3hybrid.decision.observation_assembler import ObservationAssembler
from e3hybrid.decision.policy import DecisionPolicy, PolicyRecommendation
from e3hybrid.decision.policy_registry import PolicyManager, PolicyRegistry
from e3hybrid.decision.types import DecisionType
from e3hybrid.decision.validation import DecisionValidator
from e3hybrid.vehicle.types import VehicleId


class MockPolicy(DecisionPolicy):
    """Mock policy for testing."""

    def __init__(self, name: str, enabled: bool = True, recommendation: PolicyRecommendation | None = None):
        self._name = name
        self._enabled = enabled
        self._recommendation = recommendation or PolicyRecommendation(
            decision_type=DecisionType.KEEP_CURRENT_ROUTE,
            priority=50,
            confidence=1.0,
            explanation="Mock recommendation",
            policy_name=name,
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def enabled(self) -> bool:
        return self._enabled

    def evaluate(self, observation: VehicleObservation) -> PolicyRecommendation:
        return self._recommendation


def test_decision_engine_config_creation():
    """Test DecisionEngineConfig creation."""
    config = DecisionConfig.default()
    engine_config = DecisionEngineConfig(
        config=config,
        enable_validation=True,
        enable_logging=True,
    )
    assert engine_config.config == config
    assert engine_config.enable_validation is True
    assert engine_config.enable_logging is True


def test_decision_engine_initialization():
    """Test DecisionEngine initialization."""
    config = DecisionConfig.default()
    engine_config = DecisionEngineConfig(config=config)

    registry = PolicyRegistry()
    registry.register("mock", lambda cfg: MockPolicy("mock"))

    policy_manager = PolicyManager(config, registry)
    observation_assembler = Mock(spec=ObservationAssembler)
    decision_log = Mock(spec=DecisionLog)
    validator = DecisionValidator()

    engine = DecisionEngine(
        config=engine_config,
        policy_manager=policy_manager,
        observation_assembler=observation_assembler,
        decision_log=decision_log,
        validator=validator,
    )

    assert engine._config == engine_config
    assert engine._policy_manager == policy_manager
    assert engine._observation_assembler == observation_assembler
    assert engine._decision_log == decision_log
    assert engine._validator == validator


def test_decision_engine_evaluate_with_no_policies():
    """Test evaluation when no policies are enabled."""
    config = DecisionConfig.default()
    engine_config = DecisionEngineConfig(config=config)

    registry = PolicyRegistry()
    policy_manager = PolicyManager(config, registry)
    observation_assembler = Mock(spec=ObservationAssembler)
    decision_log = Mock(spec=DecisionLog)

    engine = DecisionEngine(
        config=engine_config,
        policy_manager=policy_manager,
        observation_assembler=observation_assembler,
        decision_log=decision_log,
    )

    observation = Mock(spec=VehicleObservation)
    observation.vehicle_id = VehicleId("v1")
    observation.sim_time_s = 10.0

    decision = engine.evaluate(observation)

    assert decision.decision_type == DecisionType.KEEP_CURRENT_ROUTE
    assert decision.winning_policy == "fallback"
    assert decision.veto is False


def test_decision_engine_evaluate_with_policies():
    """Test evaluation with enabled policies."""
    config = DecisionConfig.default()
    engine_config = DecisionEngineConfig(config=config)

    registry = PolicyRegistry()
    registry.register("policy1", lambda cfg: MockPolicy("policy1", True))
    registry.register("policy2", lambda cfg: MockPolicy("policy2", True))

    policy_manager = PolicyManager(config, registry)
    observation_assembler = Mock(spec=ObservationAssembler)
    decision_log = Mock(spec=DecisionLog)

    engine = DecisionEngine(
        config=engine_config,
        policy_manager=policy_manager,
        observation_assembler=observation_assembler,
        decision_log=decision_log,
    )

    observation = Mock(spec=VehicleObservation)
    observation.vehicle_id = VehicleId("v1")
    observation.sim_time_s = 10.0

    decision = engine.evaluate(observation)

    assert decision.decision_type == DecisionType.KEEP_CURRENT_ROUTE
    assert decision.vehicle_id == VehicleId("v1")
    assert decision.sim_time_s == 10.0
    assert len(decision.applied_policies) == 2


def test_decision_engine_veto_handling():
    """Test that veto recommendations are handled correctly."""
    config = DecisionConfig.default()
    engine_config = DecisionEngineConfig(config=config)

    veto_recommendation = PolicyRecommendation(
        decision_type=DecisionType.EMERGENCY_STOP,
        priority=100,
        confidence=1.0,
        explanation="Emergency stop required",
        policy_name="safety",
        veto=True,
    )

    registry = PolicyRegistry()
    registry.register("safety", lambda cfg: MockPolicy("safety", True, veto_recommendation))

    policy_manager = PolicyManager(config, registry)
    observation_assembler = Mock(spec=ObservationAssembler)
    decision_log = Mock(spec=DecisionLog)

    engine = DecisionEngine(
        config=engine_config,
        policy_manager=policy_manager,
        observation_assembler=observation_assembler,
        decision_log=decision_log,
    )

    observation = Mock(spec=VehicleObservation)
    observation.vehicle_id = VehicleId("v1")
    observation.sim_time_s = 10.0

    decision = engine.evaluate(observation)

    assert decision.decision_type == DecisionType.EMERGENCY_STOP
    assert decision.veto is True
    assert decision.winning_policy == "safety"


def test_decision_engine_logging():
    """Test that decisions are logged when logging is enabled."""
    config = DecisionConfig.default()
    engine_config = DecisionEngineConfig(config=config, enable_logging=True)

    registry = PolicyRegistry()
    registry.register("mock", lambda cfg: MockPolicy("mock", True))

    policy_manager = PolicyManager(config, registry)
    observation_assembler = Mock(spec=ObservationAssembler)
    decision_log = Mock(spec=DecisionLog)

    engine = DecisionEngine(
        config=engine_config,
        policy_manager=policy_manager,
        observation_assembler=observation_assembler,
        decision_log=decision_log,
    )

    observation = Mock(spec=VehicleObservation)
    observation.vehicle_id = VehicleId("v1")
    observation.sim_time_s = 10.0

    engine.evaluate(observation)

    decision_log.log.assert_called_once()


def test_decision_engine_validation_failure():
    """Test that validation failures raise errors."""
    config = DecisionConfig.default()
    engine_config = DecisionEngineConfig(config=config, enable_validation=True)

    registry = PolicyRegistry()
    registry.register("mock", lambda cfg: MockPolicy("mock", True))

    policy_manager = PolicyManager(config, registry)
    observation_assembler = Mock(spec=ObservationAssembler)
    decision_log = Mock(spec=DecisionLog)

    # Mock validator to always fail
    validator = Mock(spec=DecisionValidator)
    validator.validate.return_value = Mock(is_valid=False, errors=())

    engine = DecisionEngine(
        config=engine_config,
        policy_manager=policy_manager,
        observation_assembler=observation_assembler,
        decision_log=decision_log,
        validator=validator,
    )

    observation = Mock(spec=VehicleObservation)
    observation.vehicle_id = VehicleId("v1")
    observation.sim_time_s = 10.0

    with pytest.raises(Exception):  # DecisionError
        engine.evaluate(observation)


def test_decision_engine_get_policy_names():
    """Test getting enabled and available policy names."""
    config = DecisionConfig.default()
    engine_config = DecisionEngineConfig(config=config)

    registry = PolicyRegistry()
    registry.register("policy1", lambda cfg: MockPolicy("policy1", True))
    registry.register("policy2", lambda cfg: MockPolicy("policy2", False))

    policy_manager = PolicyManager(config, registry)
    observation_assembler = Mock(spec=ObservationAssembler)

    engine = DecisionEngine(
        config=engine_config,
        policy_manager=policy_manager,
        observation_assembler=observation_assembler,
    )

    available = engine.get_available_policy_names()
    enabled = engine.get_enabled_policy_names()

    assert "policy1" in available
    assert "policy2" in available
    assert "policy1" in enabled
    assert "policy2" not in enabled
