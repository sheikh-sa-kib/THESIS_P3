"""Unit tests for PolicyRegistry and PolicyManager."""

from __future__ import annotations

import pytest

from e3hybrid.decision.config import DecisionConfig
from e3hybrid.decision.observation import VehicleObservation
from e3hybrid.decision.policy import DecisionPolicy, PolicyRecommendation
from e3hybrid.decision.policy_registry import (
    PolicyFactory,
    PolicyManager,
    PolicyRegistry,
    get_global_registry,
    register_policy,
)
from e3hybrid.decision.types import DecisionType


class MockPolicy(DecisionPolicy):
    """Mock policy for testing."""

    def __init__(self, name: str, enabled: bool = True):
        self._name = name
        self._enabled = enabled

    @property
    def name(self) -> str:
        return self._name

    @property
    def enabled(self) -> bool:
        return self._enabled

    def evaluate(self, observation: VehicleObservation) -> PolicyRecommendation:
        return PolicyRecommendation(
            decision_type=DecisionType.KEEP_CURRENT_ROUTE,
            priority=50,
            confidence=1.0,
            explanation="Mock recommendation",
            policy_name=self._name,
        )


def mock_factory(config: DecisionConfig) -> DecisionPolicy:
    """Mock policy factory."""
    return MockPolicy("mock")


def test_policy_registry_register():
    """Test registering a policy factory."""
    registry = PolicyRegistry()
    registry.register("mock", mock_factory)
    
    assert registry.is_registered("mock") is True
    assert "mock" in registry.list_registered()


def test_policy_registry_duplicate_registration():
    """Test that duplicate registration raises an error."""
    registry = PolicyRegistry()
    registry.register("mock", mock_factory)
    
    with pytest.raises(ValueError, match="already registered"):
        registry.register("mock", mock_factory)


def test_policy_registry_get_factory():
    """Test getting a registered factory."""
    registry = PolicyRegistry()
    registry.register("mock", mock_factory)
    
    factory = registry.get_factory("mock")
    assert factory == mock_factory


def test_policy_registry_get_factory_not_registered():
    """Test getting a non-registered factory raises KeyError."""
    registry = PolicyRegistry()
    
    with pytest.raises(KeyError, match="not registered"):
        registry.get_factory("nonexistent")


def test_policy_registry_list_registered():
    """Test listing registered policies."""
    registry = PolicyRegistry()
    registry.register("policy1", mock_factory)
    registry.register("policy2", mock_factory)
    
    registered = registry.list_registered()
    assert "policy1" in registered
    assert "policy2" in registered
    assert len(registered) == 2


def test_global_registry():
    """Test global registry functions."""
    global_reg = get_global_registry()
    
    # Register a policy
    register_policy("global_mock", mock_factory)
    
    assert global_reg.is_registered("global_mock") is True


def test_policy_manager_initialization():
    """Test PolicyManager initialization."""
    config = DecisionConfig.default()
    registry = PolicyRegistry()
    registry.register("mock", mock_factory)
    
    manager = PolicyManager(config, registry)
    
    assert "mock" in manager.list_available()


def test_policy_manager_get_enabled_policies():
    """Test getting enabled policies."""
    config = DecisionConfig.default()
    registry = PolicyRegistry()
    registry.register("enabled", lambda cfg: MockPolicy("enabled", True))
    registry.register("disabled", lambda cfg: MockPolicy("disabled", False))
    
    manager = PolicyManager(config, registry)
    
    enabled = manager.get_enabled_policies()
    assert len(enabled) == 1
    assert enabled[0].name == "enabled"


def test_policy_manager_get_policy():
    """Test getting a specific policy."""
    config = DecisionConfig.default()
    registry = PolicyRegistry()
    registry.register("mock", mock_factory)
    
    manager = PolicyManager(config, registry)
    
    policy = manager.get_policy("mock")
    assert policy.name == "mock"


def test_policy_manager_get_policy_not_found():
    """Test getting a non-existent policy raises KeyError."""
    config = DecisionConfig.default()
    registry = PolicyRegistry()
    registry.register("mock", mock_factory)
    
    manager = PolicyManager(config, registry)
    
    with pytest.raises(KeyError, match="not instantiated"):
        manager.get_policy("nonexistent")


def test_policy_manager_list_available():
    """Test listing available policies."""
    config = DecisionConfig.default()
    registry = PolicyRegistry()
    registry.register("policy1", mock_factory)
    registry.register("policy2", mock_factory)
    
    manager = PolicyManager(config, registry)
    
    available = manager.list_available()
    assert "policy1" in available
    assert "policy2" in available


def test_policy_manager_list_enabled():
    """Test listing enabled policies."""
    config = DecisionConfig.default()
    registry = PolicyRegistry()
    registry.register("enabled", lambda cfg: MockPolicy("enabled", True))
    registry.register("disabled", lambda cfg: MockPolicy("disabled", False))
    
    manager = PolicyManager(config, registry)
    
    enabled = manager.list_enabled()
    assert "enabled" in enabled
    assert "disabled" not in enabled
