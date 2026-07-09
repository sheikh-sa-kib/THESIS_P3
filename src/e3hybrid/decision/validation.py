"""Decision validation logic.

Validates Decision objects before they are logged or executed.
Ensures all mandatory fields are present and valid.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from e3hybrid.decision.decision import Decision


@dataclass(frozen=True, slots=True)
class DecisionValidationError:
    """A single validation error for a Decision."""

    field_name: str
    error_message: str


@dataclass(frozen=True, slots=True)
class DecisionValidationReport:
    """Report of validation errors for a Decision."""

    is_valid: bool
    errors: tuple[DecisionValidationError, ...]

    def __str__(self) -> str:
        if self.is_valid:
            return "Decision is valid"
        error_lines = [f"  - {e.field_name}: {e.error_message}" for e in self.errors]
        return "Decision validation failed:\n" + "\n".join(error_lines)


class DecisionValidator:
    """Validates Decision objects."""

    def validate(self, decision: Decision) -> DecisionValidationReport:
        """Validate a Decision object.

        Parameters
        ----------
        decision:
            The Decision to validate.

        Returns
        -------
        DecisionValidationReport
            Validation report containing any errors found.
        """
        errors: list[DecisionValidationError] = []

        # Validate decision_id.
        if not decision.decision_id:
            errors.append(
                DecisionValidationError(
                    field_name="decision_id",
                    error_message="decision_id must be non-empty",
                )
            )

        # Validate vehicle_id.
        if not decision.vehicle_id:
            errors.append(
                DecisionValidationError(
                    field_name="vehicle_id",
                    error_message="vehicle_id must be non-empty",
                )
            )

        # Validate sim_time_s.
        if decision.sim_time_s < 0:
            errors.append(
                DecisionValidationError(
                    field_name="sim_time_s",
                    error_message="sim_time_s must be non-negative",
                )
            )

        # Validate decision_type.
        if not decision.decision_type:
            errors.append(
                DecisionValidationError(
                    field_name="decision_type",
                    error_message="decision_type must be non-empty",
                )
            )

        # Validate trigger.
        if not decision.trigger or not decision.trigger.strip():
            errors.append(
                DecisionValidationError(
                    field_name="trigger",
                    error_message="trigger must be non-empty",
                )
            )

        # Validate explanation.
        if not decision.explanation or not decision.explanation.strip():
            errors.append(
                DecisionValidationError(
                    field_name="explanation",
                    error_message="explanation must be non-empty",
                )
            )

        # Validate winning_policy.
        if not decision.winning_policy or not decision.winning_policy.strip():
            errors.append(
                DecisionValidationError(
                    field_name="winning_policy",
                    error_message="winning_policy must be non-empty",
                )
            )

        # Validate applied_policies.
        if not decision.applied_policies:
            errors.append(
                DecisionValidationError(
                    field_name="applied_policies",
                    error_message="applied_policies must contain at least one policy",
                )
            )

        # Validate confidence.
        if not (0.0 <= decision.confidence <= 1.0):
            errors.append(
                DecisionValidationError(
                    field_name="confidence",
                    error_message="confidence must be in [0.0, 1.0]",
                )
            )

        # Validate veto consistency.
        if decision.veto and decision.confidence < 1.0:
            errors.append(
                DecisionValidationError(
                    field_name="veto",
                    error_message="veto decisions must have confidence=1.0",
                )
            )

        # Validate that winning_policy is in applied_policies.
        if decision.winning_policy not in decision.applied_policies:
            errors.append(
                DecisionValidationError(
                    field_name="winning_policy",
                    error_message=(
                        f"winning_policy '{decision.winning_policy}' "
                        f"must be in applied_policies {decision.applied_policies}"
                    ),
                )
            )

        # Validate all_recommendations consistency.
        if decision.all_recommendations:
            recommendation_policies = {
                r.policy_name for r in decision.all_recommendations
            }
            applied_set = set(decision.applied_policies)
            if recommendation_policies != applied_set:
                errors.append(
                    DecisionValidationError(
                        field_name="all_recommendations",
                        error_message=(
                            f"all_recommendations policy names "
                            f"{recommendation_policies} must match "
                            f"applied_policies {applied_set}"
                        ),
                    )
                )

        return DecisionValidationReport(
            is_valid=len(errors) == 0,
            errors=tuple(errors),
        )
