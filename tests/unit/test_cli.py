"""Unit tests for command-line entry points."""

from pathlib import Path

import pytest

from e3hybrid.cli.main import main


def test_cli_validate_config_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """The validate-config command should return success for base config."""

    monkeypatch.setattr(
        "sys.argv", ["e3hybrid", "validate-config", "configs/base.yaml"]
    )

    assert main() == 0


def test_cli_write_metadata_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The write-metadata command should create a metadata artifact."""

    output_path = tmp_path / "environment.json"
    monkeypatch.setattr(
        "sys.argv",
        ["e3hybrid", "write-metadata", ".", str(output_path), "11"],
    )

    assert main() == 0
    assert output_path.is_file()


def test_cli_validate_config_fails_for_missing_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CLI should exit through argparse when config validation fails."""

    monkeypatch.setattr(
        "sys.argv", ["e3hybrid", "validate-config", "configs/missing.yaml"]
    )

    with pytest.raises(SystemExit):
        main()
