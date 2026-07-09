"""Unit tests for reproducibility helpers."""

from pathlib import Path

import pytest

from e3hybrid.utils.reproducibility import (
    SeededRandomFactory,
    collect_environment_metadata,
)


def test_seeded_random_factory_repeats_named_streams() -> None:
    """The same base seed and stream name should produce the same sequence."""

    first_factory = SeededRandomFactory(123)
    second_factory = SeededRandomFactory(123)

    first_stream = first_factory.create("routing")
    second_stream = second_factory.create("routing")

    assert [first_stream.random() for _ in range(3)] == [
        second_stream.random() for _ in range(3)
    ]


def test_seeded_random_factory_separates_named_streams() -> None:
    """Different stream names should produce independent deterministic streams."""

    factory = SeededRandomFactory(123)
    routing_stream = factory.create("routing")
    communication_stream = factory.create("communication")

    assert [routing_stream.random() for _ in range(3)] != [
        communication_stream.random() for _ in range(3)
    ]


def test_environment_metadata_contains_required_research_fields() -> None:
    """Collected metadata should include fields required for reproducibility."""

    metadata = collect_environment_metadata(Path("."), random_seed=99)

    assert metadata.python_version
    assert metadata.operating_system
    assert metadata.architecture
    assert metadata.installed_packages
    assert metadata.timestamp_utc
    assert metadata.random_seed == 99


def test_environment_metadata_rejects_negative_seed() -> None:
    """Metadata collection should reject invalid random seeds."""

    with pytest.raises(ValueError, match="random_seed"):
        collect_environment_metadata(Path("."), random_seed=-1)
