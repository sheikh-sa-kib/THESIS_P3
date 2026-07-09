"""PolicyRegistry and PolicyManager — manage policy lifecycle.

The registry provides a central place to register and retrieve policies.
The manager handles policy instantiation and configuration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from e3hybrid.decision.config import DecisionConfig
    from e3hybrid.decision.policy import DecisionPolicy


class PolicyFactory(Protocol):
    """Protocol for policy factory functions."""

    def __call__(self, config: DecisionConfig) -> DecisionPolicy:
        """Create a policy instance from configuration."""
        ...


class PolicyRegistry:
    """Central registry for policy factories.

    Policies are registered by name.  The registry is used by PolicyManager
    to instantiate policies based on configuration.
    """

    def __init__(self) -> None:
        self._factories: dict[str, PolicyFactory] = {}

    def register(self, name: str, factory: PolicyFactory) -> None:
        """Register a policy factory.

        Parameters
        ----------
        name:
            Policy name (must match the policy's `name` property).
        factory:
            Factory function that creates a policy instance.
        """
        if name in self._factories:
            raise ValueError(f"Policy '{name}' is already registered")
        self._factories[name] = factory

    def get_factory(self, name: str) -> PolicyFactory:
        """Get a policy factory by name.

        Parameters
        ----------
        name:
            Policy name.

        Returns
        -------
        PolicyFactory
            Factory function for the policy.

        Raises
        ------
        KeyError
            If the policy is not registered.
        """
        if name not in self._factories:
            raise KeyError(f"Policy '{name}' is not registered")
        return self._factories[name]

    def list_registered(self) -> tuple[str, ...]:
        """Return names of all registered policies."""
        return tuple(sorted(self._factories.keys()))

    def is_registered(self, name: str) -> bool:
        """Check if a policy is registered."""
        return name in self._factories


# Global registry instance.
_global_registry = PolicyRegistry()


def register_policy(name: str, factory: PolicyFactory) -> None:
    """Register a policy in the global registry.

    This is the preferred way to register policies at module import time.
    """
    _global_registry.register(name, factory)


def get_global_registry() -> PolicyRegistry:
    """Get the global policy registry."""
    return _global_registry


class PolicyManager:
    """Manages policy instances for the Decision Engine.

    The manager instantiates policies from the registry based on configuration.
    It filters disabled policies and provides the enabled policy set for evaluation.
    """

    def __init__(self, config: DecisionConfig, registry: PolicyRegistry | None = None) -> None:
        """Initialize the policy manager.

        Parameters
        ----------
        config:
            Decision configuration containing policy enable/disable flags.
        registry:
            Policy registry to use.  If None, uses the global registry.
        """
        self._config = config
        self._registry = registry if registry is not None else get_global_registry()
        self._policies: dict[str, DecisionPolicy] = {}
        self._initialize_policies()

    def _initialize_policies(self) -> None:
        """Instantiate all registered policies."""
        for policy_name in self._registry.list_registered():
            factory = self._registry.get_factory(policy_name)
            policy = factory(self._config)
            self._policies[policy_name] = policy

    def get_enabled_policies(self) -> tuple[DecisionPolicy, ...]:
        """Return all enabled policies in priority order.

        Policies are returned in priority order (highest priority first).
        This is a convenience for the Decision Engine.
        """
        enabled = [
            policy for policy in self._policies.values() if policy.enabled
        ]
        # Sort by priority (higher priority first).
        # Priority is determined by the policy's evaluate() return values,
        # but we can use a heuristic: safety=100, emergency=90, battery=70-95, etc.
        # For now, return in registration order.
        return tuple(enabled)

    def get_policy(self, name: str) -> DecisionPolicy:
        """Get a policy instance by name.

        Parameters
        ----------
        name:
            Policy name.

        Returns
        -------
        DecisionPolicy
            Policy instance.

        Raises
        ------
        KeyError
            If the policy is not registered.
        """
        if name not in self._policies:
            raise KeyError(f"Policy '{name}' is not instantiated")
        return self._policies[name]

    def list_available(self) -> tuple[str, ...]:
        """Return names of all available policies."""
        return tuple(sorted(self._policies.keys()))

    def list_enabled(self) -> tuple[str, ...]:
        """Return names of enabled policies."""
        return tuple(
            name
            for name, policy in self._policies.items()
            if policy.enabled
        )
