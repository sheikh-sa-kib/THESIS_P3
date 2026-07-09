"""Tests for required research documentation scaffold."""

from pathlib import Path


def test_required_research_docs_exist() -> None:
    """The approved research documentation files should be present."""

    docs_dir = Path("docs")
    required_docs = {
        "architecture.md",
        "design_decisions.md",
        "algorithm_notes.md",
        "literature_mapping.md",
        "assumptions.md",
        "experiment_protocol.md",
        "api_reference.md",
        "development_log.md",
        "energy_model_design.md",
        "communication_architecture.md",
        "emergency_framework_design.md",
        "decision_engine_design.md",
    }

    missing_docs = [
        doc_name
        for doc_name in required_docs
        if not (docs_dir / doc_name).is_file()
    ]

    assert not missing_docs
