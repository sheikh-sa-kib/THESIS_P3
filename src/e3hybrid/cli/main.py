"""Command-line entry points for Phase 1 infrastructure."""

from __future__ import annotations

import argparse
from pathlib import Path

from e3hybrid.config.loader import load_project_config
from e3hybrid.core.exceptions import ConfigError
from e3hybrid.utils.logging import configure_logging
from e3hybrid.utils.reproducibility import (
    collect_environment_metadata,
    write_environment_metadata,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""

    parser = argparse.ArgumentParser(
        prog="e3hybrid",
        description="Infrastructure CLI for the E3-Hybrid research framework.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate-config", help="Validate a YAML project configuration."
    )
    validate_parser.add_argument("config_path", type=Path)

    metadata_parser = subparsers.add_parser(
        "write-metadata", help="Write environment metadata for a project root."
    )
    metadata_parser.add_argument("project_root", type=Path)
    metadata_parser.add_argument("output_path", type=Path)
    metadata_parser.add_argument("seed", type=int)
    return parser


def main() -> int:
    """Run the CLI and return an operating-system exit code."""

    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "validate-config":
            config = load_project_config(args.config_path)
            configure_logging(
                config.logging.level,
                config.logging.log_dir,
                config.logging.max_bytes,
                config.logging.backup_count,
            )
            print(f"Configuration is valid: {args.config_path}")
            return 0
        if args.command == "write-metadata":
            metadata = collect_environment_metadata(args.project_root, args.seed)
            write_environment_metadata(metadata, args.output_path)
            print(f"Environment metadata written: {args.output_path}")
            return 0
    except ConfigError as error:
        parser.error(str(error))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
