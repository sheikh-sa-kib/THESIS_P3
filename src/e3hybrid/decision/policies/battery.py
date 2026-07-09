"""BatteryPolicy — protect against SoC violations.

Priority ordering within this policy:
1. Emergency stop (SoC = 0)   → veto, priority 95
2. Wait (SoC ≤ wait_threshold) → veto, priority 95
3. Reduce speed (SoC ≤ conservation_threshold) → non-veto, priority 70
4. Keep current route          → non-veto, priority 70
"""

from __future__ import annotations

from e3hybrid.decision.config import DecisionConfig
from e3hybrid.decision.observation import VehicleObservation
from e3hybrid.decision.policy import PolicyRecommendation
from e3hybrid.decision.types import DecisionType


class BatteryPolicy:
    """Guard SoC boundaries — priority 70–95 depending on severity."""

    name: str = "battery"

    def __init__(self, config: DecisionConfig) -> None:
        self._config = config

    @property
    def enabled(self) -> bool:
        return self._config.battery.enabled

    def evaluate(self, observation: VehicleObservation) -> PolicyRecommendation:
        """Check SoC against configured thresholds."""

        cfg = self._config.battery
        soc = observation.battery.soc_kwh
        capacity = observation.battery.capacity_kwh
        min_soc = observation.constraints.min_soc_kwh
        soc_fraction = observation.battery.soc_fraction

        # Hard: battery at zero.
        if soc <= capacity * cfg.emergency_stop_threshold_fraction and soc == 0.0:
            return PolicyRecommendation(
                decision_type=DecisionType.EMERGENCY_STOP,
                priority=95,
                confidence=1.0,
                explanation=(
                    f"Battery depleted (soc={soc:.3f} kWh). "
                    f"Emergency stop required."
                ),
                policy_name=self.name,
                veto=True,
            )

        # Hard: SoC at or below minimum operational threshold.
        if soc <= min_soc:
            return PolicyRecommendation(
                decision_type=DecisionType.WAIT,
                priority=95,
                confidence=1.0,
                explanation=(
                    f"SoC {soc:.2f} kWh is at or below minimum "
                    f"{min_soc:.2f} kWh. Vehicle cannot depart."
                ),
                policy_name=self.name,
                veto=True,
                payload={"reason": "battery_below_minimum", "duration_s": None},
            )

        # Soft: SoC in conservation zone.
        if soc_fraction <= cfg.conservation_threshold_fraction:
            return PolicyRecommendation(
                decision_type=DecisionType.REDUCE_SPEED,
                priority=70,
                confidence=0.8,
                explanation=(
                    f"SoC {soc_fraction:.1%} is below conservation threshold "
                    f"({cfg.conservation_threshold_fraction:.0%}). "
                    f"Reducing speed to preserve battery."
                ),
                policy_name=self.name,
                veto=False,
                payload={
                    "target_speed_mps": observation.constraints.max_speed_mps * 0.7,
                    "reason": "battery_conservation",
                },
            )

        return PolicyRecommendation(
            decision_type=DecisionType.KEEP_CURRENT_ROUTE,
            priority=70,
            confidence=1.0,
            explanation=(
                f"Battery SoC {soc:.2f} kWh ({soc_fraction:.1%}) "
                f"is within operational range."
            ),
            policy_name=self.name,
            veto=False,
        )
